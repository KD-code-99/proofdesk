"""Infer parameter regimes from exact solved cases, then prove their full domains.

Sampled optima propose breakpoints. Only uniform SOS identities, admissible
symbolic equality witnesses and a checked interval cover certify the atlas.
"""

from __future__ import annotations

import time
from fractions import Fraction as Q

from . import algebra as A
from .inequalities import discover as discover_inequality
from .proofcheck import verify


def specialize(poly,index,coefficient):
    out={}
    for m,c in poly.items():
        n=tuple(k for i,k in enumerate(m) if i!=index)
        out[n]=out.get(n,Q(0))+c*coefficient**m[index]
    return {m:c for m,c in out.items() if c}


def discover(problem,seconds=90):
    started=time.monotonic()
    names=problem['variables']; parameter=problem['parameter']
    if parameter not in names or len(names)>4: raise ValueError('Invalid atlas variables')
    parameter_index=names.index(parameter)
    active=[n for n in names if n!=parameter]
    if not active: raise ValueError('An atlas needs state variables')
    lo,hi=problem.get('parameter_range',['0',None])
    lo=Q(lo); hi=None if hi is None else Q(hi)
    probes=sorted(set(Q(s) for s in problem['probe_points']))
    if not 2<=len(probes)<=32 or any(t<lo or (hi is not None and t>hi) for t in probes):
        raise ValueError('Probe points must stay within the declared parameter interval')
    p=A.parse(problem['polynomial'],names); q=A.parse(problem['reference'],names)
    samples=[]
    for t in probes:
        sample={'id':problem['id']+'-probe','variables':active,'polynomial':A.format_poly(specialize(p,parameter_index,t),active),'reference':A.format_poly(specialize(q,parameter_index,t),active),'nonnegative':[]}
        result=discover_inequality(sample,square_degree=problem.get('square_degree',1),optimize=True,seconds=min(seconds,30))
        samples.append({'parameter':str(t),'result':result})
        if result['status']!='CERTIFIED_SHARP_INEQUALITY':
            return {'schema_version':2,'status':'PROBE_NOT_CERTIFIED_SHARP','samples':samples,'scope':'No uniform parameter claim was made'}
    regimes=[]
    for i,(left,right) in enumerate(zip(samples,samples[1:])):
        t0,t1=Q(left['parameter']),Q(right['parameter'])
        b0,b1=Q(left['result']['verification']['bound']),Q(right['result']['verification']['bound'])
        slope=(b1-b0)/(t1-t0); intercept=b0-slope*t0
        if not regimes or (slope,intercept)!=regimes[-1]['line']:
            regimes.append({'line':(slope,intercept),'sample_segment':i})
    crossings=[]
    for left,right in zip(regimes,regimes[1:]):
        a,b=left['line']; c,d=right['line']
        if a==c:
            return {'schema_version':2,'status':'NO_CONSISTENT_REGIME_INTERSECTION','samples':samples}
        crossing=(d-b)/(a-c)
        if crossing<=lo or (hi is not None and crossing>=hi) or (crossings and crossing<=crossings[-1]):
            return {'schema_version':2,'status':'INVALID_PROPOSED_PARTITION','samples':samples}
        crossings.append(crossing)
    ends=[lo,*crossings,hi]
    base_statement={'id':problem['id'],'variables':names,'parameters':[parameter],'polynomial':problem['polynomial'],'reference':problem['reference']}
    pieces=[]; attempts=[]
    for i,regime in enumerate(regimes):
        lower,upper=ends[i],ends[i+1]
        slope,intercept=regime['line']
        expression=f'({slope})*{parameter}+({intercept})'
        assumptions=[f'{parameter}-({lower})']+([f'({upper})-{parameter}'] if upper is not None else [])
        residual=f"({problem['polynomial']})-({expression})*({problem['reference']})"
        subproblem={**base_statement,'polynomial':residual,'nonnegative':assumptions}
        result=discover_inequality(subproblem,square_degree=problem.get('square_degree',1),optimize=False,seconds=min(seconds,30))
        attempts.append({'interval':[str(lower),None if upper is None else str(upper)],'proposed_bound':expression,'result':result})
        if not result['status'].startswith('CERTIFIED_'):
            return {'schema_version':2,'status':'REGIME_PROOF_NOT_OBTAINED','samples':samples,'attempts':attempts,'scope':'The sampled law was not accepted as a universal result'}
        cert=dict(result['certificate'])
        cert['statement']={**base_statement,'nonnegative':assumptions}
        cert.pop('bound',None); cert['bound_expression']=expression
        uniform=None
        for sample in samples:
            witness=sample['result']['certificate'].get('equality_witness')
            if witness is None: continue
            point=[]; j=0
            for name in names:
                if name==parameter: point.append(parameter)
                else: point.append(witness[j]); j+=1
            candidate={**cert,'parameter_witness':point}
            try:
                evidence=verify(candidate)
            except ValueError:
                continue
            if evidence['status']=='CERTIFIED_UNIFORM_SHARP_INEQUALITY':
                uniform=candidate; break
        if uniform is None:
            return {'schema_version':2,'status':'UNIFORM_SHARPNESS_NOT_PROVED','samples':samples,'attempts':attempts}
        pieces.append({'interval':[str(lower),None if upper is None else str(upper)],'certificate':uniform})
    certificate={'schema_version':2,'kind':'sharp_inequality_atlas','domain':'RR','statement':base_statement,'parameter':parameter,'parameter_range':[str(lo),None if hi is None else str(hi)],'pieces':pieces,'historical_novelty':'UNREVIEWED'}
    evidence=verify(certificate)
    return {'schema_version':2,'status':evidence['status'],'certificate':certificate,'verification':evidence,'samples':samples,'attempts':attempts,'metrics':{'certified_probes':len(samples),'universally_proved_pieces':len(pieces),'runtime_seconds':time.monotonic()-started},'scope':'The sample values proposed the regimes. Exact identities, uniform equality witnesses and interval coverage prove every admissible parameter, including the unbounded tail.'}
