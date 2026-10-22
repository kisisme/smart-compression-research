"""Run 5 preflight and operator context; no source/config changes or codec calls."""
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))
from src import memory_repeatability_validation as r

class PowerStatus(ctypes.Structure):
    _fields_ = [("ac", wintypes.BYTE), ("battery_flag", wintypes.BYTE),
                ("battery_percent", wintypes.BYTE), ("system_status", wintypes.BYTE),
                ("battery_life", wintypes.DWORD), ("battery_full_life", wintypes.DWORD)]

d = Path(__file__).resolve().parent
plan = r._load_plan(d)
meta = r._read_json(d / "metadata.json")
history = r._history(d, 4, plan)
git = r._git_for_attempt(d)
if git["commit_hash"] != plan["implementation_commit"]:
    raise ValueError("HEAD changed")
if meta["run_status"] != "awaiting_next_run" or len(meta["runs"]) != 4:
    raise ValueError("Not ready for Run 5")
if (d / "run_05").exists() or (d / ".active_run.json").exists():
    raise ValueError("Run 5 already exists or claim active")
if r._sources() != plan["source_sha256"]:
    raise ValueError("Source changed")
env = r._environment()
if r._fixed_environment(env) != r._fixed_environment(plan["environment"]):
    raise ValueError("Environment changed")
for name, expected in meta["artifact_sha256"].items():
    if hashlib.sha256((d / name).read_bytes()).hexdigest() != expected:
        raise ValueError("Artifact changed: " + name)

power = PowerStatus()
api = ctypes.WinDLL("kernel32", use_last_error=True).GetSystemPowerStatus
api.argtypes, api.restype = (ctypes.POINTER(PowerStatus),), wintypes.BOOL
if not api(ctypes.byref(power)):
    raise ctypes.WinError(ctypes.get_last_error())
now = r.common._now()
scheme = subprocess.check_output(["powercfg", "/getactivescheme"]).decode(errors="replace")
guid = re.search(r"[0-9a-fA-F-]{36}", scheme).group()
mode = (ctypes.c_ubyte * 16)()
mode_api_name = "PowerGetUserConfiguredACPowerMode" if power.ac == 1 else "PowerGetUserConfiguredDCPowerMode"
mode_api = getattr(ctypes.WinDLL("powrprof", use_last_error=True), mode_api_name)
mode_api.argtypes, mode_api.restype = (ctypes.c_void_p,), wintypes.DWORD
mode_result = mode_api(ctypes.byref(mode))
mode_guid = str(uuid.UUID(bytes_le=bytes(mode))) if mode_result == 0 else None

# Read the previous observation without modifying earlier evidence.
old_boot = r._read_json(d / "operator_context_run_04.json")
boot_at = "2026-10-15T22:06:37.6972600+09:00"  # Actual CIM observation immediately before this preflight.
boot_delta = abs((datetime.fromisoformat(boot_at)
                  - datetime.fromisoformat(old_boot["preflight_os_boot_at_local"])).total_seconds())
if boot_delta >= 1:
    raise ValueError("Boot time changed")
before = {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in d.rglob("*") if p.is_file()}
events = {
    "power_mode": (
        f"Observed {now}: ACLineStatus={power.ac}, battery={power.battery_percent}%, "
        f"active power plan GUID={guid}; {mode_api_name} return={mode_result}, "
        f"current supply preference GUID={mode_guid}. No power settings changed. "
        "Latest user report: battery sufficient to avoid shutdown; continuous AC not guaranteed."),
    "manual_reboot_since_previous_run": False,
    "concurrent_activity": (
        "Latest user report carried forward: no other research jobs; Steam gaming may run, "
        "game shutdown not confirmed. Other ChatGPT activity not independently known. "
        "No Python processes observed in immediate preflight. Only light agent status monitoring."),
    "os_update_events": "Latest user report: none. No independent continuous update monitoring.",
    "other_events": (
         "User requested Run 5 after successful Run 4; prior Run 2 timeout records remain unchanged. "
        "User later reported falling asleep and approving requests late; this is not established "
        "as the cause of worker timeouts. Run 2 Windows Modern Standby logs and failures retained. "
        "Same source/config/HEAD; actual gaps/timestamps preserved without clock/day/gap limits. "
        "No sleep or lid settings changed; continued wakefulness is not certified."),
    "no_research_jobs_running": True,
}
r._check_events(events)
context = {
    "study_design_id": r.DESIGN_ID, "collector_revision": r.COLLECTOR_REVISION,
    "observed_at_utc": now, "environment": env, "ac_line_status": power.ac,
    "battery_percent": power.battery_percent, "active_power_plan_guid": guid,
    "power_mode_api": mode_api_name, "power_mode_result": mode_result, "power_mode_guid": mode_guid,
    "source_sha256": r._sources(), "implementation_commit": plan["implementation_commit"],
    "preflight_other_python_processes_observed": 0, "preflight_os_boot_at_local": boot_at,
    "prior_os_boot_at_local": old_boot["preflight_os_boot_at_local"], "boot_time_difference_seconds": boot_delta,
    "reboot_check_scope": "CIM boot timestamps within one second; small precision drift retained.",
    "operator_report_scope": "Latest user report carried forward, not continuous observation",
    "events": events, "prior_evidence_sha256": before,
    "prior_run_statuses": [m["run_status"] for m in history],
    "prior_failed_repeat_count": meta["failed_repeat_count"], "clock_windows_required": False,
    "run_2_failures_reused_as_normal_results": False,
    "prelaunch_errors": [],
}
for name, value in (("operator_events_run_05.json", events), ("operator_context_run_05.json", context)):
    with (d / name).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
print(json.dumps(dict(observed_at_utc=now, source_environment_history_artifacts_ok=True,
                     prior_failed_repeat_count=meta["failed_repeat_count"],
                     planned_jobs_run_5=len(plan["schedules"]["5"]), ac_line_status=power.ac,
                     battery_percent=power.battery_percent, power_mode_guid=mode_guid,
                     prior_evidence_files=len(before)), ensure_ascii=False))
