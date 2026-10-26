"""Publish explicit assistant-authored candidate judgments, never infer approval."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
POOL=ROOT/"data/results/real_unseen/real_candidates_20261026_02"
LOCAL=ROOT/"data/temp/unseen_content_review_20261026_01"
OUT=ROOT/"data/results/real_unseen/real_candidate_review_20261026_01"
DECISIONS=ROOT/"research_log/unseen_candidate_decisions_20261026.json"
EXTRA=ROOT/"data/raw/real_unseen/review_evidence_20261026_02"


def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_bytes())
def save(path,obj):
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(obj,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write("\n")


def main():
    if OUT.exists(): raise ValueError("Refusing existing review output")
    decisions=read(DECISIONS)
    inventory=read(POOL/"inventory.json")
    acquisition=read(POOL/"acquisition.json")
    raw=ROOT/acquisition["raw_root"]
    profile=read(LOCAL/"inspection.json")
    assert sha((ROOT/"research_log/inspect_unseen_candidates_20261026.py").read_bytes())==profile["inspector_sha256"]
    original_before=read(LOCAL/"protected_before.json")
    assert original_before==read(LOCAL/"protected_after.json")
    assert all(sha((ROOT/p).read_bytes())==h for p,h in original_before.items())
    before=dict(original_before)
    before.update({p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in EXTRA.rglob("*") if p.is_file()})
    by_id={d["candidate_id"]:d for d in decisions["entries"]}
    assert len(by_id)==len(decisions["entries"])==len(inventory["candidates"])
    assert set(by_id)=={r["candidate_id"] for r in inventory["candidates"]}
    profiles={r["candidate_id"]:r for r in profile["candidates"]}
    assert set(profiles)==set(by_id)
    for d in by_id.values():
        assert d["rights_review_status"]==d["privacy_review_status"]=="approved"
        assert d["rights_basis"].strip() and d["privacy_basis"].strip() and d["origin_review_status"].strip()
    evidence_plan=read(ROOT/"research_log/unseen_review_evidence_plan_20261026.json")
    source_acquisition=read(EXTRA/"acquisition.json")
    for r in source_acquisition["records"]:
        data=(EXTRA/r["relative_path"]).read_bytes()
        assert sha(data)==r["input_sha256"] and len(data)==r["size"]
        assert hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()==r["git_blob_sha1"]
    reviewed_at=datetime.now(timezone.utc).isoformat()
    plan=read(POOL/"collection_plan_snapshot.json")
    gh={f["candidate_id"]:(g,f) for g in plan["github_groups"] for f in g["files"]}
    root_notices={"cldr":"prior/notices/cldr/LICENSE","curl":"prior/notices/curl/COPYING","git":"prior/notices/git/COPYING",
                  "numpy":"prior/notices/numpy/LICENSE.txt","pandas":"prior/notices/pandas/LICENSE","natural_earth":"prior/notices/natural_earth/LICENSE.md"}
    revised,records,obligations=[],[],[]
    for old in inventory["candidates"]:
        cid=old["candidate_id"]
        d=by_id[cid]
        p=profiles[cid]
        data=(raw/old["relative_path"]).read_bytes()
        assert sha(data)==old["input_sha256"]==p["input_sha256"]
        notice_paths=[]
        group=old["origin_group_id"]
        if group in root_notices:
            notice_paths.append(raw/root_notices[group])
        elif cid in gh:
            g,f=gh[cid]
            notice_paths.append(raw/"notices"/group/f["license_path"])
            if cid=="vscode_01": notice_paths.append(raw/"notices/vscode/LICENSE.txt")
        else:
            assert group.startswith("uci_")
            notice_paths.extend([raw/"notices"/group/"source_page.html",raw/"notices/CC-BY-4.0/legalcode.en.html"])
        new=dict(old,rights_review_status=d["rights_review_status"],privacy_review_status=d["privacy_review_status"],reviewed_at_utc=reviewed_at)
        if cid=="numpy_04":
            special=decisions["special_license_update"]
            new["license_id"]=special["license_id"]
            new["license_evidence"]=old["license_evidence"]+" ; https://github.com/python/cpython/blob/29360893df0931703cb2fe0c0fbc0fc963e64ead/LICENSE"
            notice_paths.append(ROOT/special["supplemental_license"])
            assert b"PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2" in notice_paths[-1].read_bytes()
        revised.append(new)
        notice_refs=[dict(path=path.relative_to(ROOT).as_posix(),input_sha256=sha(path.read_bytes())) for path in notice_paths]
        obligations.append(dict(candidate_id=cid,carry_notices=notice_refs,retain_original_bytes_and_existing_notices=True,
                                no_endorsement=True,additional_citation_groups=[c for c in decisions["additional_citations"] if group in c["groups"]],
                                adaptation_summary=decisions["special_license_update"]["adaptation_summary"] if cid=="numpy_04" else None))
        clean=dict(d,input_sha256=old["input_sha256"],format=old["format"],origin_group_id=group,
                   source_locator=old["source_locator"],source_version=old["source_version"],reviewed_at_utc=reviewed_at,
                   license_id=new["license_id"],license_evidence=new["license_evidence"],notice_refs=notice_refs,
                   context_locations={k:[v["line"] for v in values] for k,values in p.get("contexts",{}).items()},
                   structured_review_method={"csv":"Every cell parsed; all nonnumeric values and date representations reviewed against the published observation schema",
                      "json":"Full JSON traversal, manifest/localization role and flagged/schema/telemetry contexts reviewed",
                      "python":"Whole-source AST/token/string/comment scan with source-context review; no code execution",
                      "text":"Whole document scan and attribution/example/reference contexts reviewed",
                      "log":"Every MLLOG record and all string values reviewed; numeric benchmark values not used for candidate selection",
                      "binary":"Every shapefile record or all TrueType name-table records reviewed; complete structural parsing"}[old["format"]])
        records.append(clean)
    for relation in decisions["relationships"]:
        assert set(relation["candidate_ids"])<=set(by_id)
    OUT.mkdir(parents=True)
    save(OUT/"protected_before.json",before)
    save(OUT/"decisions_snapshot.json",decisions)
    save(OUT/"inventory.json",dict(inventory_version=1,corpus_id=decisions["reviewed_corpus_id"],data_kind="research_candidate",candidates=revised))
    save(OUT/"candidate_review.json",dict(review_version=1,reviewed_at_utc=reviewed_at,policy=decisions["policy"],candidates=records,
        base_inventory_sha256=sha((POOL/"inventory.json").read_bytes()),inspection_sha256=sha((LOCAL/"inspection.json").read_bytes()),
        inspection_material_path=LOCAL.relative_to(ROOT).as_posix(),raw_root=raw.relative_to(ROOT).as_posix(),
        publisher_sha256=sha(Path(__file__).read_bytes()),inspector_sha256=profile["inspector_sha256"],
        decision_sha256=sha(DECISIONS.read_bytes()),evaluation_ready=False,unseen_overlap_audit="not_performed",selected_files=0))
    save(OUT/"relationships.json",dict(relationships=decisions["relationships"],supplementary_source_view=decisions["supplementary_source_view"],
         candidate_derivative_of="No directed relation between collected candidate files established. Undirected relationships and external lineage are explicit here; no direction is invented.",
         group_semantics="Whole repositories/original observation collections; not statistically independent samples; no new training or split."))
    save(OUT/"usage_requirements.json",dict(scope=decisions["policy"]["scope"],requirements=obligations,
         accompany_future_corpus_or_distribution=True,original_font_names_unchanged=True,original_source_bytes_unchanged=True,
         preserve_psf_adaptation_summary_for_numpy_04=True))
    save(OUT/"source_evidence.json",dict(plan=evidence_plan,acquisition=source_acquisition,raw_evidence_root=EXTRA.relative_to(ROOT).as_posix(),
         limitations=["Official Python 3.2 docs endpoint was unavailable; pinned CPython v3.2 LICENSE/source were retrieved instead.",
                      "Publisher article endpoint returned HTTP 403; Wilt title/authors/pages were checked on the publisher issue page, not the full paper.",
                      "Initial restricted evidence download was refused before any file was downloaded; empty review_evidence_20261026_01 path retained. Approved retry used review_evidence_20261026_02."]))
    command=[sys.executable,"-B","-m","src.unseen_manifest","draft","--root",str(raw),"--inventory",str(OUT/"inventory.json"),"--output-dir",str(OUT/"draft")]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    save(OUT/"draft_cli.json",dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
    after={p:sha((ROOT/p).read_bytes()) for p in before}
    assert before==after
    save(OUT/"protected_after.json",after)
    save(OUT/"review_summary.json",dict(status="file_level_review_completed",reviewed_at_utc=reviewed_at,
        execution_git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        reviewed_candidates=len(revised),rights_approved=sum(r["rights_review_status"]=="approved" for r in revised),
        privacy_approved=sum(r["privacy_review_status"]=="approved" for r in revised),
        by_format=dict(Counter(r["format"] for r in revised)),origin_groups=len({r["origin_group_id"] for r in revised}),
        original_protected_files_unchanged=len(original_before),protected_with_supplemental_evidence=len(before),
        input_bytes_unchanged=True,selected_files=0,evaluation_ready=False,unseen_overlap_audit="not_performed",draft_returncode=result.returncode,
        research_runtime_executed=False,method=decisions["policy"]["method"]))
    print(json.dumps(dict(reviewed_candidates=len(revised),rights_approved=sum(r["rights_review_status"]=="approved" for r in revised),
                          privacy_approved=sum(r["privacy_review_status"]=="approved" for r in revised),draft_returncode=result.returncode,
                          protected_unchanged=before==after,output=OUT.relative_to(ROOT).as_posix())))
    if result.returncode: raise SystemExit(result.returncode)


if __name__=="__main__": main()
