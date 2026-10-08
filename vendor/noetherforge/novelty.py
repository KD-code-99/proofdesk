"""Proof-producing membership tests for algebras of several known invariants."""

from __future__ import annotations

import itertools
from fractions import Fraction as Q

from . import algebra as A
from .proofcheck import verify


def screen(target,parents,max_degree=None,max_columns=500):
    if not parents:
        return {'status':'NO_KNOWN_GENERATORS','historical_novelty':'UNREVIEWED'}
    if len(parents)>16 or verify(target)['status']!='CERTIFIED_POLYNOMIAL_IDENTITY':
        raise ValueError('Algebra screening needs a verified target and at most sixteen parents')
    goal=target['goal']; names=goal['variables']; dim=len(names)
    p={tuple(t['powers']):Q(t['coefficient']) for t in target['candidate']}
    degree=max_degree or max(map(sum,p))
    if not 1<=degree<=8: raise ValueError('Algebra consequence degree cap')
    generators=[]
    for cert in parents:
        if cert['map_hash']!=target['map_hash'] or verify(cert)['status']!='CERTIFIED_POLYNOMIAL_IDENTITY':
            raise ValueError('A proposed generator has a different map or invalid proof')
        generators.append({tuple(t['powers']):Q(t['coefficient']) for t in cert['candidate']})
    parameters=goal.get('parameters',[])
    for name in parameters:
        generators.append({tuple(int(i==names.index(name)) for i in range(dim)):Q(1)})
    weights=[max(map(sum,g)) for g in generators]
    columns=[({(0,)*dim:Q(1)},(0,)*len(generators))]
    for count in range(1,degree+1):
        for combo in itertools.combinations_with_replacement(range(len(generators)),count):
            if sum(weights[i] for i in combo)>degree: continue
            if len(columns)>=max_columns:
                return {'status':'SCREENING_LIMIT','historical_novelty':'UNREVIEWED','scope':'The declared generated-algebra column cap was reached'}
            poly={(0,)*dim:Q(1)}
            for i in combo: poly=A.mul(poly,generators[i])
            columns.append((poly,tuple(combo.count(i) for i in range(len(generators)))))
    monoms=sorted(set(p).union(*(set(g) for g,_ in columns)))
    matrix=[[g.get(m,Q(0)) for g,_ in columns]+[-p.get(m,Q(0))] for m in monoms]
    relations=A.nullspace(matrix,len(columns)+1)
    relation=next((v for v in relations if v[-1]),None)
    if relation is None:
        return {'status':'NO_DERIVATION_FOUND_WITHIN_BOUNDS','weighted_degree_bound':degree,'columns':len(columns),'historical_novelty':'UNREVIEWED','scope':'This is not an algebraic independence proof or a complete historical novelty test'}
    combination=[]
    for (_,exponents),c in zip(columns,relation[:-1]):
        if c:
            combination.append({'coefficient':str(c/relation[-1]),'generator_powers':list(exponents[:len(parents)]),'parameter_powers':list(exponents[len(parents):])})
    cert={'schema_version':2,'kind':'algebraic_consequence','target':target,'parents':parents,'combination':combination,'weighted_degree_bound':degree}
    evidence=verify(cert)
    if evidence['status']!='CERTIFIED_ALGEBRAIC_CONSEQUENCE':
        raise AssertionError('Independent algebra consequence checker disagrees')
    return {'status':'DERIVED_FROM_KNOWN_ALGEBRA','certificate':cert,'verification':evidence,'columns':len(columns),'historical_novelty':'NOT_NEW_AS_AN_INDEPENDENT_GENERATOR'}
