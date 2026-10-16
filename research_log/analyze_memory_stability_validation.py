"""Validation-only candidate analysis bound to independently audited evidence.

Run with python -B. Default output is the full report on stdout. --output-dir
creates a NEW directory containing audit.json, candidate_labels.csv,
transfer_regrets.csv and stability_summary.json. It never alters the attempt.
No runner, worker, compressor or official scoring imports or execution.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import io
from itertools import combinations
import json
import math
import os
from pathlib import Path
import statistics
import sys

from research_log import verify_memory_stability_validation as verification

ALGORITHMS = verification.ALGORITHMS
RUNS = verification.RUNS
MODES = ("archive", "balanced", "fast_access")
SCENARIOS = ("memory_only", "timing_only", "joint")
STRATA = ("core", "tiny")
METRICS = ("size", "compress", "decompress", "memory")
LABEL_FIELDS = ("sample_id", "stratum", "mode", "scenario", "run_id", "best_algorithm", "best_score",
                "second_best_score", "second_best_gap", "tied_algorithms", *("score_" + a for a in ALGORITHMS))
REGRET_FIELDS = ("sample_id", "stratum", "mode", "scenario", "source_run_id", "target_run_id", "selected_algorithm",
                 "target_best_algorithm", "predicted_score", "oracle_best_score", "regret")
OFFICIAL_WEIGHTS = {"archive": dict(size=.70, compress=.15, decompress=.15, memory=0),
                    "balanced": dict(size=.50, compress=.25, decompress=.25, memory=0),
                    "fast_access": dict(size=.30, compress=.20, decompress=.50, memory=0)}


def require(condition, message):
    verification.require(condition, message)


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value > 0, f"Invalid positive value: {label}")
    return value


def log_ratio(value, best):
    number(value, "log numerator")
    number(best, "log denominator")
    # Preserve the specified ln(value/best) calculation normally; avoid an
    # intermediate overflow for otherwise finite positive metrics.
    ratio = value / best
    return math.log(ratio) if math.isfinite(ratio) and ratio > 0 else math.log(value) - math.log(best)


def stats(values):
    require(bool(values), "Empty diagnostic group")
    for value in values:
        number(value, "diagnostic value")
    mean = statistics.mean(values)
    std = statistics.pstdev(values)
    return dict(values=list(values), median=statistics.median(values), mean=mean,
                min=min(values), max=max(values), population_std=std, cv=std / mean)


def select(metrics, weights):
    require(set(metrics) == set(ALGORITHMS) and set(weights) == set(METRICS), "Incomplete algorithm/weight vector")
    for algorithm in ALGORITHMS:
        require(set(metrics[algorithm]) == set(METRICS), "Incomplete metric vector")
        for field in METRICS:
            number(metrics[algorithm][field], field)
    require(all(type(w) in (int, float) and math.isfinite(w) and w >= 0 for w in weights.values()), "Invalid weights")
    best = {field: min(metrics[a][field] for a in ALGORITHMS) for field in METRICS}
    scores = {a: sum(weights[f] * log_ratio(metrics[a][f], best[f]) for f in METRICS) for a in ALGORITHMS}
    require(all(math.isfinite(v) and v >= 0 for v in scores.values()), "Invalid candidate score")
    ordered = sorted(scores.values())
    ties = [a for a in ALGORITHMS if scores[a] == ordered[0]]
    return dict(best_algorithm=ties[0], best_score=ordered[0], second_best_score=ordered[1],
                second_best_gap=ordered[1] - ordered[0], tied_algorithms=ties,
                **{"score_" + a: scores[a] for a in ALGORITHMS})


def judgment(technical_valid, spans, memory_regrets, joint_regrets):
    """Inclusive, unrounded policy boundaries; no approximate score ties."""
    if technical_valid is not True:
        return dict(status="inconclusive", memory_stability_satisfied=None, joint_stability_satisfied=None)
    require(bool(spans) and bool(memory_regrets) and bool(joint_regrets), "Missing judgment conditions")
    for value in [*spans, *memory_regrets, *joint_regrets]:
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "Invalid judgment value")
    criteria = verification.CRITERIA
    limit = criteria["epsilon"] / (2 * criteria["w_memory_max"])
    memory_ok = all(v <= limit for v in spans) and all(v <= criteria["delta"] for v in memory_regrets)
    joint_ok = all(v <= criteria["delta"] for v in joint_regrets)
    status = ("memory_stability_not_satisfied" if not memory_ok else
              "joint_stability_not_satisfied" if not joint_ok else "observed_conditions_satisfied")
    return dict(status=status, memory_stability_satisfied=memory_ok, joint_stability_satisfied=joint_ok)


def _calculate(samples, measurements, raw):
    """Internal numeric kernel on complete audit-validated rows; no I/O."""
    require(set(measurements) == set(RUNS) and set(raw) == set(RUNS), "Exactly six runs are required")
    ids = [s["sample_id"] for s in samples]
    require(len(ids) == len(set(ids)) and ids, "Duplicate/empty samples")
    strata = {s["sample_id"]: s["stratum"] for s in samples}
    require(set(strata.values()) == set(STRATA), "Both strata are required")
    groups = defaultdict(dict)
    for run in RUNS:
        require(set(raw[run]) == {"memory", "timing"}, "Missing raw measurement kind")
        for kind, rows in raw[run].items():
            for row in rows:
                key = (run, row["sample_id"], row["algorithm"], kind, row["phase"])
                index = verification.positive_int(row["repeat_index"], "repeat_index")
                require(index not in groups[key], "Duplicate raw repeat")
                groups[key][index] = verification.positive_int(row["peak_process_working_set_bytes" if kind == "memory" else "elapsed_ns"], kind)
    expected_groups = {(r, s, a, k, p) for r in RUNS for s in ids for a in ALGORITHMS
                       for k in ("memory", "timing") for p in verification.PHASES}
    require(set(groups) == expected_groups and all(set(g) == {1, 2, 3, 4, 5} for g in groups.values()), "Incomplete/unplanned raw groups")
    arrays = {key: [values[i] for i in range(1, 6)] for key, values in groups.items()}
    vectors, representatives, phases = {}, [], []
    for run in RUNS:
        rows = measurements[run]
        pairs = [(row["sample_id"], row["algorithm"]) for row in rows]
        require(len(pairs) == len(set(pairs)) and set(pairs) == {(s, a) for s in ids for a in ALGORITHMS}, "Incomplete/duplicate measurements")
        for row in rows:
            sid, algorithm = row["sample_id"], row["algorithm"]
            require(row["verified"] == "True" and row["failed_repeat_count"] == "0", "Failed pair cannot be analyzed")
            values = {(kind, p): statistics.median(arrays[run, sid, algorithm, kind, p])
                      for kind in ("memory", "timing") for p in verification.PHASES}
            vector = dict(size=number(float(row["compression_ratio"]), "ratio"),
                          compress=values["timing", "compress"] / 1000000,
                          decompress=values["timing", "decompress"] / 1000000,
                          memory=max(values["memory", "compress"], values["memory", "decompress"]))
            expected = dict(compression_time_ms=vector["compress"], decompression_time_ms=vector["decompress"],
                            compression_peak_memory_bytes=values["memory", "compress"],
                            decompression_peak_memory_bytes=values["memory", "decompress"], peak_memory_bytes=vector["memory"])
            for field, value in expected.items():
                actual = verification.positive_int(row[field], field) if "memory" in field else float(row[field])
                require(actual == value, f"Measurement differs from raw median: {field}")
            vectors[run, sid, algorithm] = vector
            maximum = [p for p in verification.PHASES if values["memory", p] == vector["memory"]]
            representatives.append(dict(run_id=run, sample_id=sid, stratum=strata[sid], algorithm=algorithm,
                                        compression_ratio=vector["size"], compression_time_ms=vector["compress"],
                                        decompression_time_ms=vector["decompress"], compression_peak_memory_bytes=values["memory", "compress"],
                                        decompression_peak_memory_bytes=values["memory", "decompress"], peak_memory_bytes=vector["memory"],
                                        maximum_phases=maximum))
            for kind in ("memory", "timing"):
                for phase in verification.PHASES:
                    phases.append(dict(run_id=run, sample_id=sid, stratum=strata[sid], algorithm=algorithm, kind=kind,
                                       phase=phase, unit="bytes" if kind == "memory" else "ns", repeat_indices=[1, 2, 3, 4, 5],
                                       **stats(arrays[run, sid, algorithm, kind, phase])))
    anchors, across, spans, algorithm_pairs = {}, [], [], []
    for sid in ids:
        for algorithm in ALGORITHMS:
            ratios = [vectors[r, sid, algorithm]["size"] for r in RUNS]
            require(len(set(ratios)) == 1, "Ratio changed across runs")
            anchor = {field: statistics.median(vectors[r, sid, algorithm][field] for r in RUNS) for field in METRICS}
            anchors[sid, algorithm] = anchor
            for field in ("compress", "decompress", "memory"):
                values = [vectors[r, sid, algorithm][field] for r in RUNS]
                record = dict(sample_id=sid, stratum=strata[sid], algorithm=algorithm, metric=field,
                              unit="bytes" if field == "memory" else "ms", run_ids=list(RUNS), **stats(values))
                across.append(record)
                if field == "memory":
                    span = log_ratio(max(values), min(values))
                    limit = verification.CRITERIA["epsilon"] / (2 * verification.CRITERIA["w_memory_max"])
                    spans.append(dict(sample_id=sid, stratum=strata[sid], algorithm=algorithm, log_span=span,
                                      limit=limit, satisfied=span <= limit))
            for phase in verification.PHASES:
                values = [statistics.median(arrays[r, sid, algorithm, "memory", phase]) for r in RUNS]
                across.append(dict(sample_id=sid, stratum=strata[sid], algorithm=algorithm, metric="memory_" + phase,
                                   unit="bytes", run_ids=list(RUNS), **stats(values)))
        for left, right in combinations(ALGORITHMS, 2):
            lvals = [vectors[r, sid, left]["memory"] for r in RUNS]
            rvals = [vectors[r, sid, right]["memory"] for r in RUNS]
            differences = [a - b for a, b in zip(lvals, rvals)]
            signs = [(v > 0) - (v < 0) for v in differences]
            algorithm_pairs.append(dict(sample_id=sid, stratum=strata[sid], left=left, right=right, run_ids=list(RUNS),
                                        left_values_bytes=lvals, right_values_bytes=rvals, differences_bytes=differences,
                                        signs=signs, tied_by_run=[v == 0 for v in differences], sign_consistent=len(set(signs)) == 1,
                                        ranges_overlap=max(min(lvals), min(rvals)) <= min(max(lvals), max(rvals))))
    labels, indexed, comparisons, anchor_regrets, regrets, arithmetic = [], {}, [], [], [], []
    for sid in ids:
        reference = {a: anchors[sid, a] for a in ALGORITHMS}
        for mode in MODES:
            weights = verification.WEIGHTS[mode]
            chosen_reference = select(reference, weights)
            identity = dict(sample_id=sid, stratum=strata[sid], mode=mode)
            labels.append(dict(**identity, scenario="reference", run_id=None, **chosen_reference))
            scenario_metrics = {}
            for run in RUNS:
                measured = {a: vectors[run, sid, a] for a in ALGORITHMS}
                for scenario in SCENARIOS:
                    current = {a: {field: (reference[a][field] if
                                          (scenario == "memory_only" and field in ("compress", "decompress")) or
                                          (scenario == "timing_only" and field == "memory") else measured[a][field])
                                   for field in METRICS} for a in ALGORITHMS}
                    selection = select(current, weights)
                    scenario_metrics[scenario, run] = current
                    indexed[sid, mode, scenario, run] = selection
                    labels.append(dict(**identity, scenario=scenario, run_id=run, **selection))
                    predicted = selection["score_" + chosen_reference["best_algorithm"]]
                    anchor_regrets.append(dict(**identity, scenario=scenario, target_run_id=run,
                                               selected_algorithm=chosen_reference["best_algorithm"], target_best_algorithm=selection["best_algorithm"],
                                               predicted_score=predicted, oracle_best_score=selection["best_score"], regret=predicted - selection["best_score"]))
                official = select(measured, OFFICIAL_WEIGHTS[mode])
                without = select(measured, {**weights, "memory": 0})
                joint = indexed[sid, mode, "joint", run]
                benefit = weights["memory"] * log_ratio(measured[without["best_algorithm"]]["memory"], measured[joint["best_algorithm"]]["memory"])
                comparisons.append(dict(**identity, run_id=run, official_v2=official, candidate_without_memory=without,
                                        candidate_joint_algorithm=joint["best_algorithm"], weighted_memory_benefit=benefit,
                                        benefit_exceeds_delta=benefit > verification.CRITERIA["delta"]))
            for scenario in SCENARIOS:
                for source in RUNS:
                    source_label = indexed[sid, mode, scenario, source]["best_algorithm"]
                    for target in RUNS:
                        selection = indexed[sid, mode, scenario, target]
                        predicted = selection["score_" + source_label]
                        regret = predicted - selection["best_score"]
                        require(math.isfinite(regret) and regret >= 0 and (source != target or regret == 0), "Invalid directional regret")
                        regrets.append(dict(**identity, scenario=scenario, source_run_id=source, target_run_id=target,
                                            selected_algorithm=source_label, target_best_algorithm=selection["best_algorithm"],
                                            predicted_score=predicted, oracle_best_score=selection["best_score"], regret=regret))
            terms = {a: [weights["memory"] * log_ratio(scenario_metrics["memory_only", r][a]["memory"],
                                                     min(scenario_metrics["memory_only", r][b]["memory"] for b in ALGORITHMS))
                         for r in RUNS] for a in ALGORITHMS}
            term_ranges = {a: max(v) - min(v) for a, v in terms.items()}
            max_span = max(row["log_span"] for row in spans if row["sample_id"] == sid)
            score_bound = 2 * weights["memory"] * max_span
            regret_bound = 2 * max(term_ranges.values())
            observed = max(row["regret"] for row in regrets if row["sample_id"] == sid and row["mode"] == mode and row["scenario"] == "memory_only")
            # Tolerance is ONLY for floating-point QA of the derived theorem;
            # judgment() and benefit tests always use strict original thresholds.
            within = lambda actual, bound: actual <= bound or math.isclose(actual, bound, rel_tol=1e-12, abs_tol=1e-15)
            require(within(max(term_ranges.values()), score_bound) and within(observed, regret_bound), "Memory arithmetic relation failed")
            arithmetic.append(dict(**identity, normalized_memory_terms_by_algorithm=terms, term_ranges=term_ranges,
                                   max_memory_span=max_span, score_difference_bound=score_bound, transfer_regret_bound=regret_bound,
                                   observed_max_memory_only_regret=observed, consistency_check_passed=True,
                                   floating_QA_tolerance=dict(relative=1e-12, absolute=1e-15, used_for_policy=False)))
    by_stratum = {}
    for stratum in STRATA:
        span_values = [r["log_span"] for r in spans if r["stratum"] == stratum]
        memory_values = [r["regret"] for r in regrets if r["stratum"] == stratum and r["scenario"] == "memory_only"]
        joint_values = [r["regret"] for r in regrets if r["stratum"] == stratum and r["scenario"] == "joint"]
        by_stratum[stratum] = dict(sample_count=sum(v == stratum for v in strata.values()), span_condition_count=len(span_values),
                                  max_memory_span=max(span_values), max_memory_only_regret=max(memory_values), max_joint_regret=max(joint_values),
                                  **judgment(True, span_values, memory_values, joint_values))
    decision = judgment(True, [r["log_span"] for r in spans], [r["regret"] for r in regrets if r["scenario"] == "memory_only"],
                        [r["regret"] for r in regrets if r["scenario"] == "joint"])
    benefit_conditions = []
    for sid in ids:
        for mode in MODES:
            values = [r["weighted_memory_benefit"] for r in comparisons if r["sample_id"] == sid and r["mode"] == mode]
            benefit_conditions.append(dict(sample_id=sid, stratum=strata[sid], mode=mode, run_ids=list(RUNS),
                                           weighted_memory_benefits=values, all_runs_exceed_delta=all(v > verification.CRITERIA["delta"] for v in values)))
    scenario_summary = []
    for stratum in STRATA:
        for scenario in SCENARIOS:
            selected = [r for r in regrets if r["stratum"] == stratum and r["scenario"] == scenario]
            matches = [r["selected_algorithm"] == r["target_best_algorithm"] for r in selected]
            scenario_summary.append(dict(stratum=stratum, scenario=scenario, transfer_count=len(selected), max_regret=max(r["regret"] for r in selected),
                                         mean_regret=statistics.mean(r["regret"] for r in selected), exact_label_match_count=sum(matches),
                                         exact_label_match_rate=sum(matches) / len(matches), diagonal_pairs_included=True))
    return dict(representatives=representatives, phase_diagnostics=phases, representative_across_runs=across,
                reference_anchors=[dict(sample_id=s, stratum=strata[s], algorithm=a, **anchors[s, a]) for s in ids for a in ALGORITHMS],
                memory_spans=spans, memory_algorithm_pairs=algorithm_pairs, candidate_labels=labels, transfer_regrets=regrets,
                anchor_regrets=anchor_regrets, official_and_nonmemory_comparisons=comparisons, memory_benefit_conditions=benefit_conditions,
                arithmetic_checks=arithmetic, scenario_summary=scenario_summary, decision=dict(**decision, by_stratum=by_stratum),
                counts=dict(samples=len(ids), representatives=len(representatives), phase_groups=len(phases), candidate_labels=len(labels),
                            transfer_regrets=len(regrets), anchor_regrets=len(anchor_regrets), comparisons=len(comparisons)),
                observed_memory_benefit_condition_count=sum(r["all_runs_exceed_delta"] for r in benefit_conditions))


def _evidence_names():
    return {*verification.IMMUTABLE, "metadata.json", *(name for run in RUNS for name in
            (f"run_{run:02d}_stdout.txt", f"run_{run:02d}_stderr.txt", f"run_{run:02d}/metadata.json",
             *(f"run_{run:02d}/{n}" for n in verification.ARTIFACTS)))}


def _recheck(directory, evidence, sources):
    for name, checksum in evidence.items():
        require(verification.digest((directory / name).read_bytes()) == checksum, f"Evidence changed during analysis/publication: {name}")
    for path, checksum in sources.items():
        require(verification.digest(Path(path).read_bytes()) == checksum, f"Source changed during analysis/publication: {path}")
    require(not (directory / ".active_run.json").exists(), "Active claim appeared during analysis/publication")
    require({p.name for p in directory.iterdir() if p.is_dir() and p.name.startswith("run_")} ==
            {f"run_{run:02d}" for run in RUNS}, "Run inventory changed during analysis/publication")


def analyze(directory: Path) -> dict:
    require(sys.dont_write_bytecode, "Run analysis with python -B")
    directory = Path(directory).resolve()
    script = Path(__file__).resolve()
    source_paths = [script, Path(verification.__file__).resolve(), *(verification.ROOT / n for n in verification.SOURCES)]
    sources = {str(p): verification.digest(p.read_bytes()) for p in source_paths}
    audited = verification.audit(directory)
    require(audited.get("audit_passed") is True and audited.get("measurement_status") == "validation_only"
            and audited.get("score_inclusion") is False and audited.get("design_id") == verification.DESIGN, "Audit did not validate evidence")
    require(audited["audit_script_sha256"] == sources[str(Path(verification.__file__).resolve())], "Audit code changed")
    require(set(audited["input_sha256"]) == _evidence_names(), "Incomplete audited evidence manifest")
    snapshots = {}
    for name, checksum in audited["input_sha256"].items():
        data = (directory / name).read_bytes()
        require(verification.digest(data) == checksum, f"Evidence changed after audit: {name}")
        snapshots[name] = data
    def table(name, fields):
        reader = csv.DictReader(io.StringIO(snapshots[name].decode("utf-8"), newline=""), strict=True)
        require(reader.fieldnames == list(fields), "Audited CSV schema mismatch")
        return list(reader)
    plan = verification.parse_json(snapshots["plan.json"])
    config = verification.parse_json((verification.ROOT / "config/experiment_config.json").read_bytes())
    verification.same(plan["candidate_weights"], verification.WEIGHTS, "Candidate weights changed")
    verification.same(plan["criteria"], verification.CRITERIA, "Criteria changed")
    expected_official = {mode: dict(compression_ratio=w["size"], compression_time=w["compress"], decompression_time=w["decompress"])
                         for mode, w in OFFICIAL_WEIGHTS.items()}
    verification.same(config["selection_modes"], expected_official, "Official comparison weights changed")
    samples = table("samples.csv", verification.SAMPLE_FIELDS)
    measurements = {r: table(f"run_{r:02d}/measurements.csv", verification.MEASUREMENT_FIELDS) for r in RUNS}
    raw = {r: {kind: table(f"run_{r:02d}/{kind}_repeats.csv", verification.MEMORY_FIELDS if kind == "memory" else verification.TIMING_FIELDS)
               for kind in ("memory", "timing")} for r in RUNS}
    calculated = _calculate(samples, measurements, raw)
    _recheck(directory, audited["input_sha256"], sources)
    return dict(schema_version=1, design_id=verification.DESIGN, attempt_id=audited["attempt_id"],
                measurement_status="validation_only", score_inclusion=False, analysis_status="completed_validation_candidate_analysis",
                technical_validity_status="independent_saved_evidence_audit_passed", analyzed_at_utc=datetime.now(timezone.utc).isoformat(),
                measurement_commit=audited["measurement_commit"], analysis_script_sha256=sources[str(script)], source_sha256=sources,
                audit=audited, samples=samples, candidate_weights=verification.WEIGHTS, official_comparison_weights=OFFICIAL_WEIGHTS,
                criteria=verification.CRITERIA, conventions=dict(anchor="median of six run representatives; not pooled raw repeats",
                memory="max of phase medians; no repeat-wise pairing of separate phase processes",
                score="weighted ln(value/minimum); log difference fallback only on intermediate ratio overflow/underflow",
                ties="exact equality; gzip,bz2,lzma,zstd order; second-best gap is zero on ties",
                transfer="all 36 directed pairs including zero diagonals for each of three run scenarios",
                ranges="closed observed ranges, not confidence intervals", cv="population standard deviation / mean",
                thresholds="original unrounded expressions; inclusive <= stability limits and strict > memory-benefit delta",
                arithmetic_QA="round-off tolerance only for theorem consistency; never used for policy or selection"),
                limitations=["Candidate calculations only; official labels/models and three-metric scoring remain unchanged.",
                             "Observed conditions do not establish scientific adoption, future error bounds or hardware generalization.",
                             "Stability satisfaction and observed memory selection benefit are separate findings.",
                             "Reference anchor is a diagnostic construct, not an observed run or external oracle.",
                             "No measurement, compression, restoration or model learning was rerun.",
                             "Audit checks saved consistency; hashes/events do not authenticate measurements or independently certify restoration."],
                **calculated)


def _csv_bytes(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, ensure_ascii=False, allow_nan=False) if isinstance(value, (list, dict)) else value
                         for key, value in row.items()})
    return stream.getvalue().encode("utf-8")


def publish(report, directory: Path, output: Path):
    """Exclusive new output directory; keep any partial publication on failure."""
    require(report["audit"].get("audit_passed") is True and report.get("score_inclusion") is False
            and report.get("analysis_status") == "completed_validation_candidate_analysis", "Cannot publish unsuccessful analysis")
    directory, output = Path(directory).resolve(), Path(output).absolute()
    _recheck(directory, report["audit"]["input_sha256"], report["source_sha256"])
    payloads = {"audit.json": (json.dumps(report["audit"], indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"),
                "candidate_labels.csv": _csv_bytes(LABEL_FIELDS, report["candidate_labels"]),
                "transfer_regrets.csv": _csv_bytes(REGRET_FIELDS, report["transfer_regrets"])}
    # Compute everything before creating a directory. A pre-existing path is
    # always refused, and failed writes are never deleted or silently retried.
    output.mkdir(exist_ok=False)
    try:
        for name, data in payloads.items():
            with (output / name).open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            require((output / name).read_bytes() == data, f"Published bytes mismatch: {name}")
        _recheck(directory, report["audit"]["input_sha256"], report["source_sha256"])
        summary = {key: value for key, value in report.items() if key not in ("candidate_labels", "transfer_regrets")}
        summary["tables"] = dict(candidate_labels=dict(file="candidate_labels.csv", rows=len(report["candidate_labels"]), fields=list(LABEL_FIELDS)),
                               transfer_regrets=dict(file="transfer_regrets.csv", rows=len(report["transfer_regrets"]), fields=list(REGRET_FIELDS)))
        summary["output_artifact_sha256"] = {name: verification.digest(data) for name, data in payloads.items()}
        summary["publication_contract"] = "Require a successful CLI/API return and absence of publication_failed.json; partial files are not a successful export."
        data = (json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        with (output / "stability_summary.json").open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        require((output / "stability_summary.json").read_bytes() == data, "Published summary bytes mismatch")
        _recheck(directory, report["audit"]["input_sha256"], report["source_sha256"])
    except BaseException as exc:
        # This directory was created by this invocation. Never put a failure
        # marker in an existing user's output path or replace partial files.
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
    parser.add_argument("--output-dir", type=Path, help="New directory for the four analysis artifacts; never overwrite")
    args = parser.parse_args(arguments)
    try:
        report = analyze(args.experiment_dir)
        if args.output_dir:
            publish(report, args.experiment_dir, args.output_dir)
            printed = dict(analysis_status=report["analysis_status"], decision=report["decision"], counts=report["counts"],
                           measurement_status="validation_only", score_inclusion=False, output_dir=str(args.output_dir.absolute()))
        else:
            printed = report
        serialized = json.dumps(printed, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    except (OSError, ValueError, KeyError, TypeError, OverflowError, csv.Error) as exc:
        parser.exit(1, f"Analysis inconclusive: {exc}\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
