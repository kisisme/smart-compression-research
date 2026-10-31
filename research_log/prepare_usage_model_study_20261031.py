"""Freeze declared study inputs/criteria without features, models or codec work."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.unseen_manifest import freeze_manifest, audit_manifest

PLAN=ROOT/'research_log/usage_model_study_plan_20261031.json'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok: raise ValueError(message)
def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False); stream.write('\n')


def main():
    plan=json.loads(PLAN.read_bytes()); out=ROOT/plan['output_root']
    require(not out.exists(),'Existing study must not be overwritten')
    out.mkdir(parents=True,exist_ok=False)
    try:
        review=ROOT/plan['corpus']['review_root']; overlap=ROOT/plan['corpus']['overlap_root']
        prior=json.loads((ROOT/'data/results/usage_scenarios_20261031_01/summary.json').read_bytes())
        protected={**json.loads((review/'protected_after.json').read_bytes()),**prior['protected_after_sha256']}
        require(not {'research_progress.md','.gitattributes'}&set(protected),'Unexpected mutable status document in protected map')
        for name,value in protected.items(): require(sha(ROOT/name)==value,'Protected input changed: '+name)
        require(sha(ROOT/plan['scenario_freeze'])==plan['scenario_freeze_sha256'],'Scenario definition changed')
        inventory=json.loads((ROOT/plan['corpus']['inventory']).read_bytes())
        overlap_summary=json.loads((overlap/'summary.json').read_bytes())
        require(overlap_summary['inventory_sha256']==sha(ROOT/plan['corpus']['inventory']),'Overlap inventory mismatch')
        require(overlap_summary['candidate_exact_overlaps']==0 and overlap_summary['candidates_checked']==len(inventory['candidates']),
                'Unresolved overlap or coverage')
        for name,value in overlap_summary['artifact_sha256'].items(): require(sha(overlap/name)==value,'Overlap evidence changed: '+name)
        selected=sorted(c['candidate_id'] for c in inventory['candidates'])
        require(len(selected)==len(set(selected))==60,'Expected complete reviewed selection')
        require(all(c['rights_review_status']=='approved' and c['privacy_review_status']=='approved' for c in inventory['candidates']),
                'Review not approved')
        selection={'selection_version':1,'corpus_id':inventory['corpus_id'],
                   'draft_manifest_sha256':sha(ROOT/plan['corpus']['draft']/'manifest.json'),'candidate_ids':selected}
        write(out/'selection.json',selection)
        response=freeze_manifest(ROOT/plan['corpus']['draft'],out/'selection.json',out/'corpus')
        write(out/'corpus_freeze_response.json',response)
        audit=audit_manifest(out/'corpus',response['manifest_sha256']); require(audit['verified'],'Corpus audit failed')
        write(out/'corpus_audit.json',audit)
        evidence=out/'corpus_evidence'; evidence.mkdir()
        for name in ('inventory.json','usage_requirements.json','relationships.json','source_evidence.json','verification.json','review_summary.json'):
            (evidence/name).write_bytes((review/name).read_bytes())
        for name in ('summary.json','candidate_overlap.json','verification.json','reconstruction_evidence.json'):
            (evidence/('overlap_'+name)).write_bytes((overlap/name).read_bytes())
        notice_index=[]; notices=evidence/'notices'; notices.mkdir()
        requirements=json.loads((review/'usage_requirements.json').read_bytes())
        require({r['candidate_id'] for r in requirements['requirements']}==set(selected),'Notice requirements coverage mismatch')
        for row in requirements['requirements']:
            for notice in row['carry_notices']:
                source=ROOT/notice['path']; digest=sha(source)
                require(digest==notice['input_sha256'],'Required notice changed')
                dest=notices/(digest+'.notice')
                if not dest.exists(): dest.write_bytes(source.read_bytes())
                notice_index.append({'candidate_id':row['candidate_id'],'original':notice['path'],
                                     'copy':dest.relative_to(out).as_posix(),'sha256':digest})
        write(evidence/'notice_index.json',notice_index)
        manifest=json.loads((out/'corpus/manifest.json').read_bytes())
        source_paths=[PLAN,Path(__file__),ROOT/'research_log/usage_model_study_design_20261031.md',ROOT/'src/unseen_manifest.py',
                      ROOT/'src/usage_objectives.py',ROOT/'config/experiment_config.json',ROOT/plan['scenario_freeze']]
        after={k:sha(ROOT/k) for k in protected}; require(after==protected,'Protected inputs changed during preparation')
        lock={'status':'criteria_and_corpus_frozen_before_training','created_at_utc':datetime.now(timezone.utc).isoformat(),
              'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'plan':plan,'source_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in source_paths},
              'corpus_manifest_sha256':response['manifest_sha256'],'selected_ids':selected,
              'corpus_sample_count':len(manifest['selected_ids']),'notice_references':len(notice_index),
              'protected_before_sha256':protected,'protected_after_sha256':after,
              'corpus_artifact_sha256':{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file()},
              'eligibility_scope':'Ready for this predeclared local candidate study, subject to manifest/metadata/source fences; not generic evaluation_ready or independence certification.',
              'features_predictions_training_benchmarks_executed':False}
        write(out/'study_lock.json',lock)
        print(json.dumps({'status':lock['status'],'study_lock_sha256':sha(out/'study_lock.json'),
                          'corpus_manifest_sha256':response['manifest_sha256'],'selected':len(selected),
                          'protected_files':len(protected),'notice_references':len(notice_index)},ensure_ascii=False))
    except Exception as exc:
        write(out/'preparation_failed.json',{'status':'failed','error':repr(exc)}); raise


if __name__=='__main__': main()
