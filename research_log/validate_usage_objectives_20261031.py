"""Run fixture tests and check new functions against prior synthetic math examples."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'research_log/usage_objectives_validation_20261031.json'
sys.path.insert(0,str(ROOT))
from src.usage_objectives import LifetimePolicy, evaluate_lifetime_cost, select_under_deadlines


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition,message):
    if not condition:
        raise ValueError(message)


def main():
    require(not OUT.exists(),'Existing validation must not be overwritten')
    started = datetime.now(timezone.utc).isoformat()
    previous_path = ROOT/'research_log/usage_objective_design_checks_20261030.json'
    previous = json.loads(previous_path.read_bytes())
    protected = {**previous['protected_after_sha256'],**previous['design_source_sha256'],
                 previous_path.relative_to(ROOT).as_posix():sha(previous_path)}
    for name,value in protected.items():
        require(sha(ROOT/name)==value,'Previous protected input changed: '+name)
    sources = {name:sha(ROOT/name) for name in (
        'src/usage_objectives.py','tests/test_usage_objectives.py','research_log/usage_objectives.md',
        'research_log/validate_usage_objectives_20261031.py')}
    environment = os.environ.copy()
    environment['PYTHONIOENCODING'] = 'utf-8'
    command = [sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_usage_objectives.py','-v']
    tests = subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,timeout=90)
    stdout,stderr = tests.stdout.decode('utf-8'),tests.stderr.decode('utf-8')
    match = re.search(r'Ran (\d+) tests in ([0-9.]+)s',stderr)
    test_record = {'command':command,'returncode':tests.returncode,'stdout':stdout,'stderr':stderr,
                   'count':int(match[1]) if match else None,'seconds':float(match[2]) if match else None}
    evidence = {'status':'validation_started','started_at_utc':started,
                'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'git_status':subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
                'python_version':platform.python_version(),'platform':platform.platform(),
                'tests':test_record,'source_sha256':sources,'protected_before_sha256':protected,
                'data_kind':'synthetic_fixture_only','new_codec_measurement':False,
                'memory_measured_or_scored':False,'official_score_changed':False,
                'new_model_training_or_evaluation':False,'production_integration':False}
    try:
        require(tests.returncode==0 and match is not None and stderr.rstrip().endswith('OK'),'Dedicated fixture tests failed')
        # Reuse the previous design's anonymous examples. Extra codecs below are
        # artificial dominated candidates required by the four-codec input contract.
        old_candidates = previous['fixture_candidates']
        mapping = {'A':'gzip','B':'bz2'}
        rows = []
        for old_name,algorithm in mapping.items():
            r = old_candidates[old_name]
            rows.append({'sample_id':'artificial_usage_validation','algorithm':algorithm,'original_size':1000,
                         'compressed_size':int(r['B']),'compression_time_ms':r['Tc'],
                         'decompression_time_ms':r['Td'],'verified':True,'status':'ok'})
        for algorithm,size,time in (('lzma',500,100),('zstd',800,200)):
            rows.append({'sample_id':'artificial_usage_validation','algorithm':algorithm,'original_size':1000,
                         'compressed_size':size,'compression_time_ms':time,'decompression_time_ms':time,
                         'verified':True,'status':'ok'})
        cost_cases,deadline_cases = [],[]
        for case in previous['lifetime_cost_cases']:
            p = LifetimePolicy(retention_days=case['H'],expected_restorations=case['N'],
                storage_cost_per_byte_day=1,compression_cost_per_ms=1,decompression_cost_per_ms=1,
                profile_kind='time_only' if float(case['H'])==0 else 'storage')
            result = evaluate_lifetime_cost(rows,policy=p)
            for name,expected in case['costs'].items():
                require(math.isclose(result['values'][mapping[name]],float(expected),rel_tol=1e-14),'Prior exact-decimal cost mismatch')
            if case['result']=='tie':
                require(result['tied_algorithms']==['gzip','bz2'] and result['selected_algorithm']=='gzip','Tie contract mismatch')
            else:
                require(result['selected_algorithm']==mapping[case['result']],'Expected winner mismatch')
            cost_cases.append({'previous_anonymous_example':case,'actual':result})
        for case in previous['deadline_cases']:
            result = select_under_deadlines(rows,compression_limit_ms=case['tau_c'],decompression_limit_ms=case['tau_d'])
            expected = mapping[case['chosen']] if case['chosen'] is not None else None
            require(result['selected_algorithm']==expected and result['status']==case['status'],'Deadline example mismatch')
            require(result['feasible_algorithms']==[mapping[a] for a in case['feasible']],'Deadline feasible-set mismatch')
            deadline_cases.append({'previous_anonymous_example':case,'actual':result})
        doc = ROOT/'research_log/usage_objectives.md'
        targets = [(doc.parent/t).resolve() for t in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8'))]
        require(all(p.exists() or p==OUT for p in targets),'Broken implementation documentation link')
        after = {name:sha(ROOT/name) for name in protected}
        require(after==protected,'Protected files changed during tests')
        require(all(sha(ROOT/name)==value for name,value in sources.items()),'Implementation source changed during validation')
        evidence.update(status='fixture_tests_and_design_examples_verified',fixture_rows=rows,
                        lifetime_cases=cost_cases,deadline_cases=deadline_cases,
                        protected_after_sha256=after,protected_file_count=len(protected),
                        local_link_count=len(targets),completed_at_utc=datetime.now(timezone.utc).isoformat(),
                        limitations=['All codec-named rows are artificial fixtures, not research measurements.',
                                     'Only the dedicated test suite ran; no full repository suite or empirical benchmark.',
                                     'Operational policy values remain unset; no official labels, models or CLI/GUI changes.',
                                     'Binary64 costs can round very close real-valued results; no epsilon-based merging.'])
    except Exception as exc:
        evidence.update(status='failed',error=repr(exc),completed_at_utc=datetime.now(timezone.utc).isoformat())
        raise
    finally:
        with OUT.open('x',encoding='utf-8',newline='\n') as stream:
            json.dump(evidence,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write('\n')
    require(all(p.exists() for p in targets),'Published evidence link missing')
    print(json.dumps({'status':evidence['status'],'tests':test_record['count'],'seconds':test_record['seconds'],
                      'cost_examples':len(cost_cases),'deadline_examples':len(deadline_cases),
                      'protected_files':len(protected),'links':len(targets)},ensure_ascii=False))


if __name__=='__main__':
    main()
