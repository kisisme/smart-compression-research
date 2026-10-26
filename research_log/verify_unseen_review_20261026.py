"""Independent verification of review decisions, unchanged inputs and new draft."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"data/results/real_unseen/real_candidate_review_20261026_01"
BASE=ROOT/"data/results/real_unseen/real_candidates_20261026_02"


def read(p): return json.loads(p.read_bytes())
def sha(b): return hashlib.sha256(b).hexdigest()


def main():
    old=read(BASE/"inventory.json")
    inv=read(OUT/"inventory.json")
    review=read(OUT/"candidate_review.json")
    summary=read(OUT/"review_summary.json")
    manifest=read(OUT/"draft/manifest.json")
    decisions=read(OUT/"decisions_snapshot.json")
    usages=read(OUT/"usage_requirements.json")
    sources=read(OUT/"source_evidence.json")
    before,after=read(OUT/"protected_before.json"),read(OUT/"protected_after.json")
    assert before==after and all(sha((ROOT/p).read_bytes())==h for p,h in before.items())
    assert sha((BASE/"inventory.json").read_bytes())==review["base_inventory_sha256"]
    assert sha((ROOT/"research_log/unseen_candidate_decisions_20261026.json").read_bytes())==review["decision_sha256"]
    assert read(ROOT/"research_log/unseen_candidate_decisions_20261026.json")==decisions
    assert sha((ROOT/"research_log/inspect_unseen_candidates_20261026.py").read_bytes())==review["inspector_sha256"]
    assert sha((ROOT/"research_log/publish_unseen_review_20261026.py").read_bytes())==review["publisher_sha256"]
    assert not review["evaluation_ready"] and review["selected_files"]==0
    assert not summary["evaluation_ready"] and not summary["research_runtime_executed"]
    assert review["unseen_overlap_audit"]==manifest["unseen_overlap_audit"]=="not_performed"
    assert manifest["status"]=="draft" and not manifest["evaluation_ready"] and manifest["selected_ids"]==[]
    assert manifest["provenance_review"]=="declared_metadata_only"  # source/rights judgments live in separate review evidence
    assert manifest["group_issues"]==[] and read(OUT/"draft_cli.json")["returncode"]==0
    assert (OUT/"inventory.json").read_bytes()==(OUT/"draft/inventory_snapshot.json").read_bytes()
    assert manifest["source_sha256"]==sha((ROOT/"src/unseen_manifest.py").read_bytes())
    for p,h in manifest["artifact_sha256"].items(): assert sha((OUT/"draft"/p).read_bytes())==h
    old_by_id={r["candidate_id"]:r for r in old["candidates"]}
    new_by_id={r["candidate_id"]:r for r in inv["candidates"]}
    review_by_id={r["candidate_id"]:r for r in review["candidates"]}
    decisions_by_id={r["candidate_id"]:r for r in decisions["entries"]}
    manifest_by_id={r["candidate_id"]:r for r in manifest["candidates"]}
    usage_by_id={r["candidate_id"]:r for r in usages["requirements"]}
    assert len(new_by_id)==len(inv["candidates"])==60
    assert set(new_by_id)==set(old_by_id)==set(review_by_id)==set(decisions_by_id)==set(manifest_by_id)==set(usage_by_id)
    raw=ROOT/review["raw_root"]
    hashes=[]
    for cid,row in new_by_id.items():
        original=old_by_id[cid]
        allowed={"rights_review_status","privacy_review_status","reviewed_at_utc"}
        if cid=="numpy_04": allowed|={"license_id","license_evidence"}
        assert set(row)==set(original)
        assert all(row[k]==v for k,v in original.items() if k not in allowed)
        assert original["rights_review_status"]==original["privacy_review_status"]=="pending"
        assert row["rights_review_status"]==row["privacy_review_status"]=="approved"
        assert row["reviewed_at_utc"]==review["reviewed_at_utc"]
        r,d,m=review_by_id[cid],decisions_by_id[cid],manifest_by_id[cid]
        assert all(r[k]==v for k,v in d.items())
        assert all(m[k]==v for k,v in row.items())
        assert m["issues"]==[] and m["selection_status"]=="candidate" and m["exact_duplicate_of"] is None
        data=(raw/row["relative_path"]).read_bytes()
        assert sha(data)==row["input_sha256"]==original["input_sha256"]==r["input_sha256"]
        assert len(data)==row["original_size"] and 16384<=len(data)<=1048576
        hashes.append(sha(data))
        assert r["rights_basis"].strip() and r["privacy_basis"].strip() and r["structured_review_method"].strip()
        assert r["notice_refs"]==usage_by_id[cid]["carry_notices"] and r["notice_refs"]
        for notice in r["notice_refs"]: assert sha((ROOT/notice["path"]).read_bytes())==notice["input_sha256"]
    assert len(hashes)==len(set(hashes))
    assert new_by_id["numpy_04"]["license_id"]=="BSD-3-Clause AND PSF-2.0"
    assert usage_by_id["numpy_04"]["adaptation_summary"]
    extra=ROOT/sources["raw_evidence_root"]
    for record in sources["acquisition"]["records"]:
        data=(extra/record["relative_path"]).read_bytes()
        assert sha(data)==record["input_sha256"] and len(data)==record["size"]
        assert hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()==record["git_blob_sha1"]
    assert read(OUT/"relationships.json")["relationships"]==decisions["relationships"]
    assert all(set(r["candidate_ids"])<=set(new_by_id) for r in decisions["relationships"])
    groups=Counter(r["origin_group_id"] for r in inv["candidates"])
    formats=Counter(r["format"] for r in inv["candidates"])
    assert len(formats)==6 and set(formats.values())=={10} and len(groups)==18 and max(groups.values())<=5
    assert all(len({r["origin_group_id"] for r in inv["candidates"] if r["format"]==fmt})>=2 for fmt in formats)
    ignored=subprocess.run(["git","check-ignore","--stdin"],cwd=ROOT,text=True,capture_output=True,
                           input="\n".join(p.relative_to(ROOT).as_posix() for p in extra.rglob("*") if p.is_file())+"\n")
    assert ignored.returncode==0 and len(ignored.stdout.splitlines())==len([p for p in extra.rglob("*") if p.is_file()])
    result=dict(status="review_decisions_inputs_notices_and_draft_verified",verified_at_utc=datetime.now(timezone.utc).isoformat(),
                execution_git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                verifier_sha256=sha(Path(__file__).read_bytes()),reviewed_candidates=len(new_by_id),rights_approved=60,privacy_approved=60,
                by_format=dict(formats),origin_groups=len(groups),original_inputs_unchanged=60,
                original_inspection_protected_files_unchanged=summary["original_protected_files_unchanged"],
                protected_with_supplemental_evidence_unchanged=len(before),exact_duplicate_candidates=0,
                supplemental_notice_candidate="numpy_04",license_metadata_changed_candidates=[cid for cid in new_by_id if new_by_id[cid]["license_id"]!=old_by_id[cid]["license_id"]],
                relationship_records=len(decisions["relationships"]),selected_files=0,evaluation_ready=False,
                unseen_overlap_audit="not_performed",corpus_frozen=False,research_runtime_executed=False,
                judgment_scope=decisions["policy"]["scope"],method=decisions["policy"]["method"],
                verifier_scope="Checks artifact/decision consistency and preservation; does not independently establish legal facts or certify anonymity.")
    with (OUT/"verification.json").open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
        stream.write("\n")
    print(json.dumps(result,ensure_ascii=False))


if __name__=="__main__": main()
