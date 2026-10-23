"""Validation-only candidate analysis of independently audited Run 2 replacement.

Run with python -B. Reaudit both evidence roots on every invocation, calculate
only from hash-bound snapshots, and export into an exclusive new directory.
The unchanged three-day analyzer supplies only its pure numeric/CSV functions;
its audit, analysis, date acceptance rules, and publisher are never called.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sys

from research_log import analyze_memory_stability_validation as numeric
from research_log import verify_memory_repeatability_validation as verification

require = verification.require
_calculate = numeric._calculate
LABEL_FIELDS, REGRET_FIELDS = numeric.LABEL_FIELDS, numeric.REGRET_FIELDS


def _recheck(audited, sources):
    verification.recheck_report_inputs(audited)
    for name, checksum in sources.items():
        require(verification.digest((verification.ROOT / name).read_bytes()) == checksum,
                f"Analysis source changed: {name}")


def _check_policy(plan, config):
    """Share the numeric kernel only while every inherited numeric rule agrees."""
    fixed = verification.fixed_plan(plan["attempt_id"], plan["attempt_reason"])
    verification.same(plan["candidate_weights"], fixed["candidate_weights"], "Candidate weights changed")
    verification.same(plan["criteria"], fixed["criteria"], "Repeatability criteria changed")
    verification.same(plan["candidate_weights"], numeric.verification.WEIGHTS, "Kernel weights differ from frozen plan")
    inherited = {k: v for k, v in numeric.verification.CRITERIA.items()
                 if k not in ("day_offsets_hours", "first_run_tolerance_minutes", "second_run_gap_minutes")}
    verification.same({k: plan["criteria"][k] for k in inherited}, inherited, "Kernel numeric criteria differ from plan")
    verification.same(list(numeric.RUNS), list(verification.RUNS), "Kernel logical run IDs differ")
    verification.same(list(numeric.ALGORITHMS), plan["criteria"]["tie_order"], "Kernel tie order differs")
    expected_official = {mode: dict(compression_ratio=w["size"], compression_time=w["compress"],
                                    decompression_time=w["decompress"])
                         for mode, w in numeric.OFFICIAL_WEIGHTS.items()}
    verification.same(config["selection_modes"], expected_official, "Official comparison weights changed")


def analyze(directory: Path, replacement_directory: Path) -> dict:
    require(sys.dont_write_bytecode, "Run analysis with python -B")
    directory, replacement_directory = Path(directory).resolve(), Path(replacement_directory).resolve()
    source_paths = [Path(__file__).resolve(), Path(numeric.__file__).resolve(),
                    Path(verification.__file__).resolve(), Path(verification.base.__file__).resolve(),
                    *(verification.ROOT / name for name in verification.SOURCES),
                    verification.ROOT / verification.AMENDMENT_PATH]
    sources = {p.relative_to(verification.ROOT).as_posix(): verification.digest(p.read_bytes()) for p in source_paths}
    audited = verification.audit(directory, replacement_directory)
    require(audited.get("audit_passed") is True and audited.get("measurement_status") == "validation_only"
            and audited.get("score_inclusion") is False and audited.get("design_id") == verification.DESIGN
            and audited.get("amendment_id") == verification.AMENDMENT, "Audit did not validate replacement evidence")
    verification.same(audited["evidence_directories"], dict(active=str(directory), replacement=str(replacement_directory)),
                      "Audit evidence roots differ from requested inputs")
    for name, checksum in audited["audit_source_sha256"].items():
        if name in sources:
            require(sources[name] == checksum, f"Audit source changed: {name}")
    _recheck(audited, sources)
    # Snapshot the complete audited active tree, including plan and metadata.
    # The replacement/archive tree remains fenced by the full independent audit.
    snapshots = {}
    for name, checksum in audited["input_sha256"]["active"].items():
        data = (directory / verification.relative_name(name)).read_bytes()
        require(verification.digest(data) == checksum, f"Evidence changed after audit: {name}")
        snapshots[name] = data

    def table(name, fields):
        reader = csv.DictReader(io.StringIO(snapshots[name].decode("utf-8"), newline=""), strict=True)
        require(reader.fieldnames == list(fields), "Audited CSV schema mismatch")
        rows = list(reader)
        require(all(set(r) == set(fields) and all(isinstance(v, str) for v in r.values()) for r in rows),
                "Audited CSV row width mismatch")
        return rows

    plan = verification.parse_json(snapshots["plan.json"])
    config = verification.parse_json((verification.ROOT / "config/experiment_config.json").read_bytes())
    _check_policy(plan, config)
    samples = table("samples.csv", verification.SAMPLE_FIELDS)
    measurements = {r: table(f"run_{r:02d}/measurements.csv", verification.MEASUREMENT_FIELDS) for r in verification.RUNS}
    raw = {r: {kind: table(f"run_{r:02d}/{kind}_repeats.csv",
                         verification.MEMORY_FIELDS if kind == "memory" else verification.TIMING_FIELDS)
               for kind in ("memory", "timing")} for r in verification.RUNS}
    calculated = _calculate(samples, measurements, raw)
    _recheck(audited, sources)
    return dict(schema_version=1, design_id=verification.DESIGN, amendment_id=verification.AMENDMENT,
        attempt_id=audited["attempt_id"], measurement_status="validation_only", score_inclusion=False,
        analysis_status="completed_validation_candidate_analysis",
        technical_validity_status="independent_replacement_evidence_audit_passed",
        analyzed_at_utc=datetime.now(timezone.utc).isoformat(),
        original_measurement_commit=audited["original_measurement_commit"],
        replacement_execution_commit=audited["replacement_execution_commit"],
        source_sha256=sources, audit=audited, samples=samples,
        candidate_weights=plan["candidate_weights"], criteria=plan["criteria"],
        official_comparison_weights=numeric.OFFICIAL_WEIGHTS,
        active_execution_order=audited["active_execution_order"], original_schedule_order_preserved=False,
        conventions=dict(anchor="median of six run representatives; not pooled raw repeats",
            memory="max of phase medians; separate phase processes are not paired",
            score="weighted ln(value/minimum); log difference fallback on intermediate overflow/underflow",
            ties="exact equality; gzip,bz2,lzma,zstd order; zero second-best gap on ties",
            transfer="all 36 directed logical run pairs including zero diagonals in each scenario",
            chronology="logical run IDs retained; physical order and timestamps are in the audit",
            ranges="closed observed ranges, not confidence intervals", cv="population standard deviation / mean",
            thresholds="unrounded inclusive <= stability limits; strict > delta for memory benefit",
            arithmetic_QA="round-off tolerance only for theorem consistency; never for policy or selection"),
        limitations=["Candidate analysis only; official three-metric labels, models and weights remain unchanged.",
            "Original collection failed; three archived timeouts remain failures and are not imputed.",
            "Full Run 2 replacement changed physical run order and execution HEAD; this is not original schedule success.",
            "Observed environment only; no cross-day proof, future error bound or hardware generalization.",
            "Stability and observed memory selection benefit are separate; neither automatically adopts memory.",
            "Reference anchor is diagnostic, not an observed run or external oracle.",
            "No compression, restoration, measurement or model learning was rerun.",
            "Saved consistency does not independently authenticate execution or certify restoration."], **calculated)


def _check_output(output, roots):
    output = Path(output).resolve()
    require(not any(output.is_relative_to(Path(root).resolve()) for root in roots),
            "Analysis output must be outside input evidence")
    require(not output.exists(), "Analysis output already exists")
    return output


def publish(report, output: Path):
    """Keep partial evidence and a failure marker if a new publication fails."""
    require(report.get("analysis_status") == "completed_validation_candidate_analysis"
            and report.get("design_id") == verification.DESIGN and report.get("score_inclusion") is False
            and report["audit"].get("audit_passed") is True, "Cannot publish unsuccessful analysis")
    output = _check_output(output, report["audit"]["evidence_directories"].values())
    _recheck(report["audit"], report["source_sha256"])
    payloads = {"audit.json": (json.dumps(report["audit"], indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"),
                "candidate_labels.csv": numeric._csv_bytes(LABEL_FIELDS, report["candidate_labels"]),
                "transfer_regrets.csv": numeric._csv_bytes(REGRET_FIELDS, report["transfer_regrets"]),
                ".gitattributes": b"* -text\n"}
    output.mkdir(exist_ok=False)
    try:
        for name, data in payloads.items():
            with (output / name).open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            require((output / name).read_bytes() == data, f"Published bytes mismatch: {name}")
        _recheck(report["audit"], report["source_sha256"])
        summary = {k: v for k, v in report.items() if k not in ("candidate_labels", "transfer_regrets")}
        summary["tables"] = dict(candidate_labels=dict(file="candidate_labels.csv", rows=len(report["candidate_labels"]), fields=list(LABEL_FIELDS)),
                               transfer_regrets=dict(file="transfer_regrets.csv", rows=len(report["transfer_regrets"]), fields=list(REGRET_FIELDS)))
        summary["output_artifact_sha256"] = {name: verification.digest(data) for name, data in payloads.items()}
        summary["publication_contract"] = "Require successful CLI/API return and no publication_failed.json; partial files are not a successful export."
        data = (json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        with (output / "stability_summary.json").open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        require((output / "stability_summary.json").read_bytes() == data, "Published summary bytes mismatch")
        _recheck(report["audit"], report["source_sha256"])
    except BaseException as exc:
        try:
            with (output / "publication_failed.json").open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(dict(publication_status="failed", validity_status="inconclusive", error=f"{type(exc).__name__}: {exc}"),
                          stream, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
        except BaseException as marker_error:
            exc.add_note(f"Recording publication failure also failed: {type(marker_error).__name__}: {marker_error}")
        raise


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, required=True)
    parser.add_argument("--replacement-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, help="Exclusive new analysis directory outside evidence roots")
    args = parser.parse_args(arguments)
    try:
        if args.output_dir:
            _check_output(args.output_dir, (args.experiment_dir, args.replacement_dir))
        report = analyze(args.experiment_dir, args.replacement_dir)
        if args.output_dir:
            publish(report, args.output_dir)
            printed = dict(analysis_status=report["analysis_status"], decision=report["decision"], counts=report["counts"],
                           measurement_status="validation_only", score_inclusion=False, output_dir=str(args.output_dir.resolve()))
        else:
            printed = report
        serialized = json.dumps(printed, indent=2, ensure_ascii=False, allow_nan=False)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, csv.Error, IndexError) as exc:
        parser.exit(1, f"Analysis inconclusive: {exc}\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
