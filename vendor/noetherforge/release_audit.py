"""Execute the full declared mathematical release oracle and preserve its evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs():
    files=list((ROOT/'noetherforge').glob('*.py'))+list((ROOT/'noetherforge/tests').glob('*.py'))+list((ROOT/'noetherforge/examples').glob('*.json'))+list((ROOT/'benchmarks/baseline_v0').glob('*.py'))
    files += [ROOT/'PROVENANCE.json',ROOT/'pyproject.toml',ROOT/'vendor/openai-math/CONTENTS.md']
    return sorted(files)


def execute(argv,log,seconds):
    start=time.monotonic()
    try:
        proc=subprocess.run(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=seconds)
        output,code=proc.stdout,proc.returncode
    except subprocess.TimeoutExpired as error:
        output,code=error.stdout or b'',124
    Path(log).write_bytes(output)
    fatal=any(s in output for s in (b'Fatal Python error',b'Windows fatal exception'))
    return {'argv':argv,'exit_status':code,'runtime_seconds':time.monotonic()-start,'hard_wall_seconds':seconds,'fatal_diagnostic':fatal,'log':str(Path(log).relative_to(ROOT))}


def audit(out):
    from .corpus import save_index
    from .ledger import ClaimLedger

    out=Path(out).resolve()
    if not out.is_relative_to(ROOT): raise ValueError('Audit output must stay inside this project')
    out.mkdir(parents=True,exist_ok=False)
    started=datetime.now(timezone.utc).isoformat(); start=time.monotonic()
    before={p.relative_to(ROOT).as_posix():sha(p) for p in inputs()}
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    corpus=save_index(ROOT/'vendor/openai-math',out/'corpus.json')
    commands=[execute([sys.executable,'-B','-m','unittest','discover','-s','noetherforge/tests','-v'],out/'tests.log',300)]
    if commands[-1]['exit_status']==0 and not commands[-1]['fatal_diagnostic']:
        commands.append(execute([sys.executable,'-B','-m','noetherforge.frontier_benchmark','--out',str(out/'benchmark')],out/'benchmark.log',300))
    if len(commands)>1 and commands[-1]['exit_status']==0 and not commands[-1]['fatal_diagnostic']:
        commands.append(execute([sys.executable,'-I','-B',str(ROOT/'noetherforge/frontier_replay.py'),str(out/'benchmark')],out/'isolated-replay.log',180))
    ledger=ClaimLedger(out/'runtime-ledger.sqlite')
    if len(commands)==3 and commands[-1]['exit_status']==0:
        results=json.loads((out/'benchmark/results.json').read_text())
        for row in results['frontier']:
            result=row['result']
            for accepted in result.get('accepted',[]): ledger.accept(accepted['certificate'])
            if result.get('certificate'): ledger.accept(result['certificate'])
            for proposal in result.get('events',[]):
                if proposal.get('verification',{}).get('status')=='REFUTED': ledger.reject(proposal['certificate'],proposal['verification'])
        ledger.accept(results['algebraic_novelty_control']['noether_forge']['certificate'])
    ledger_result=ledger.recheck()
    snapshot=ledger.export(); ledger.close()
    (out/'ledger.json').write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8',newline='\n')
    after={p.relative_to(ROOT).as_posix():sha(p) for p in inputs()}
    unchanged=before==after
    success=len(commands)==3 and unchanged and all(c['exit_status']==0 and not c['fatal_diagnostic'] for c in commands)
    software=[{'name':'Python','version':platform.python_version()}]
    for name in ('scipy','numpy','sympy'):
        try: software.append({'name':name,'version':importlib.metadata.version(name)})
        except importlib.metadata.PackageNotFoundError: pass
    artifacts=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.suffix!='.sqlite']
    manifest={'schema_version':1,'claim_id':'NOETHER-FORGE-EXPANDED-MATHEMATICS-RELEASE','repository':{'commit':revision,'dirty':True},'command':[sys.executable,'-B','-m','noetherforge.audit','--out',str(out)],'executed_commands':commands,'environment':{'software':software,'hardware':f'{platform.system()} {platform.machine()} {platform.processor()}'},'mathematics':{'assertion_tested':'Legacy parity on twelve frozen controls, eleven expanded mathematical programs, algebraic novelty and exact independent replay of all retained claims','coefficient_domain':'QQ for identities; RR for ordered inequalities','conventions':'Rational expressions retain syntactic nonzero guards; square weights and inequalities are exact; sharp parameter atlases require uniform equality witnesses and exact interval coverage','inputs':[{'path':p,'sha256_before':h,'sha256_after':after.get(p)} for p,h in before.items()],'bounds':{'legacy_controls':12,'expanded_controls':11,'legacy_checks_per_case':64,'rational_checks_per_case':200,'max_rational_numerator_coefficients':180,'word_polynomial_term_cap':20000,'coefficient_bit_cap':4096,'subprocess_wall_seconds':[c['hard_wall_seconds'] for c in commands]},'non_claims':['Known mathematical controls do not establish historical novelty','No training or weight changes in the unreleased OpenAI model','No assertion that failed bounded searches prove nonintegrability or negativity','New predicate support is not a claim of superiority to all existing mathematical software']},'randomness':{'used':True,'generator':'Python random.Random','seed':7319007},'run':{'started_at':started,'runtime_seconds':time.monotonic()-start,'exit_status':0 if success else 1},'outputs':artifacts,'checks':[f'Source inputs unchanged: {unchanged}',f'Ledger exact replay: {ledger_result}',f'Corpus provenance: {corpus["upstream_commit"]}; {corpus["counts"]}','The isolated replay binds certificates to the actual goal, domain, parameter range and requested predicate'],'result':'FULL_RELEASE_ORACLE_PASSED' if success else 'AUDIT_INCOMPLETE_OR_FAILED','residual_risks':['Version 1 manifest includes additional input hashes and hard subprocess caps but is not the Mathbox v2 runner schema','Historical novelty and general open-problem capability remain unestablished','Sparse-square and monomial-denominator dictionaries are bounded discovery mechanisms; their failures are inconclusive']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'result':manifest['result'],'path':str(out),'runtime_seconds':manifest['run']['runtime_seconds'],'source_inputs_unchanged':unchanged,'ledger':ledger_result},indent=2))
    return 0 if success else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--out',type=Path,required=True)
    raise SystemExit(audit(parser.parse_args().out))
