"""Read-only verification of the user's native Smart smoke execution.

Decode the already saved selected payload in memory, without another compression,
prediction, benchmark, model deserialization or publication of restored files.
"""
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import subprocess

import zstandard

ROOT=Path(__file__).resolve().parent.parent
PLAN=ROOT/"research_log/gui_manual_qa_plan_20261028.json"
OUT=ROOT/"research_log/gui_manual_smart_verified_20261028.json"


def check(ok,message):
    if not ok:
        raise ValueError(message)


def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_bytes())
def digest(path): return sha(path.read_bytes())
def display(value): return format(value,".7g") if type(value) is float else str(value)


def main():
    check(not OUT.exists(),"Choose a new verification output; no overwrite")
    plan=read(PLAN)
    package=ROOT/plan["output_paths"]["smart"]
    original=Path(plan["input_path"])
    manifest_path=package/"manifest.json"
    manifest=read(manifest_path)
    check(manifest["smart_mode_version"]==1 and manifest["verified"] is True,"Unverified manifest")
    check(manifest["algorithm"]=="zstd" and manifest["compressed_file"]=="payload.zst","Unexpected saved algorithm")
    check(manifest["mode"]==plan["mode"]=="archive","Mode mismatch")
    input_bytes=original.read_bytes()
    check(sha(input_bytes)==plan["input_sha256"]==manifest["input_sha256"],"Input hash mismatch")
    check(Path(manifest["input_path"]).resolve()==original.resolve(),"Input path mismatch")
    check(manifest["original_filename"]==original.name and manifest["original_size"]==len(input_bytes),"Original metadata mismatch")
    payload_path=package/manifest["compressed_file"]
    payload=payload_path.read_bytes()
    check(len(payload)==manifest["compressed_size"] and sha(payload)==manifest["compressed_sha256"],"Payload mismatch")
    check(manifest["compression_ratio"]==len(payload)/len(input_bytes),"Ratio mismatch")
    restored=zstandard.ZstdDecompressor().decompress(payload,max_output_size=len(input_bytes))
    check(restored==input_bytes and sha(restored)==manifest["input_sha256"],"Saved payload does not restore to original bytes")

    provenance=manifest["provenance"]
    model_path=Path(provenance["model_path"])
    summary_path=model_path.parent/"random_forest_summary.json"
    summary=read(summary_path)
    config_path=ROOT/"config/experiment_config.json"
    config=read(config_path)
    check(provenance["model_kind"]==plan["model"]=="random_forest","Model choice mismatch")
    check(digest(model_path)==provenance["model_sha256"]==summary["output_sha256"][model_path.name],"Model hash mismatch")
    check(digest(summary_path)==provenance["model_summary_sha256"],"Model summary hash mismatch")
    check(digest(config_path)==provenance["config_sha256"],"Config hash mismatch")
    for key,source in (("compression_settings","compression"),("feature_settings","features"),
                       ("model_settings","random_forest")):
        check(provenance[key]==config[source],"Recorded settings differ: "+key)
    check(provenance["selection_weights"]==config["selection_modes"][plan["mode"]],"Weights mismatch")
    for rel,value in provenance["source_sha256"].items():
        check(digest(ROOT/rel)==value,"Prediction source mismatch: "+rel)
    check(digest(ROOT/"smart_compress.py")==manifest["smart_compress_source_sha256"],"Smart source mismatch")
    check(platform.python_version()==provenance["python_version"],"Python version mismatch")
    for package_name,version in provenance["package_versions"].items():
        check(metadata.version(package_name)==version,"Package version mismatch: "+package_name)
    check(all(type(v) in (int,float) and math.isfinite(v) for v in manifest["features"].values()),"Invalid stored features")

    observer=ROOT/plan["observer_root"]
    observations=[json.loads(line) for line in (observer/"observations.jsonl").read_text(encoding="utf-8").splitlines()]
    pane=observations[-1]["panes"]["smart"]
    check(pane["summary"]=="완료 · 검증 통과" and pane["mode"]==plan["mode"] and pane["model"]==plan["model_label"],"GUI state mismatch")
    check(pane["name"]==package.name and Path(pane["source"]).resolve()==original.resolve(),"GUI paths mismatch")
    expected=[
        ["선택 알고리즘",manifest["algorithm"]],["사용 목적 / 모델",plan["mode"]+" / "+plan["model_label"]],
        ["원본 bytes",str(len(input_bytes))],["압축 bytes",str(len(payload))],
        ["압축률 (작을수록 유리)",display(manifest["compression_ratio"])],["복원 검증","통과"],
        ["모델 출력 (보정되지 않음)",display(manifest["prediction_confidence"])],
        *[["특징 · "+name,display(value)] for name,value in manifest["features"].items()],
        ["요청 출력 경로",str(package)]]
    check(pane["tree"]==expected,"Displayed rows differ from manifest")
    candidates=[]
    for log_path in (observer/"sessions").rglob("*.json"):
        log=read(log_path)
        if Path(log.get("request",{}).get("output_dir",".")).resolve()==package.resolve():
            candidates.append((log_path,log))
    check(len(candidates)==1,"Expected exactly one Smart execution log")
    log_path,job=candidates[0]
    check(job["status"]=="succeeded" and job["return_code"]==0 and job["log_error"] is None,"Job did not succeed")
    check(job["data"]==manifest,"Job manifest snapshot mismatch")
    request=job["request"]
    check(request["operation"]=="smart" and request["mode"]==plan["mode"] and request["model_kind"]==plan["model"],"Job request mismatch")
    snapshot=job["input_snapshot"]
    for rel,value in snapshot["source_sha256"].items():
        check(digest(ROOT/rel)==value,"Job source changed: "+rel)
    for path,value in snapshot["input_files"].items():
        check(digest(Path(path))==value,"Job input/model changed: "+path)
    response=json.loads(job["stdout"])
    check(response["verified"] is True and response["algorithm"]==manifest["algorithm"],"Child response mismatch")
    protected=read(ROOT/"research_log/gui_reboot_recovery_20261028.json")["protected_after"]
    check(all(digest(ROOT/rel)==value for rel,value in protected.items()),"Pre-existing protected file changed")
    artifact_paths=[PLAN,manifest_path,payload_path,log_path,original,model_path,summary_path,config_path]
    artifact_hashes={p.relative_to(ROOT).as_posix():digest(p) for p in artifact_paths}
    result=dict(status="manual_smart_package_and_observer_verified",verified_at_utc=datetime.now(timezone.utc).isoformat(),
        execution_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        verifier_sha256=digest(Path(__file__)),plan_sha256=digest(PLAN),
        input_kind=plan["input_kind"],interaction_operator="user",verification_operator="assistant",
        package_dir=package.relative_to(ROOT).as_posix(),algorithm=manifest["algorithm"],mode=manifest["mode"],model=provenance["model_kind"],
        original_size=len(input_bytes),compressed_size=len(payload),compression_ratio=len(payload)/len(input_bytes),
        restored_in_memory_matches_original=True,restored_sha256=sha(restored),
        verified_gui_rows=len(expected),job_log_path=log_path.relative_to(ROOT).as_posix(),job_id=job["job_id"],
        job_started_at_utc=job["started_at_utc"],job_finished_at_utc=job["finished_at_utc"],
        observed_state_snapshot=observations[-1],manifest_snapshot=manifest,job_log_snapshot=job,
        native_screen_observations=dict(
            method="Assistant inspected native cua_repl screenshots and sent scroll/click actions; screenshot payloads not saved.",
            gui_visible=True,pycharm_occludes_right_side=True,
            top_summary_and_sizes_seen=True,scroll_down_changed_visible_rows=True,
            bottom_bigram_segment_entropy_and_output_path_row_seen=True,
            row_click_selected_visible_feature=True,end_key_attempt_blocked_twice=True,
            end_key_blocker="user input was detected in this window; call get_window_state before continuing",
            full_unoccluded_gui_or_all_dpi_verified=False,original_capture_root_cause_established=False),
        existing_protected_files_unchanged=len(protected),artifact_sha256=artifact_hashes,
        model_deserialized_or_new_prediction=False,new_compression_or_benchmark=False,
        restored_files_published=False,manual_gui_restore_and_compare_completed=False,
        tests_suite_rerun=False,unseen_research_evaluation=False,
        next_step="User executes GUI restore to planned fresh output; verify actual restored bytes and logs next.")
    check(all(digest(ROOT/rel)==value for rel,value in artifact_hashes.items()),"Artifact changed during verification")
    with OUT.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2);stream.write("\n")
    print(json.dumps({k:result[k] for k in ("status","algorithm","original_size","compressed_size","compression_ratio",
        "restored_in_memory_matches_original","verified_gui_rows","existing_protected_files_unchanged")},ensure_ascii=False))


if __name__=="__main__":main()
