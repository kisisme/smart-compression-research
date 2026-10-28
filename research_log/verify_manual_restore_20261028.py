"""Verify saved user-operated GUI restoration, without running a restore again."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"research_log/gui_manual_restore_verified_20261028.json"


def check(ok,message):
    if not ok:
        raise ValueError(message)


def read(path): return json.loads(path.read_bytes())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    check(not OUT.exists(),"Existing verification must not be overwritten")
    plan_path=ROOT/"research_log/gui_manual_qa_plan_20261028.json"
    plan=read(plan_path)
    prior_path=ROOT/"research_log/gui_manual_smart_verified_20261028.json"
    prior=read(prior_path)
    check(digest(plan_path)==prior["plan_sha256"],"Plan changed")
    for rel,value in prior["artifact_sha256"].items():
        check(digest(ROOT/rel)==value,"Previous Smart artifact changed: "+rel)
    original=Path(plan["input_path"])
    package=ROOT/plan["output_paths"]["smart"]
    output=ROOT/plan["output_paths"]["restore"]
    manifest_path=package/"manifest.json"
    manifest=read(manifest_path)
    restored_path=output/manifest["original_filename"]
    check(sorted(p.name for p in output.iterdir())==[manifest["original_filename"]],"Unexpected restored output contents")
    check(not output.is_symlink() and not output.is_junction() and restored_path.is_file()
          and not restored_path.is_symlink() and not restored_path.is_junction(),"Expected regular restored file")
    original_bytes=original.read_bytes()
    restored_bytes=restored_path.read_bytes()
    check(restored_bytes==original_bytes,"Restored bytes differ from original")
    check(len(restored_bytes)==manifest["original_size"] and digest(restored_path)==manifest["input_sha256"]==plan["input_sha256"],"Restored size/hash mismatch")
    observer=ROOT/plan["observer_root"]
    observations=[json.loads(line) for line in (observer/"observations.jsonl").read_text(encoding="utf-8").splitlines()]
    pane=observations[-1]["panes"]["decompress"]
    check(pane["summary"]=="완료 · 검증 통과" and pane["name"]==output.name,"GUI state mismatch")
    check(Path(pane["source"]).resolve()==package.resolve(),"GUI package path mismatch")
    matches=[]
    for path in (observer/"sessions").rglob("*.json"):
        job=read(path)
        if Path(job.get("request",{}).get("output_dir",".")).resolve()==output.resolve():
            matches.append((path,job))
    check(len(matches)==1,"Expected one restoration job log")
    log_path,job=matches[0]
    check(job["request"]["operation"]=="decompress" and Path(job["request"]["input_path"]).resolve()==package.resolve(),"Job request mismatch")
    check(job["status"]=="succeeded" and job["return_code"]==0 and job["log_error"] is None,"Job did not succeed")
    response=json.loads(job["stdout"])
    check(response==job["data"] and response["verified"] is True,"Child response/log mismatch")
    check(response["smart_decompress_version"]==response["smart_mode_version"]==1,"Restore version mismatch")
    check(response["manifest_sha256"]==digest(manifest_path) and response["algorithm"]==manifest["algorithm"],"Package identity mismatch")
    check(response["compressed_sha256"]==manifest["compressed_sha256"] and response["compressed_size"]==manifest["compressed_size"],"Saved payload metadata mismatch")
    check(response["restored_file"]==restored_path.name and response["restored_size"]==len(restored_bytes)
          and response["restored_sha256"]==digest(restored_path),"Restore response file mismatch")
    check(Path(response["output_dir"]).resolve()==output.resolve() and Path(response["package_dir"]).resolve()==package.resolve(),"Restore response paths mismatch")
    check(response["smart_decompress_source_sha256"]==digest(ROOT/"smart_decompress.py"),"Restore source mismatch")
    snapshot=job["input_snapshot"]
    for rel,value in snapshot["source_sha256"].items():
        check(digest(ROOT/rel)==value,"Job source changed: "+rel)
    for path,value in snapshot["input_files"].items():
        check(digest(Path(path))==value,"Job package input changed: "+path)
    expected=[["복원 파일",restored_path.name],["복원 bytes",str(len(restored_bytes))],
              ["알고리즘",manifest["algorithm"]],["복원 SHA-256",digest(restored_path)],
              ["크기·해시 검증","통과"],["요청 출력 경로",str(output)]]
    check(pane["tree"]==expected,"GUI restoration rows mismatch")
    protected=read(ROOT/"research_log/gui_reboot_recovery_20261028.json")["protected_after"]
    check(all(digest(ROOT/rel)==value for rel,value in protected.items()),"Pre-existing protected file changed")
    paths=[plan_path,prior_path,original,manifest_path,package/manifest["compressed_file"],restored_path,log_path]
    artifacts={path.relative_to(ROOT).as_posix():digest(path) for path in paths}
    result=dict(status="manual_gui_restoration_saved_bytes_verified",verified_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        verifier_sha256=digest(Path(__file__)),plan_sha256=digest(plan_path),input_kind=plan["input_kind"],
        interaction_operator="user",verification_operator="assistant",algorithm=manifest["algorithm"],
        restored_file=restored_path.name,restored_path=restored_path.relative_to(ROOT).as_posix(),
        restored_size=len(restored_bytes),restored_sha256=digest(restored_path),original_bytes_equal=True,
        original_filename_preserved=True,verified_gui_rows=len(expected),job_log_path=log_path.relative_to(ROOT).as_posix(),
        job_log_snapshot=job,observed_state_snapshot=observations[-1],artifact_sha256=artifacts,
        existing_protected_files_unchanged=len(protected),previous_smart_artifacts_unchanged=True,
        assistant_reran_decompression_or_prediction=False,tests_suite_rerun=False,
        agent_visual_restore_qa_performed=False,manual_compare_completed=False,unseen_research_evaluation=False,
        next_step="User runs actual Compare from Smart result to planned fresh output; verify raw repeats/scores/log next.")
    check(all(digest(ROOT/rel)==value for rel,value in artifacts.items()),"Artifact changed during verification")
    with OUT.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2);stream.write("\n")
    print(json.dumps({key:result[key] for key in ("status","algorithm","restored_size","restored_sha256",
        "original_bytes_equal","verified_gui_rows","existing_protected_files_unchanged")},ensure_ascii=False))


if __name__=="__main__":main()
