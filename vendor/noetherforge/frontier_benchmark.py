"""Compare the frozen predecessor with the expanded theorem language and kernel."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import tempfile
import time
from pathlib import Path

from .benchmark import fixtures
from .engine import search
from .goals import Goal,digest
from .laboratory import invent
from .novelty import screen
from .proofcheck import verify

ROOT=Path(__file__).resolve().parents[1]


def casebook():
    rational=[
        {'id':'lyness-symbolic','kind':'rational_recurrence','variables':['x','y','a'],'transitions':['y','(a+y)/x','a'],'parameters':['a'],'max_degree':3,'max_denominator_degree':2},
        {'id':'lyness-two','kind':'rational_recurrence','variables':['x','y'],'transitions':['y','(2+y)/x'],'max_degree':3,'max_denominator_degree':2},
        {'id':'reciprocal-orbit','kind':'rational_recurrence','variables':['x','y'],'transitions':['y','1/x'],'max_degree':3,'max_denominator_degree':2},
        {'id':'cayley-rotation','kind':'rational_recurrence','variables':['x','y','t'],'transitions':['((1-t**2)*x-2*t*y)/(1+t**2)','(2*t*x+(1-t**2)*y)/(1+t**2)','t'],'parameters':['t'],'max_degree':2,'max_denominator_degree':0}
    ]
    inequalities=[
        {'id':'three-variable-quartic','kind':'inequality','variables':['x','y','z'],'polynomial':'x**4+y**4+z**4-x**2*y**2-y**2*z**2-z**2*x**2','square_degree':2},
        {'id':'cauchy-four','kind':'inequality','variables':['x','y','a','b'],'polynomial':'(x**2+y**2)*(a**2+b**2)-(x*a+y*b)**2','square_degree':2},
        {'id':'interval-domain','kind':'inequality','variables':['x'],'polynomial':'x*(1-x)','nonnegative':['x','1-x'],'square_degree':0},
        {'id':'sharp-quadratic','kind':'inequality','variables':['x','y'],'polynomial':'5*x**2+6*x*y+5*y**2','reference':'x**2+y**2','square_degree':1,'optimize':True},
        {'id':'sharp-three','kind':'inequality','variables':['x','y','z'],'polynomial':'(x-y)**2+(y-z)**2+(z-x)**2+3*(x**2+y**2+z**2)','reference':'x**2+y**2+z**2','square_degree':1,'optimize':True}
    ]
    atlas=json.loads((ROOT/'noetherforge/examples/spectral-atlas.json').read_text())
    altered={**atlas,'id':'shifted-parameter-atlas','polynomial':'(2*t+5)*x**2+2*(2*t-3)*x*y+(2*t+5)*y**2','probe_points':['0','3/4','3/2','9/4','3','4']}
    return rational+inequalities+[atlas,altered]


def run(out):
    from benchmarks.baseline_v0.goals import Goal as OldGoal
    from benchmarks.baseline_v0.engine import search as old_search,Archive as OldArchive,inspect_candidate as old_inspect
    from benchmarks.baseline_v0.algebra import parse as old_parse

    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    provenance=json.loads((ROOT/'PROVENANCE.json').read_text())
    for name,expected in provenance['baseline_files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('The frozen predecessor changed')
    problems=casebook()
    contract={'schema_version':2,'new_programs':problems,'legacy_cases':[{'goal':g.as_dict(),'expected_positive':positive} for g,_,positive in fixtures()],'budgets':{'legacy_checks':64,'new_checks':200,'new_cooperative_wall_seconds':90},'baseline_checkpoint':provenance['prior_local_checkpoint'],'baseline_files':provenance['baseline_files'],'interpretation':'Representation and predicate expansion versus the frozen predecessor. Unsupported tasks are reported as unsupported, not mathematical failures. Known controls do not establish historical novelty.'}
    contract['hash']=digest(contract)
    (out/'contract.json').write_text(json.dumps(contract,indent=2)+'\n',encoding='utf-8',newline='\n')
    started=time.monotonic(); legacy=[]; frontier=[]
    for goal,oracle,positive in fixtures():
        new=search(goal,strategy='full_symbolic',budget=64,seconds=30)
        old=old_search(OldGoal.from_dict(goal.as_dict()),strategy='full_symbolic',budget=64,seconds=30)
        legacy.append({'goal':goal.as_dict(),'expected_positive':positive,'predecessor':old,'noether_forge':new})
        for result in (old,new):
            expected='CERTIFIED_INVARIANT' if positive else 'CERTIFIED_TEMPLATE_EXCLUSION'
            if result['status']!=expected: raise ValueError('A declared legacy case regressed')
    for problem in problems:
        if problem['kind']=='rational_recurrence':
            try:
                OldGoal.from_dict(problem)
                old_status='REPRESENTABLE'
            except (ValueError,KeyError,SyntaxError): old_status='UNSUPPORTED_VARIABLE_DENOMINATORS'
        else:
            old_status='UNSUPPORTED_ORDERED_OR_PARAMETER_FAMILY_PREDICATE'
        result=invent(problem,budget=200,seconds=90)
        if not result['status'].startswith('CERTIFIED_'):
            raise ValueError(f"The declared frontier control was not certified: {problem['id']} / {result['status']}")
        frontier.append({'problem':problem,'predecessor_status':old_status,'result':result})
    g=Goal('two-actions',['x','y','u','v'],['y','-x','v','-u'],4)
    parents=[g.certificate(old_parse(s,g.variables)) for s in ('x**2+y**2','u**2+v**2')]
    target=g.certificate(old_parse('(x**2+y**2)*(u**2+v**2)',g.variables))
    with tempfile.TemporaryDirectory() as temp:
        archive=OldArchive(Path(temp)/'old.sqlite')
        for parent in parents:
            p={tuple(t['powers']):__import__('fractions').Fraction(t['coefficient']) for t in parent['candidate']}
            old_inspect(OldGoal.from_dict(g.as_dict()),p,archive)
        p=old_parse('(x**2+y**2)*(u**2+v**2)',g.variables)
        old_result=old_inspect(OldGoal.from_dict(g.as_dict()),p,archive); archive.close()
    new_result=screen(target,parents)
    novelty={'predecessor':old_result,'noether_forge':new_result}
    if old_result['local_novelty']!='NEW_TO_LOCAL_ARCHIVE' or new_result['status']!='DERIVED_FROM_KNOWN_ALGEBRA':
        raise ValueError('The intended multi-generator novelty control did not distinguish the implementations')
    bundle={'schema_version':2,'contract_hash':contract['hash'],'legacy':legacy,'frontier':frontier,'algebraic_novelty_control':novelty,'runtime_seconds':time.monotonic()-started,'historically_novel_results_verified':0}
    (out/'results.json').write_text(json.dumps(bundle,indent=2)+'\n',encoding='utf-8',newline='\n')
    report=['# Expanded mathematics comparison','',contract['interpretation'],'',f"Legacy parity: {len(legacy)}/{len(legacy)} cases for both implementations.",'',f"Expanded programs certified: {len(frontier)}/{len(frontier)}.",'','| Program | Predecessor | NOETHER-FORGE |','|---|---|---|']
    for row in frontier: report.append(f"| {row['problem']['id']} | {row['predecessor_status']} | {row['result']['status']} |")
    report += ['','The predecessor treated the product of two known independent actions as new to its archive. The new algebra membership checker supplied an independently verified two-generator derivation.','',f"Runtime: {bundle['runtime_seconds']:.3f}s. No improvement in model weights or historical novelty is claimed.",'','Every hypothesis, counterexample and accepted certificate is retained in results.json.']
    (out/'REPORT.md').write_text('\n'.join(report)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'legacy_cases':len(legacy),'expanded_programs':len(frontier),'novelty_control':new_result['status'],'path':str(out),'runtime_seconds':bundle['runtime_seconds']},indent=2))
    return bundle


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
