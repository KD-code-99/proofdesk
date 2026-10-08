"""Standalone proof kernel for rational identities, inequalities and derivations.

No search module, numerical optimizer or search-side rational arithmetic is
imported. Polynomial monomials are sorted words, not search exponent vectors.
Run: python -I -B noetherforge/proofcheck.py certificate.json
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import re
import sys
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

_spec = importlib.util.spec_from_file_location('noether_independent_polynomials',Path(__file__).with_name('verifier.py'))
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)


def exact(value):
    if not isinstance(value,str) or not re.fullmatch(r'-?\d{1,1250}(/\d{1,1250})?',value):
        raise ValueError('Expected an exact rational string')
    return F(value)


def canonical_guard(poly,dim):
    if not poly:
        raise ValueError('The claimed domain is empty')
    if not any(w for w in poly): return None
    lcm = math.lcm(*(c.denominator for c in poly.values()))
    gcd = abs(math.gcd(*(int(c*lcm) for c in poly.values())))
    first = min(poly,key=lambda w:tuple(w.count(i) for i in range(dim)))
    sign = 1 if poly[first]>0 else -1
    normalized = {w:F(int(c*lcm)//gcd*sign) for w,c in poly.items()}
    ts = [{'powers':[w.count(i) for i in range(dim)],'coefficient':str(c)} for w,c in normalized.items()]
    return json.dumps(sorted(ts,key=lambda t:(sum(t['powers']),t['powers'])),sort_keys=True)


def guard_set(guards,dim):
    out = {}
    if len(guards)>1000: raise P.VerificationLimit('Rational guard cap')
    for g in guards:
        key = canonical_guard(g,dim)
        if key is not None: out[key]=g
    return out


class FieldElement:
    def __init__(self,n,d=None,guards=()):
        self.n,self.d = P.trim(n),P.trim({():F(1)} if d is None else d)
        if not self.d: raise ValueError('Zero rational denominator')
        self.guards=list(guards)
        # Independent monomial cancellation, expressed with word multiplicities.
        if self.n:
            counts = [Counter(w) for w in self.n]+[Counter(w) for w in self.d]
            common = Counter()
            for i in set().union(*(set(c) for c in counts)):
                common[i]=min(c[i] for c in counts)
            if any(common.values()):
                def reduce_word(w):
                    c=Counter(w); c.subtract(common)
                    return tuple(i for i in sorted(c) for _ in range(c[i]))
                self.n={reduce_word(w):c for w,c in self.n.items()}
                self.d={reduce_word(w):c for w,c in self.d.items()}
        else:
            self.d={():F(1)}

    def plus(self,b):
        return FieldElement(P.plus(P.product(self.n,b.d),P.product(b.n,self.d)),P.product(self.d,b.d),self.guards+b.guards)

    def negative(self):
        return FieldElement({w:-c for w,c in self.n.items()},self.d,self.guards)

    def minus(self,b): return self.plus(b.negative())

    def times(self,b):
        return FieldElement(P.product(self.n,b.n),P.product(self.d,b.d),self.guards+b.guards)

    def over(self,b):
        if not b.n: raise ValueError('Division by zero rational function')
        return FieldElement(P.product(self.n,b.d),P.product(self.d,b.n),self.guards+b.guards+[b.n])

    def power(self,k):
        if k<0: return FieldElement({():F(1)}).over(self.power(-k))
        result=FieldElement({():F(1)},guards=self.guards)
        for _ in range(k): result=result.times(self)
        return result

    def at(self,point):
        if any(not P.value(g,point) for g in self.guards):
            raise ValueError('Evaluation is outside the original expression domain')
        d=P.value(self.d,point)
        if not d: raise ValueError('Undefined rational evaluation')
        return P.value(self.n,point)/d


def expression(text,names):
    if not isinstance(text,str) or len(text)>12000: raise ValueError('Invalid rational syntax')
    tree=ast.parse(text,mode='eval')
    if sum(1 for _ in ast.walk(tree))>1500: raise P.VerificationLimit('Rational expression cap')
    def walk(node):
        if isinstance(node,ast.Name) and node.id in names:
            return FieldElement({(names.index(node.id),):F(1)})
        if isinstance(node,ast.Constant) and type(node.value) is int:
            return FieldElement({():F(node.value)} if node.value else {})
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            p=walk(node.operand)
            return p.negative() if isinstance(node.op,ast.USub) else p
        if isinstance(node,ast.BinOp):
            if isinstance(node.op,ast.Pow):
                rhs,sgn=node.right,1
                if isinstance(rhs,ast.UnaryOp) and isinstance(rhs.op,ast.USub): rhs,sgn=rhs.operand,-1
                if not isinstance(rhs,ast.Constant) or type(rhs.value) is not int or not 0<=rhs.value<=8:
                    raise ValueError('Invalid rational exponent')
                return walk(node.left).power(sgn*rhs.value)
            a,b=walk(node.left),walk(node.right)
            if isinstance(node.op,ast.Add): return a.plus(b)
            if isinstance(node.op,ast.Sub): return a.minus(b)
            if isinstance(node.op,ast.Mult): return a.times(b)
            if isinstance(node.op,ast.Div): return a.over(b)
        raise ValueError('Unsupported rational syntax')
    return walk(tree.body)


def substitute(poly,maps):
    result=FieldElement({})
    for word,c in poly.items():
        term=FieldElement({():c})
        for i in word: term=term.times(maps[i])
        result=result.plus(term)
    return result


def variables(goal):
    names=goal['variables']
    if not isinstance(names,list) or not 1<=len(names)<=4 or len(set(names))!=len(names) or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,30}',v) for v in names):
        raise ValueError('Invalid quantified variables')
    return names


def rational_context(cert):
    if cert.get('schema_version')!=2 or cert.get('domain')!='QQ': raise ValueError('Invalid rational certificate schema')
    goal=cert['goal']; names=variables(goal)
    params=goal.get('parameters',[])
    if len(set(params))!=len(params) or not set(params)<set(names) or len(goal['transitions'])!=len(names):
        raise ValueError('Invalid rational parameter or transition definitions')
    payload={'kind':'rational_recurrence','variables':names,'transitions':goal['transitions'],'parameters':params,'guards':goal.get('guards',[])}
    h=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
    if h!=cert['map_hash']: raise ValueError('Rational certificate has a stale or altered map')
    maps=[expression(s,names) for s in goal['transitions']]
    for name in params:
        if maps[names.index(name)].minus(expression(name,names)).n:
            raise ValueError('A claimed parameter changes')
    guards=[g for m in maps for g in m.guards]+[P.expand(g,names) for g in goal.get('guards',[])]
    return goal,names,maps,{names.index(p) for p in params},guards


def verify_rational(cert):
    _,names,maps,params,guards=rational_context(cert)
    n=P.candidate_terms(cert['numerator'],len(names)); d=P.candidate_terms(cert['denominator'],len(names))
    initial=FieldElement(n).over(FieldElement(d))
    after=substitute(n,maps).over(substitute(d,maps))
    required=guard_set(guards+initial.guards+after.guards,len(names))
    supplied=guard_set([P.candidate_terms(g,len(names)) for g in cert['required_nonzero_guards']],len(names))
    if set(required)!=set(supplied):
        raise ValueError('The certificate omits, changes or adds domain guards')
    active=False
    for i in range(len(names)):
        if i in params: continue
        def diff(poly):
            out={}
            for w,c in poly.items():
                if i in w:
                    v=list(w); v.remove(i)
                    out[tuple(v)]=c*w.count(i)
            return out
        if P.plus(P.product(diff(n),d),P.product(n,diff(d)),-1): active=True
    if not active: return {'status':'TRIVIAL_PARAMETER_FUNCTION'}
    residual=after.minus(initial)
    if not residual.n:
        return {'status':'CERTIFIED_RATIONAL_INVARIANT','arithmetic':'exact_rational','domain_nonzero_guard_count':len(required),'historical_novelty':'UNREVIEWED'}
    avoid=P.trim(residual.n)
    for g in required.values(): avoid=P.product(avoid,g)
    # Include all evaluation denominators, even if they are redundant domain guards.
    avoid=P.product(avoid,residual.d)
    point=P.witness(avoid,len(names))
    image=[m.at(point) for m in maps]
    before,after_value=initial.at(point),initial.at(image)
    if before==after_value or any(not P.value(g,point) for g in required.values()):
        raise AssertionError('Invalid rational counterexample')
    return {'status':'REFUTED','counterexample':{name:str(v) for name,v in zip(names,point)},'before':str(before),'after':str(after_value),'domain_nonzero_guard_count':len(required)}


def verify_inequality(cert):
    if cert.get('schema_version')!=2 or cert.get('domain')!='RR': raise ValueError('Invalid inequality schema')
    statement=cert['statement']; names=variables(statement)
    p=P.expand(statement['polynomial'],names)
    q=P.expand(statement.get('reference','0'),names)
    parameters=statement.get('parameters',[])
    if len(set(parameters))!=len(parameters) or not set(parameters)<=set(names):
        raise ValueError('Invalid inequality parameter set')
    if 'bound_expression' in cert:
        bound_poly=P.expand(cert['bound_expression'],names)
        param_indexes={names.index(s) for s in parameters}
        if any(any(i not in param_indexes for i in w) for w in bound_poly):
            raise ValueError('A bound expression depends on the state it is supposed to bound')
        bound_text=cert['bound_expression']
    else:
        bound=exact(cert.get('bound','0'))
        bound_poly={():bound}
        bound_text=str(bound)
    target=P.plus(p,P.product(bound_poly,q),-1)
    assumptions=[P.expand(g,names) for g in statement.get('nonnegative',[])]
    if len(assumptions)>12 or len(cert['squares'])>2000: raise P.VerificationLimit('Inequality certificate size cap')
    rhs={}
    for term in cert['squares']:
        weight=exact(term['weight'])
        if weight<0: raise ValueError('Negative square weight is not a proof of nonnegativity')
        polynomial=P.expand(term['polynomial'],names)
        square=P.product(polynomial,polynomial)
        factors=term.get('assumptions',[])
        if len(factors)>12 or any(type(i) is not int or not 0<=i<len(assumptions) for i in factors):
            raise ValueError('A square cites an absent domain assumption')
        for i in factors: square=P.product(square,assumptions[i])
        rhs=P.plus(rhs,{w:weight*c for w,c in square.items()})
    residual=P.plus(target,rhs,-1)
    if residual:
        return {'status':'INVALID_CERTIFICATE','reason':'The asserted sum of nonnegative terms is not the target polynomial','residual_terms':len(residual)}
    result={'status':'CERTIFIED_POLYNOMIAL_INEQUALITY','bound':bound_text,'domain_nonnegative_assumptions':len(assumptions),'historical_novelty':'UNREVIEWED','sharpness':'UNPROVED'}
    if cert.get('equality_witness') is not None:
        point=[exact(s) for s in cert['equality_witness']]
        if len(point)!=len(names) or any(P.value(g,point)<0 for g in assumptions) or P.value(q,point)<=0 or P.value(target,point)!=0:
            raise ValueError('An equality witness does not prove sharpness on the declared domain')
        result['status']='CERTIFIED_SHARP_INEQUALITY'
        result['sharpness']='PROVED_BY_EXACT_ADMISSIBLE_WITNESS'
    if cert.get('parameter_witness') is not None:
        witness=cert['parameter_witness']
        if len(witness)!=len(names) or not parameters:
            raise ValueError('Invalid parameter-family witness')
        params={names.index(s) for s in parameters}
        maps=[P.expand(s,names) for s in witness]
        for i,m in enumerate(maps):
            if any(any(j not in params for j in w) for w in m):
                raise ValueError('A parameter-family witness depends on an unspecified state')
            if i in params and m!={(i,):F(1)}:
                raise ValueError('A parameter-family witness changes the parameter')
        def specialize(poly):
            result={}
            for w,c in poly.items():
                term={():c}
                for i in w: term=P.product(term,maps[i])
                result=P.plus(result,term)
            return result
        if specialize(target):
            raise ValueError('The witness does not attain the bound for the entire parameter family')
        reference=specialize(q)
        if set(reference)!={()} or reference[()]<=0:
            raise ValueError('The uniform witness lacks a strictly positive constant reference')
        parameter_constraints=[g for g in assumptions if all(all(i in params for i in w) for w in g)]
        for g in assumptions:
            image=specialize(g)
            if image and not (set(image)=={()} and image[()]>=0) and image not in parameter_constraints:
                raise ValueError('Uniform witness admissibility was not proved on the full domain')
        result['status']='CERTIFIED_UNIFORM_SHARP_INEQUALITY'
        result['sharpness']='PROVED_FOR_EVERY_ADMISSIBLE_PARAMETER'
    return result


def verify_atlas(cert):
    if cert.get('schema_version')!=2 or cert.get('domain')!='RR':
        raise ValueError('Invalid parameter atlas schema')
    statement=cert['statement']; names=variables(statement)
    parameter=cert['parameter']
    if parameter not in names or statement.get('parameters')!=[parameter]:
        raise ValueError('Atlas needs one explicitly quantified parameter')
    lower,upper=cert['parameter_range']
    lower=exact(lower); upper=None if upper is None else exact(upper)
    if upper is not None and upper<=lower: raise ValueError('Empty or reversed atlas interval')
    pieces=cert['pieces']
    if not 1<=len(pieces)<=32: raise ValueError('Atlas piece count cap')
    previous=lower
    for index,piece in enumerate(pieces):
        lo,hi=piece['interval']; lo=exact(lo); hi=None if hi is None else exact(hi)
        if previous is None or lo!=previous or (hi is not None and hi<=lo):
            raise ValueError('The atlas has a coverage gap, overlap, or reversed interval')
        child=piece['certificate']; definition=child['statement']
        if definition['variables']!=names or definition.get('parameters')!=[parameter] or P.expand(definition['polynomial'],names)!=P.expand(statement['polynomial'],names) or P.expand(definition.get('reference','0'),names)!=P.expand(statement['reference'],names):
            raise ValueError('Atlas pieces prove different mathematical statements')
        expected=[P.expand(f'{parameter}-({lo})',names)]
        if hi is not None: expected.append(P.expand(f'({hi})-{parameter}',names))
        supplied=[P.expand(s,names) for s in definition.get('nonnegative',[])]
        if supplied!=expected:
            raise ValueError('An atlas piece has missing or extra hypotheses')
        if verify_inequality(child)['status']!='CERTIFIED_UNIFORM_SHARP_INEQUALITY':
            raise ValueError('An atlas piece is not uniformly sharp')
        previous=hi
    if previous!=upper:
        raise ValueError('The atlas does not cover the requested parameter range')
    return {'status':'CERTIFIED_SHARP_PARAMETER_ATLAS','pieces':len(pieces),'coverage':'EXACT_CLOSED_INTERVAL_COVER','parameter_range':cert['parameter_range'],'historical_novelty':'UNREVIEWED'}


def verify_consequence(cert):
    target=cert['target']; parents=cert['parents']
    if not 1<=len(parents)<=16: raise ValueError('Invalid algebra generators')
    if P.verify(target)['status']!='CERTIFIED_POLYNOMIAL_IDENTITY': raise ValueError('Target is not a proved invariant')
    names=target['goal']['variables']; n=len(names)
    generators=[]
    for parent in parents:
        if parent['map_hash']!=target['map_hash'] or P.verify(parent)['status']!='CERTIFIED_POLYNOMIAL_IDENTITY':
            raise ValueError('An algebra generator has an incompatible map or proof')
        generators.append(P.candidate_terms(parent['candidate'],n))
    result={}
    parameters=target['goal'].get('parameters',[])
    if len(cert['combination'])>1000: raise P.VerificationLimit('Algebra consequence cap')
    for term in cert['combination']:
        exponents=term['generator_powers']
        if len(exponents)!=len(generators) or any(type(k) is not int or not 0<=k<=8 for k in exponents):
            raise ValueError('Invalid algebra combination powers')
        poly={():exact(term['coefficient'])}
        parameter_powers=term.get('parameter_powers',[0]*len(parameters))
        if len(parameter_powers)!=len(parameters) or any(type(k) is not int or not 0<=k<=8 for k in parameter_powers):
            raise ValueError('Invalid fixed-parameter powers')
        word=tuple(sorted(names.index(name) for name,k in zip(parameters,parameter_powers) for _ in range(k)))
        poly=P.product(poly,{word:F(1)})
        for g,k in zip(generators,exponents):
            for _ in range(k): poly=P.product(poly,g)
        result=P.plus(result,poly)
    target_poly=P.candidate_terms(target['candidate'],n)
    return {'status':'CERTIFIED_ALGEBRAIC_CONSEQUENCE' if not P.plus(result,target_poly,-1) else 'REFUTED','generators':len(generators)}


def verify(cert):
    kind=cert.get('kind')
    if kind=='rational_invariant': return verify_rational(cert)
    if kind=='sos_inequality': return verify_inequality(cert)
    if kind=='sharp_inequality_atlas': return verify_atlas(cert)
    if kind=='algebraic_consequence': return verify_consequence(cert)
    return P.verify(cert)


if __name__=='__main__':
    try:
        result=verify(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
        print(json.dumps(result,indent=2))
        raise SystemExit(0 if result['status'].startswith('CERTIFIED_') else 2)
    except (ValueError,KeyError,OSError,SyntaxError,P.VerificationLimit) as error:
        print(json.dumps({'status':'INVALID_OR_INCONCLUSIVE','reason':str(error)}))
        raise SystemExit(1)
