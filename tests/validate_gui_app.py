"""Opt-in mapped Tk/backend smoke verification, not model performance research.

Run from the repository root with its venv Python. This calls application callbacks
and pumps actual Tk events; it does not automate OS input or take screenshots.
Every run creates fresh artifacts and refuses to replace the requested JSON record.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
import tkinter as tk
import traceback
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from gui_app import CompressionApp, MODEL_LABELS, demo_comparison
from src.gui_jobs import ALGORITHMS, MODELS, MODES, SOURCE_FILES, JobRunner
from src.scoring import MODE_WEIGHTS, score_sample


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record",type=Path,required=True)
    args = parser.parse_args()
    if args.record.exists():
        parser.error("Record already exists; choose a new record path")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "data/temp" / ("gui_app_validation_"+stamp)
    output.mkdir()
    source = output / "한글 공백 & GUI 입력 🧪.md"
    source.write_bytes((ROOT / "README.md").read_bytes())
    protected = {ROOT / p for p in SOURCE_FILES}
    protected.update(ROOT / p for p in ("README.md","research_protocol_v2.md","gui_app.py","tests/test_gui_app.py","tests/validate_gui_app.py"))
    for kind in MODELS:
        protected.update((ROOT / "data/results/pilot_1008" / kind).glob("*.pkl"))
        protected.add(ROOT / "data/results/pilot_1008" / kind / (kind+"_summary.json"))
    protected.add(source)
    before = {str(p.relative_to(ROOT)):sha(p) for p in sorted(protected)}
    record = dict(started_at_utc=stamp,kind="Tk callback and real backend smoke; not research/model evaluation",
        git_head_at_execution=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        python=sys.version,platform=platform.platform(),output_dir=str(output),protected_before=before,jobs=[],checks={},
        visual_qa=dict(native_input_automation=False,screenshots=False,
            blocker="Computer-use node_repl kernel initialization failed with os error 3 (kernel assets path missing), including retry after reset"))
    root = tk.Tk()
    runner = JobRunner(log_root=output / "sessions")
    dialogs = Mock()
    app = CompressionApp(root,runner=runner,dialogs=dialogs)
    callback_errors = []
    root.report_callback_exception = lambda *exc: callback_errors.append(repr(exc))
    heartbeat = [0]
    def tick():
        heartbeat[0] += 1
        root.after(10,tick)
    root.after(10,tick)
    try:
        record["tk_patchlevel"] = root.tk.call("info","patchlevel")
        root.update()
        assert root.winfo_ismapped()
        assert not runner.busy and app.active is None
        record["checks"]["mapped_window_without_starting_job"] = True
        for pane in app.panes.values():
            pane.parent.set(str(output))

        def run(operation, *, expect="succeeded"):
            pane = app.panes[operation]
            start_count = heartbeat[0]
            assert app.start(operation)
            assert not app.start(operation), "Duplicate accepted"
            assert not app.request_close(), "Active window closed"
            deadline = time.monotonic()+120
            while app.active is not None:
                root.update()
                if time.monotonic() > deadline:
                    raise TimeoutError("Tk job did not finish")
                time.sleep(.005)
            result = pane.last_result
            assert result.status == expect, result.as_dict()
            assert heartbeat[0]-start_count >= 2, "Tk heartbeat did not run during job"
            assert not runner.busy
            assert all(str(w.cget("state")) == normal for p in app.panes.values() for w,normal in p.controls)
            assert all(app.notebook.tab(p.frame,"state") == "normal" for p in app.panes.values())
            assert result.log_path and json.loads(result.log_path.read_text(encoding="utf-8")) == result.as_dict()
            entry = result.as_dict()
            entry["tk_heartbeats_during_job"] = heartbeat[0]-start_count
            entry["displayed_rows"] = [pane.tree.item(i,"values") for i in pane.tree.get_children()]
            entry["displayed_summary"] = pane.summary.get()
            record["jobs"].append(entry)
            return result

        for kind in MODELS:
            for mode in MODES:
                pane = app.panes["smart"]
                pane.source.set(str(source))
                pane.mode.set(mode)
                pane.model.set(MODEL_LABELS[kind])
                pane.name.set(kind+"_"+mode)
                smart = run("smart")
                protected.update(smart.request.output_dir.iterdir())
                # Record package bytes before the restore/corruption tests.
                for p in smart.request.output_dir.iterdir():
                    before[str(p.relative_to(ROOT))] = sha(p)
                app.prepare_restore()
                assert app.active is None and not runner.busy
                restored = run("decompress")
                assert (restored.request.output_dir / restored.data["restored_file"]).read_bytes() == source.read_bytes()
        app.prepare_compare()
        assert app.active is None and not runner.busy
        compared = run("compare")
        joined = demo_comparison(app.smart_result,compared,"fast_access")
        assert joined and "동일 입력 Demo" in app.panes["compare"].demo.get()
        record["demo"] = joined
        compare_dir = compared.request.output_dir
        artifacts = {p.name:p.read_text(encoding="utf-8") for p in compare_dir.iterdir() if p.is_file()}
        record["compare_artifacts_utf8"] = artifacts
        rows = list(csv.DictReader((compare_dir / "compression_results.csv").open(encoding="utf-8",newline="")))
        repeats = list(csv.DictReader((compare_dir / "timing_repeats.csv").open(encoding="utf-8",newline="")))
        labels = list(csv.DictReader((compare_dir / "selection_labels.csv").open(encoding="utf-8",newline="")))
        assert len(repeats) == 40 and len(rows) == 4 and len(labels) == 3
        for row in rows:
            assert row["verified"] == "True" and row["status"] == "ok"
            for phase,field in (("compress","compression_time_ms"),("decompress","decompression_time_ms")):
                elapsed = [int(r["elapsed_ns"]) for r in repeats if r["algorithm"] == row["algorithm"] and r["phase"] == phase]
                assert len(elapsed) == 5 and float(row[field]) == statistics.median(elapsed)/1e6
        # Recompute official scores from saved measurements with the existing scorer.
        config = json.loads((compare_dir / "config_snapshot.json").read_text(encoding="utf-8"))
        assert config["selection_modes"] == MODE_WEIGHTS
        scored = score_sample(rows)
        for label in labels:
            expected = scored[label["mode"]]
            assert label["best_algorithm"] == expected.best_algorithm and float(label["best_score"]) == expected.best_score
            assert all(float(label["score_"+a]) == expected.scores[a] for a in ALGORITHMS)
        record["checks"]["raw_repeats_40_aggregates_4_labels_3_and_medians"] = True
        record["checks"]["official_scores_recomputed"] = True
        # A published comparison keeps its official weights and memory exclusions.
        assert compared.data["memory_measured"] is False and compared.data["memory_score_inclusion"] is False
        record["checks"]["memory_not_measured_or_scored"] = True

        # Existing output is rejected before a child process and remains byte-identical.
        pane = app.panes["compare"]
        pane.name.set(compare_dir.name)
        assert not app.start("compare") and pane.last_result is None
        assert {p.name:p.read_text(encoding="utf-8") for p in compare_dir.iterdir() if p.is_file()} == artifacts
        record["checks"]["existing_output_rejected_and_preserved"] = True

        # Deliberate corruption is confined to a new copy, never an existing package.
        broken = output / "intentionally_corrupted_copy"
        shutil.copytree(app.panes["smart"].last_result.request.output_dir,broken)
        payload = broken / smart.data["compressed_file"]
        raw = payload.read_bytes()
        payload.write_bytes(bytes([raw[0]^1])+raw[1:])
        broken_hash = sha(payload)
        pane = app.panes["decompress"]
        pane.source.set(str(broken))
        pane.fresh_name()
        failed = run("decompress",expect="failed")
        assert not failed.request.output_dir.exists() and sha(payload) == broken_hash
        assert pane.summary_label.cget("style") == "Error.TLabel" and app.smart_result is None
        record["checks"]["corrupt_copy_rejected_without_output_or_source_change"] = True
        assert callback_errors == [], callback_errors
        record["checks"]["tk_callback_errors"] = callback_errors
        record["checks"]["mapped_window_busy_lock_close_guard_heartbeat_and_unlock"] = True
        record["protected_after"] = {name:sha(ROOT / name) for name in before}
        assert record["protected_after"] == before
        record["checks"]["protected_hashes_unchanged"] = True
        record["checks"]["idle_close"] = app.request_close()
    except BaseException as exc:
        record["status"] = "validation_failed"
        record["error"] = dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        raise
    finally:
        if not app._closed and not runner.busy and app.active is None:
            app.request_close()
        # Preserve evidence on validation failure as well; successful assertions
        # below and the final status are only reached on a complete execution.
        record["protected_before"] = before
        with (output / "validation_partial.json").open("x",encoding="utf-8") as stream:
            json.dump(record,stream,ensure_ascii=False,allow_nan=False,indent=2)

    command = [sys.executable,"-B","-m","unittest","discover","-s","tests","-p","test_gui*.py","-v"]
    tests = subprocess.run(command,cwd=ROOT,capture_output=True,env={**os.environ,"PYTHONIOENCODING":"utf-8"})
    record["tests"] = dict(command=command,return_code=tests.returncode,stdout=tests.stdout.decode("utf-8"),stderr=tests.stderr.decode("utf-8"))
    assert tests.returncode == 0, record["tests"]
    record["status"] = "completed"
    record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    with args.record.open("x",encoding="utf-8") as stream:
        json.dump(record,stream,ensure_ascii=False,allow_nan=False,indent=2)
    print(json.dumps(dict(record=str(args.record),output_dir=str(output),jobs=len(record["jobs"]),status=record["status"])))


if __name__ == "__main__":
    main()
