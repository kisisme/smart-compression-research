"""Document validation and exact-decimal math examples, not a production scorer."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT/'research_log/usage_objective_design_v1.md'
SPEC = ROOT/'research_log/usage_objective_spec_v1.json'
OUT = ROOT/'research_log/usage_objective_design_checks_20261030.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    check(not OUT.exists(), 'Existing evidence must not be overwritten')
    prior_root = ROOT/'data/results/pilot_tradeoff_20261029_01'
    prior = json.loads((prior_root/'summary.json').read_bytes())
    verification = json.loads((prior_root/'verification.json').read_bytes())
    publication = json.loads((prior_root/'publication.json').read_bytes())
    protected = dict(prior['protected_before_sha256'])
    protected.update(prior['source_sha256'])
    protected.update(publication['artifacts_sha256'])
    protected.update({f'data/results/pilot_tradeoff_20261029_01/{k}':v for k,v in prior['output_sha256'].items()})
    check(digest(prior_root/'summary.json')==verification['summary_sha256'],'Prior summary changed')
    check(digest(ROOT/'research_log/verify_pilot_tradeoffs_20261029.py')==verification['verifier_sha256'],'Prior verifier changed')
    check(digest(ROOT/'research_log/publish_pilot_tradeoffs_20261029.py')==publication['publisher_sha256'],'Prior publisher changed')
    for relative in ('data/results/pilot_tradeoff_20261029_01/summary.json',
                     'data/results/pilot_tradeoff_20261029_01/verification.json',
                     'data/results/pilot_tradeoff_20261029_01/publication.json',
                     'research_log/verify_pilot_tradeoffs_20261029.py',
                     'research_log/publish_pilot_tradeoffs_20261029.py',
                     'research_log/memory_reference_indicator_decision_20261023.md'):
        protected.setdefault(relative,digest(ROOT/relative))
    for relative,value in protected.items():
        check(digest(ROOT/relative)==value,'Protected file changed: '+relative)
    spec = json.loads(SPEC.read_bytes())
    config = json.loads((ROOT/'config/experiment_config.json').read_bytes())
    check(config['memory']['status']=='validation_only','Memory policy changed')
    check(spec['status']=='candidate_design_only' and spec['official_replacement'] is False,'Design falsely marked official')
    check(set(spec['profiles'])==set(config['selection_modes']),'Mode coverage differs')
    check(all(profile[k] is None for profile in spec['profiles'].values() for k in ('H','N','k_s','k_c','k_d')),
          'Unfounded operational defaults introduced')
    for weights in config['selection_modes'].values():
        check(set(weights)=={'compression_ratio','compression_time','decompression_time'},'Official score changed')
    doc = DOC.read_text(encoding='utf-8')
    targets = [(DOC.parent/t).resolve() for t in re.findall(r'\]\(([^)]+)\)',doc)]
    check(all(p.exists() or p==OUT for p in targets),'Broken document link')
    check('주후보' in doc and '공식 채택' in doc and 'null' in doc,'Missing status/context explanation')
    design_sources = {p.relative_to(ROOT).as_posix():digest(p) for p in (DOC,SPEC,Path(__file__))}

    # These anonymous A/B numbers are deliberately artificial, with no codec names.
    D = Decimal
    candidates = {'A':{'B':D(100),'Tc':D(20),'Td':D(8)},
                  'B':{'B':D(140),'Tc':D(5),'Td':D(2)}}
    def costs(H,N,ks=D(1),kc=D(1),kd=D(1),data=candidates):
        return {name:ks*H*r['B']+kc*r['Tc']+kd*N*r['Td'] for name,r in data.items()}
    cases = []
    for H,N,expected in ((D(1),D(0),'A'),(D(1),D(10),'B'),(D(5),D(10),'A'),
                         (D(0),D(0),'B'),(D('.375'),D(0),'tie'),(D('.975'),D(4),'tie')):
        values = costs(H,N)
        actual = 'tie' if values['A']==values['B'] else min(values,key=values.__getitem__)
        check(actual==expected,'Cost ordering mismatch')
        delta_B = candidates['B']['B']-candidates['A']['B']
        delta_c = candidates['A']['Tc']-candidates['B']['Tc']
        delta_d = candidates['A']['Td']-candidates['B']['Td']
        h_star = (delta_c+N*delta_d)/delta_B
        check((values['A']<values['B'])==(H>h_star),'Retention boundary mismatch')
        check(values['A']-values['B']==-H*delta_B+delta_c+N*delta_d,'Difference equation mismatch')
        cases.append({'H':str(H),'N':str(N),'costs':{k:str(v) for k,v in values.items()},
                      'H_star':str(h_star),'result':actual})
    baseline = costs(D(1),D(10))
    scaled = costs(D(1),D(10),ks=D('3.5'),kc=D('3.5'),kd=D('3.5'))
    check(all(scaled[k]==baseline[k]*D('3.5') for k in baseline),'Coefficient scale mismatch')
    kib_data = {name:{**r,'B':r['B']/D(1024)} for name,r in candidates.items()}
    check(costs(D(1),D(10),ks=D(1024),data=kib_data)==baseline,'Byte/KiB unit conversion mismatch')
    # A negative retention boundary: smaller A is also faster to compress here.
    faster_small = {'A':{**candidates['A'],'Tc':D(1),'Td':D(1)},'B':candidates['B']}
    check(costs(D(0),D(0),data=faster_small)['A']<costs(D(0),D(0),data=faster_small)['B'],
          'Negative-boundary case mismatch')
    # Restoration crossover, chosen to have an exact finite decimal boundary.
    n_star = (D('.975')*D(40)-D(15))/D(6)
    check(n_star==D(4) and costs(D('.975'),D(3))['A']<costs(D('.975'),D(3))['B']
          and costs(D('.975'),D(5))['A']>costs(D('.975'),D(5))['B'],'Restoration boundary mismatch')
    constraints = []
    for tc,td,expected in ((D(25),D(10),'A'),(D(25),D(3),'B'),(D(1),D(1),None),(D(20),D(8),'A')):
        feasible = [name for name,r in candidates.items() if r['Tc']<=tc and r['Td']<=td]
        chosen = min(feasible,key=lambda name:candidates[name]['B']) if feasible else None
        check(chosen==expected,'Constraint/empty-set/inclusive-boundary mismatch')
        constraints.append({'tau_c':str(tc),'tau_d':str(td),'feasible':feasible,'chosen':chosen,
                            'status':'selected' if feasible else 'constraint_unsatisfied'})
    after = {relative:digest(ROOT/relative) for relative in protected}
    check(after==protected,'Protected inputs changed during validation')
    evidence = {'status':'candidate_design_and_synthetic_math_checked',
                'created_at_utc':datetime.now(timezone.utc).isoformat(),
                'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'design_source_sha256':design_sources,'protected_before_sha256':protected,
                'protected_after_sha256':after,'protected_file_count':len(protected),
                'local_link_count':len(targets),'document_links_exist_after_publication':True,
                'fixture_kind':'anonymous artificial numbers, not measured research data',
                'fixture_candidates':{k:{m:str(v) for m,v in r.items()} for k,r in candidates.items()},
                'fixture_policy_coefficients':{'k_s':'1 point/(byte day)','k_c':'1 point/ms','k_d':'1 point/ms'},
                'lifetime_cost_cases':cases,'deadline_cases':constraints,
                'additional_checks':['positive coefficient scale invariance','byte/KiB coefficient conversion',
                                     'negative retention boundary','restoration count crossover'],
                'operational_coefficients_selected':False,'official_definition_changed':False,
                'new_codec_measurement':False,'memory_measured_or_scored':False,
                'new_model_training_or_evaluation':False,'unit_test_suite_executed':False,
                'next_task':'Separate pure candidate scorer implementation and artificial fixture tests; no official switch.'}
    with OUT.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(evidence,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write('\n')
    check(all(p.exists() for p in targets),'Published link missing')
    print(json.dumps({'status':evidence['status'],'protected_file_count':len(protected),
                      'cost_examples':len(cases),'deadline_examples':len(constraints),
                      'local_links':len(targets),'git_head':evidence['git_head']},ensure_ascii=False))


if __name__=='__main__':
    main()
