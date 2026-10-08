"""Run typed mathematical programs and retain their actual proof feedback."""

from __future__ import annotations

import json
from pathlib import Path

from .goals import Goal
from .engine import search
from .rational import RationalGoal,discover as discover_rational
from .inequalities import discover as discover_inequality
from .ledger import ClaimLedger


def invent(problem,budget=200,seconds=90,ledger=None):
    kind=problem.get('kind','polynomial_recurrence')
    if kind=='rational_recurrence':
        result=discover_rational(RationalGoal.from_dict(problem),budget,seconds)
    elif kind=='inequality_atlas':
        from .atlas import discover
        result=discover(problem,seconds)
    elif kind=='inequality':
        result=discover_inequality(problem,square_degree=problem.get('square_degree',2),optimize=problem.get('optimize',False),seconds=seconds)
    elif kind=='polynomial_recurrence':
        result=search(Goal.from_dict(problem),strategy='full_symbolic',budget=budget,seconds=seconds)
    else:
        raise ValueError('Unsupported mathematical program kind')
    if ledger:
        claims=[]
        for item in result.get('accepted',[]):
            cert=item['certificate']
            if cert['kind']=='polynomial_invariant':
                from .novelty import screen
                novelty=screen(cert,ledger.polynomial_generators(cert['map_hash']))
                item['algebraic_novelty_screen']=novelty
                if novelty.get('certificate'): ledger.accept(novelty['certificate'])
            claims.append(ledger.accept(cert))
        if result.get('certificate'): claims.append(ledger.accept(result['certificate']))
        for event in result.get('events',[]):
            if event.get('verification',{}).get('status')=='REFUTED':
                ledger.reject(event['certificate'],event['verification'])
        result['ledger_claims']=claims
    return result


def save(result,out):
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    (out/'result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    certificates=[a['certificate'] for a in result.get('accepted',[])]+([result['certificate']] if result.get('certificate') else [])
    for i,cert in enumerate(certificates):
        (out/f'proof-{i+1}.json').write_text(json.dumps(cert,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    lines=['# Mathematical program result','',f"Status: `{result['status']}`",'']
    if result.get('goal'): lines += [f"Problem: `{result['goal']['id']}`",'']
    for accepted in result.get('accepted',[]): lines += [f"Invariant: `{accepted['formula']}`",'']
    if result.get('verification'): lines += [f"Verification: `{result['verification']}`",'']
    lines += ['Historical novelty requires a separate source and prior-result review.','',result.get('scope','')]
    (out/'RESULT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    return out
