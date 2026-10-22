"""Light status observer only; never launches/retries measurement jobs."""
import json
from pathlib import Path
import sys
import time

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))
from src import memory_repeatability_validation as r

study = Path(__file__).resolve().parent
with (study / "run_04_monitor.jsonl").open("x", encoding="utf-8", newline="\n") as log:
    while True:
        try:
            metadata = r._read_json(study / "run_04/metadata.json")
            snapshot = {name: metadata.get(name) for name in (
                "run_status", "job_count", "memory_repeat_count", "timing_repeat_count",
                "failed_repeat_count", "run_error", "finalization_status")}
            snapshot["metadata_save_retry_event_count"] = len(metadata.get("metadata_save_retry_events", []))
            snapshot["observed_at_utc"] = r.common._now()
            terminal = (metadata["run_status"] not in ("running", "finalizing")
                        and not (study / ".active_run.json").exists())
            if terminal:
                coordinator = r._read_json(study / "metadata.json")
                snapshot["coordinator_status"] = coordinator["run_status"]
                snapshot["attempt_failed_repeat_count"] = coordinator["failed_repeat_count"]
        except (OSError, ValueError) as exc:
            terminal = False
            snapshot = dict(observed_at_utc=r.common._now(),
                            observer_error=f"{type(exc).__name__}: {exc}")
        line = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
        log.write(line + "\n")
        log.flush()
        print(line, flush=True)
        if terminal:
            break
        time.sleep(30)
