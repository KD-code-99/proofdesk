"""Isolated replay of the expanded mathematics without importing the search code."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

spec=importlib.util.spec_from_file_location('noether_proof_kernel',Path(__file__).with_name('proofcheck.py'))
K=importlib.util.module_from_spec(spec); spec.loader.exec_module(K)


def check_run(run):
    records=0
    def bound(cert):
        if run.get('goal') and (cert.get('goal')!=run['goal'] or cert.get('map_hash')!=run['map_hash']):
            raise ValueError('A saved proof belongs to a different program goal')
        return K.verify(cert)
    for row in run.get('events',[]):
        if row.get('certificate'):
            if bound(row['certificate'])!=row['verification']: raise ValueError('Proposal evidence failed replay')
            records+=1
    for row in run.get('accepted',[]):
        if bound(row['certificate'])!=row['verification']: raise ValueError('An accepted proof failed replay')
        records+=1
    for row in run.get('exclusions',[]):
        if bound(row['certificate'])!=row['verification']: raise ValueError('An exclusion failed replay')
        records+=1
    if run.get('certificate'):
        if K.verify(run['certificate'])!=run['verification']: raise ValueError('A theorem family failed replay')
        records+=1
    for row in run.get('samples',[]): records+=check_run(row['result'])
    for row in run.get('attempts',[]): records+=check_run(row['result'])
    return records


def bind_problem(definition,result):
    kind=definition['kind']
    if kind=='rational_recurrence':
        actual=result['goal']
        for key in ('id','variables','transitions','max_degree','max_denominator_degree'):
            if actual[key]!=definition[key]: raise ValueError('Rational program definitions changed')
        for key in ('parameters','guards'):
            if actual.get(key,[])!=definition.get(key,[]): raise ValueError('Rational domain or parameters changed')
        if result['status']!='CERTIFIED_RATIONAL_INVARIANT' or not result['accepted']:
            raise ValueError('A rational task lacks its accepted universal proof')
    elif kind=='inequality':
        if result['statement']!=definition or result['certificate']['statement']!=definition:
            raise ValueError('Inequality task definitions changed')
        expected='CERTIFIED_SHARP_INEQUALITY' if definition.get('optimize') else 'CERTIFIED_POLYNOMIAL_INEQUALITY'
        if result['status']!=expected or result['verification']['status']!=expected:
            raise ValueError('The inequality predicate or sharpness obligation changed')
    elif kind=='inequality_atlas':
        cert=result['certificate']; statement=cert['statement']
        for key in ('id','variables','polynomial','reference'):
            if statement[key]!=definition[key]: raise ValueError('Atlas target changed')
        if cert['parameter']!=definition['parameter'] or cert['parameter_range']!=definition['parameter_range']:
            raise ValueError('Atlas parameter scope changed')
        if result['status']!='CERTIFIED_SHARP_PARAMETER_ATLAS': raise ValueError('Atlas obligation not achieved')
    else: raise ValueError('Unknown declared benchmark program')


def replay(directory):
    directory=Path(directory)
    contract=json.loads((directory/'contract.json').read_text())
    results=json.loads((directory/'results.json').read_text())
    bare={k:v for k,v in contract.items() if k!='hash'}
    h=hashlib.sha256(json.dumps(bare,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
    if h!=contract['hash'] or h!=results['contract_hash']: raise ValueError('Contract hash mismatch')
    if len(results['legacy'])!=len(contract['legacy_cases']) or len(results['frontier'])!=len(contract['new_programs']): raise ValueError('Declared benchmark scope changed')
    records=0
    for definition,row in zip(contract['legacy_cases'],results['legacy']):
        if row['goal']!=definition['goal'] or row['expected_positive']!=definition['expected_positive']: raise ValueError('Legacy goal mismatch')
        expected='CERTIFIED_INVARIANT' if definition['expected_positive'] else 'CERTIFIED_TEMPLATE_EXCLUSION'
        if row['predecessor']['status']!=expected or row['noether_forge']['status']!=expected: raise ValueError('Legacy acceptance scope changed')
        records+=check_run(row['predecessor'])+check_run(row['noether_forge'])
    for definition,row in zip(contract['new_programs'],results['frontier']):
        if definition!=row['problem'] or not row['result']['status'].startswith('CERTIFIED_'): raise ValueError('Frontier program mismatch or missing proof')
        bind_problem(definition,row['result'])
        records+=check_run(row['result'])
    novelty=results['algebraic_novelty_control']['noether_forge']
    if K.verify(novelty['certificate'])!=novelty['verification'] or novelty['status']!='DERIVED_FROM_KNOWN_ALGEBRA': raise ValueError('Algebraic consequence did not replay')
    return {'status':'INDEPENDENT_FRONTIER_REPLAY_PASSED','legacy_cases':len(results['legacy']),'expanded_programs':len(results['frontier']),'mathematical_evidence_records':records+1,'historically_novel_results_verified':0}


if __name__=='__main__':
    print(json.dumps(replay(sys.argv[1]),indent=2))
