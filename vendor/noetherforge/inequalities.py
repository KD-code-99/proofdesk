"""Discover exact nonnegative decompositions and sharp inequality constants.

HiGHS is a proposal mechanism. Exact coefficient reconstruction and the separate
proof kernel are the acceptance mechanism. Numerical infeasibility is scoped.
"""

from __future__ import annotations

import itertools
import math
import time
from fractions import Fraction as Q

from . import algebra as A
from .goals import digest
from .proofcheck import verify


def square_dictionary(names,degree=2):
    dim=len(names)
    basis=[(0,)*dim]+A.monomials(dim,degree)
    if len(basis)>50:
        raise ValueError('Square-form basis exceeds 50 monomials')
    forms=[{m:Q(1)} for m in basis]
    # Pairwise binomials provide sparse, interpretable certificates. Failure is
    # not a statement that no general SOS Gram matrix exists.
    for i,u in enumerate(basis):
        for v in basis[i+1:]:
            if sum(u)!=sum(v): continue
            for sign in (-1,1): forms.append({u:Q(1),v:Q(sign)})
    return forms


def combination_forms(names,square_degree,assumptions,max_assumption_product=2):
    dim=len(names)
    forms=square_dictionary(names,square_degree)
    products=[()]+[indices for d in range(1,min(max_assumption_product,len(assumptions))+1) for indices in itertools.combinations(range(len(assumptions)),d)]
    if len(products)*len(forms)>3000:
        raise A.ResourceLimit('Nonnegative certificate dictionary exceeds 3000 columns')
    result=[]
    for indexes in products:
        multiplier={(0,)*dim:Q(1)}
        for i in indexes: multiplier=A.mul(multiplier,assumptions[i])
        for form in forms:
            term=A.mul(A.mul(form,form),multiplier)
            result.append((form,indexes,term))
    return result


def rational_solve(matrix,rhs,proposed):
    """Recover exact coefficients on the numerically selected support."""
    support=[i for i,x in enumerate(proposed) if abs(float(x))>1e-8]
    if not support: return None
    rows=[[row[i] for i in support]+[-value] for row,value in zip(matrix,rhs)]
    basis=A.nullspace(rows,len(support)+1)
    relation=next((v for v in basis if v[-1]),None)
    if relation is None: return None
    answer=[Q(0)]*len(proposed)
    for index,coefficient in zip(support,relation[:-1]): answer[index]=coefficient/relation[-1]
    return answer


def equality_witness(forms,weights,names,p,q,assumptions):
    """Try exact nullspace witnesses for homogeneous linear square forms."""
    dim=len(names)
    rows=[]
    for (form,indices,_),weight in zip(forms,weights):
        if not weight or indices: continue
        if any(sum(m)!=1 for m in form): return None
        rows.append([form.get(tuple(int(i==j) for i in range(dim)),Q(0)) for j in range(dim)])
    for point in A.nullspace(rows,dim):
        if A.evaluate(q,point)>0 and A.evaluate(p,point)==0 and all(A.evaluate(g,point)>=0 for g in assumptions):
            return [str(x) for x in point]
    return None


def discover(statement,square_degree=2,optimize=False,seconds=30):
    from scipy.optimize import linprog
    import numpy as np

    started=time.monotonic()
    names=list(statement['variables'])
    if not 1<=len(names)<=4 or len(set(names))!=len(names):
        raise ValueError('Use one to four distinct inequality variables')
    if type(square_degree) is not int or not 0<=square_degree<=3 or not 0<seconds<=3600:
        raise ValueError('Invalid inequality search bounds')
    target=A.parse(statement['polynomial'],names)
    reference=A.parse(statement.get('reference','0'),names)
    assumptions=[A.parse(s,names) for s in statement.get('nonnegative',[])]
    if len(assumptions)>6: raise ValueError('At most six explicit nonnegative assumptions')
    forms=combination_forms(names,square_degree,assumptions)
    support=sorted(set(target).union(reference).union(*(set(term) for _,_,term in forms)))
    matrix=[[term.get(m,Q(0)) for _,_,term in forms] for m in support]
    rhs=[target.get(m,Q(0)) for m in support]
    if optimize:
        if not reference: raise ValueError('A nonzero reference polynomial is required for best-constant search')
        for m,row in zip(support,matrix): row.append(reference.get(m,Q(0)))
    objective=[0.0]*len(forms)+([-1.0] if optimize else [])
    bounds=[(0,None)]*len(forms)+([(None,None)] if optimize else [])
    # Official SciPy 1.18 API: explicit equality constraints, bounds, and HiGHS.
    # https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html
    result=linprog(objective,A_eq=np.array(matrix,dtype=float),b_eq=np.array(rhs,dtype=float),bounds=bounds,method='highs',options={'time_limit':float(seconds)})
    base={'schema_version':2,'statement':statement,'statement_hash':digest(statement),'metrics':{'dictionary_columns':len(forms),'coefficient_equations':len(support),'runtime_seconds':time.monotonic()-started},'numerical_proposal':{'status':int(result.status),'success':bool(result.success)},'scope':'A failed bounded sparse-square dictionary does not disprove nonnegativity or exclude other SOS representations.'}
    if not result.success:
        return {**base,'status':'NO_CERTIFICATE_IN_DECLARED_DICTIONARY','reason':str(result.message)}
    exact=rational_solve(matrix,rhs,result.x)
    if exact is None:
        return {**base,'status':'EXACT_RECONSTRUCTION_FAILED'}
    weights=exact[:len(forms)]
    if any(w<0 for w in weights):
        return {**base,'status':'EXACT_RECONSTRUCTION_FAILED','reason':'The reconstructed square weights are not nonnegative'}
    bound=exact[-1] if optimize else Q(0)
    certificate={'schema_version':2,'kind':'sos_inequality','domain':'RR','statement':statement,'bound':str(bound),'squares':[{'weight':str(w),'polynomial':A.format_poly(form,names),'assumptions':list(indices)} for (form,indices,_),w in zip(forms,weights) if w],'historical_novelty':'UNREVIEWED'}
    residual=A.add(target,A.scale(reference,-bound))
    if optimize:
        witness=equality_witness(forms,weights,names,residual,reference,assumptions)
        if witness is not None: certificate['equality_witness']=witness
    evidence=verify(certificate)
    if not evidence['status'].startswith('CERTIFIED_'):
        return {**base,'status':'EXACT_CERTIFICATE_REJECTED','verification':evidence}
    base['metrics']['runtime_seconds']=time.monotonic()-started
    return {**base,'status':evidence['status'],'certificate':certificate,'verification':evidence}
