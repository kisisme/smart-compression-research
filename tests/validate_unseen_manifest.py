"""Opt-in CLI smoke using explicitly artificial files, never unseen research data."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tests.test_unseen_manifest import fixture


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record",type=Path,required=True)
    args = parser.parse_args()
    if args.record.exists(): parser.error("Record exists; choose a new path")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT/"data/temp"/("unseen_manifest_validation_"+stamp)
    output.mkdir()
    previous = json.loads((ROOT/"research_log/unseen_evaluation_design_v1_checks.json").read_text(encoding="utf-8"))
    before = {n:digest(ROOT/n) for n in previous["protected_before"]}
    assert before==previous["protected_before"]
    source_names = ("src/unseen_manifest.py","tests/test_unseen_manifest.py","tests/validate_unseen_manifest.py")
    source_before = {n:digest(ROOT/n) for n in source_names}
    root,inventory_path,inventory = fixture(output)
    original = {str(p.relative_to(root)):digest(p) for p in root.rglob("*") if p.is_file()}
    environment = {**os.environ,"PYTHONIOENCODING":"utf-8"}
    record = dict(kind="Artificial CLI/contract validation; not real corpus collection or research evaluation",
        started_at_utc=stamp,output_dir=str(output),source_sha256=source_before,protected_before=before,
        git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        calls=[],checks={},fixture_file_sha256=original,
        gui_status="Not run; live node_repl probe still returned failed to start Node runtime (os error 3)")
    def call(*arguments,expected=0):
        command = [sys.executable,"-B","-m","src.unseen_manifest",*map(str,arguments)]
        completed = subprocess.run(command,cwd=ROOT,env=environment,capture_output=True)
        result = dict(command=command,return_code=completed.returncode,
                      stdout=completed.stdout.decode("utf-8"),stderr=completed.stderr.decode("utf-8"))
        record["calls"].append(result)
        assert completed.returncode==expected,result
        return json.loads(result["stdout"]) if expected==0 and arguments[0]!="--help" else None
    def selection(path,draft,content=inventory):
        value = dict(selection_version=1,corpus_id=content["corpus_id"],draft_manifest_sha256=draft["manifest_sha256"],
                     candidate_ids=[r["candidate_id"] for r in content["candidates"]])
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    try:
        call("--help")
        draft = call("draft","--root",root,"--inventory",inventory_path,"--output-dir",output/"draft")
        chosen = output/"selection.json"
        selection(chosen,draft)
        frozen = call("freeze","--draft-dir",output/"draft","--selection",chosen,"--output-dir",output/"frozen")
        audited = call("audit","--manifest-dir",output/"frozen","--expected-sha256",frozen["manifest_sha256"])
        assert audited["verified"] and audited["data_kind"]=="test_fixture" and audited["evaluation_ready"] is False
        manifest = json.loads((output/"frozen/manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["selected_ids"])==60
        assert all(r["selection_status"]=="selected" for r in manifest["candidates"])
        assert Counter(r["format"] for r in manifest["candidates"])=={f:10 for f in ("text","csv","json","python","log","binary")}
        assert len({r["origin_group_id"] for r in manifest["candidates"]})>=12
        assert max(Counter(r["origin_group_id"] for r in manifest["candidates"]).values())<=5
        for row in manifest["candidates"]:
            path = root/row["relative_path"]
            assert digest(path)==row["input_sha256"] and path.stat().st_size==row["original_size"]
            assert row["sample_id"]=="uf_"+digest(path)
        assert all(digest(output/"frozen"/n)==v for n,v in manifest["artifact_sha256"].items())
        frozen_bytes = {p.name:p.read_bytes() for p in (output/"frozen").iterdir()}
        record["frozen_artifacts_utf8"] = {n:b.decode("utf-8") for n,b in frozen_bytes.items()}
        record["draft_manifest_utf8"] = (output/"draft/manifest.json").read_text(encoding="utf-8")
        record["checks"]["independent_hash_schema_quota_and_fixture_separation"] = True
        call("freeze","--draft-dir",output/"draft","--selection",chosen,"--output-dir",output/"frozen",expected=1)
        call("audit","--manifest-dir",output/"frozen","--expected-sha256","0"*64,expected=1)
        assert frozen_bytes=={p.name:p.read_bytes() for p in (output/"frozen").iterdir()}
        record["checks"]["existing_output_and_wrong_digest_rejected_without_change"] = True

        pending = json.loads(inventory_path.read_text(encoding="utf-8"))
        pending["candidates"][0]["rights_review_status"] = "pending"
        pending_path = output/"pending_inventory.json"
        pending_path.write_text(json.dumps(pending,ensure_ascii=False),encoding="utf-8")
        pending_draft = call("draft","--root",root,"--inventory",pending_path,"--output-dir",output/"pending_draft")
        selection(output/"pending_selection.json",pending_draft,pending)
        call("freeze","--draft-dir",output/"pending_draft","--selection",output/"pending_selection.json",
             "--output-dir",output/"not_published",expected=1)
        assert not (output/"not_published").exists()
        record["checks"]["pending_review_cannot_freeze"] = True

        damaged = output/"deliberately_damaged_package_copy"
        shutil.copytree(output/"frozen",damaged)
        (damaged/"selection_snapshot.json").write_bytes(b"{}")
        call("audit","--manifest-dir",damaged,"--expected-sha256",frozen["manifest_sha256"],expected=1)
        record["checks"]["damaged_copy_rejected"] = True
        assert original=={str(p.relative_to(root)):digest(p) for p in root.rglob("*") if p.is_file()}
        record["checks"]["fixture_input_bytes_unchanged"] = True
        command = [sys.executable,"-B","-m","unittest","discover","-s","tests","-p","test_unseen_manifest.py","-v"]
        tests = subprocess.run(command,cwd=ROOT,env=environment,capture_output=True)
        record["tests"] = dict(command=command,return_code=tests.returncode,
            stdout=tests.stdout.decode("utf-8"),stderr=tests.stderr.decode("utf-8"))
        assert tests.returncode==0,record["tests"]
        record["protected_after"] = {n:digest(ROOT/n) for n in before}
        assert record["protected_after"]==before
        assert {n:digest(ROOT/n) for n in source_names}==source_before
        record["checks"]["existing_protected_files_and_final_sources_unchanged"] = True
        record["status"] = "completed_artificial_validation"
    except BaseException as exc:
        record["status"] = "validation_failed"
        record["error"] = type(exc).__name__+": "+str(exc)
        raise
    finally:
        with (output/"validation_record.json").open("x",encoding="utf-8") as stream:
            json.dump(record,stream,ensure_ascii=False,allow_nan=False,indent=2)
    record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    with args.record.open("x",encoding="utf-8") as stream:
        json.dump(record,stream,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps(dict(record=str(args.record),output_dir=str(output),status=record["status"],cli_calls=len(record["calls"]))))


if __name__=="__main__":
    main()
