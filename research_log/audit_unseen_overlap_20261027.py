"""Reconstruct recorded synthetic inputs and compare full hashes, without benchmarks.

Only trusted local Git sources at the two recorded experiment commits are loaded.
Original input hashes were not recorded: this is a reconstruction-based audit,
not a retrospective verification of original byte identities or semantic novelty.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src import unseen_manifest as paths

REVIEW = ROOT / "data/results/real_unseen/real_candidate_review_20261026_01"
DATASETS = (
    ("validation_72", "data/results", 72, "e44fea992bb6c70330e3b4de235764be36bb0b5f"),
    ("pilot_1008", "data/results/pilot_1008", 1008, "4d2d637bea96a4a1ddbbedb2c077fd0474ca8c19"),
)
SOURCES = ("src/data_generator.py", "src/experiment_runner.py", "config/experiment_config.json")
LIMITATION = (
    "Original experiments did not store input bytes or input hashes. Full SHA-256 values here "
    "are reconstructed from clean recorded Git sources, matching CPython version, seed, size "
    "and generation parameters. Original byte identity cannot independently be proven. "
    "Historical stdlib binary/source hashes were not recorded. Exact hash checks do not "
    "establish semantic novelty, anonymity, independence or evaluation readiness."
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(paths._read(path, collect=True)[2])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def normalized(data):
    return data.decode("utf-8-sig").replace("\r\n", "\n")


def historical_plan(source, generator, count, base_seed):
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_experiment_plan")
    namespace = dict(SampleSpec=SimpleNamespace, SAMPLE_SIZES=generator.SAMPLE_SIZES,
                     GENERATOR_NAMES=generator.GENERATOR_NAMES)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<trusted historical plan>", "exec"), namespace)
    return namespace["build_experiment_plan"](count, base_seed)


def validate_records(meta, rows, generator, config, count, commit):
    require(meta["git"] == {"commit_hash": commit, "worktree_dirty": False}, "Untrusted execution commit/dirty worktree")
    require(meta["python_version"] == platform.python_version() and
            meta["python_implementation"] == platform.python_implementation(), "Python runtime mismatch")
    require(meta["schema_version"] == 1 and meta["sample_count"] == len(rows) == count, "Sample coverage mismatch")
    require(meta["seed_strategy"] == "base_seed + zero_based_sample_index" and
            meta["sample_id_strategy"] == "sample_{zero_based_sample_index:06d}", "Unknown plan strategy")
    require(meta["generators"] == list(generator.GENERATOR_NAMES) and
            meta["sample_sizes"] == list(generator.SAMPLE_SIZES) == config["sample_sizes"], "Generator/size definition mismatch")
    for key, target in (("compression_settings", "compression"), ("timing", "timing"), ("feature_settings", "features")):
        require(meta[key] == config[target], f"Historical config mismatch: {key}")
    conditions = [(name, size) for size in generator.SAMPLE_SIZES for name in generator.GENERATOR_NAMES]
    for index, row in enumerate(rows):
        name, size = conditions[index % len(conditions)]
        require(row["sample_id"] == f"sample_{index:06d}" and row["generator"] == name and
                int(row["seed"]) == meta["base_seed"] + index and int(row["size"]) == size and
                int(row["file_size"]) == size, f"Sample plan mismatch at index {index}")
        require(type(json.loads(row["generation_parameters"])) is dict, "Invalid generation parameters")
    require(dict(Counter(r["generator"] for r in rows)) == meta["generator_counts"], "Generator totals mismatch")
    require(dict(Counter(r["size"] for r in rows)) == meta["size_counts"], "Size totals mismatch")


def reconstruct(meta, rows, generator, config, count, commit):
    validate_records(meta, rows, generator, config, count, commit)
    for row in rows:
        sample = generator.generate_sample(row["generator"], int(row["size"]), int(row["seed"]))
        require(sample.generator == row["generator"] and sample.seed == int(row["seed"]) and
                sample.size == len(sample.data) == int(row["size"]), f"Generated size/identity mismatch: {row['sample_id']}")
        require(sample.parameters == json.loads(row["generation_parameters"]), f"Generation parameters mismatch: {row['sample_id']}")
        yield dict(sample_id=row["sample_id"], generator=sample.generator, seed=sample.seed,
                   size=sample.size, generation_parameters=sample.parameters, input_sha256=sha(sample.data))


def compare(candidates, synthetic):
    by_hash = defaultdict(list)
    for row in synthetic:
        by_hash[row["input_sha256"]].append({k: row[k] for k in ("dataset", "sample_id", "seed", "size")})
    return [dict(candidate_id=c["candidate_id"], input_sha256=c["input_sha256"],
                 reconstructed_matches=by_hash.get(c["input_sha256"], []),
                 exclusion_reason="exact_overlap_with_reconstructed_synthetic_input" if c["input_sha256"] in by_hash else None)
            for c in candidates]


def snapshot(expected):
    result = {}
    for rel, digest in expected.items():
        value = paths._read(ROOT.joinpath(*paths._relative(rel)))[1]
        require(value == digest, f"Protected input differs: {rel}")
        result[rel] = value
    return result


def run(output):
    output = paths._no_links(Path(output).absolute())
    require(output.is_relative_to(ROOT / "data/results/real_unseen") and output.parent == ROOT / "data/results/real_unseen",
            "Use a new direct child of data/results/real_unseen")
    output.mkdir(exist_ok=False)
    try:
        expected = read(REVIEW / "protected_after.json")
        for path in REVIEW.rglob("*"):
            if path.is_file():
                expected[path.relative_to(ROOT).as_posix()] = paths._read(path)[1]
        for _, directory, _, _ in DATASETS:
            for name in ("samples.csv", "experiment_metadata.json", "compression_results.csv", "selection_labels.csv"):
                path = ROOT / directory / name
                expected[path.relative_to(ROOT).as_posix()] = paths._read(path)[1]
        for path in (Path(__file__), ROOT / "src/unseen_manifest.py", *(ROOT / p for p in SOURCES)):
            expected[path.relative_to(ROOT).as_posix()] = paths._read(path)[1]
        before = snapshot(expected)
        save(output / "protected_before.json", before)
        review = read(REVIEW / "candidate_review.json")
        raw_root = paths._root(ROOT / review["raw_root"])
        inventory_bytes = paths._read(REVIEW / "inventory.json", collect=True)[2]
        inventory, candidates, issues, signatures = paths._scan(raw_root, inventory_bytes)
        require(len(candidates) == 60 and not issues and all(not c["issues"] for c in candidates), "Reviewed candidates have unresolved issues")
        original_draft = read(REVIEW / "draft/manifest.json")
        require(original_draft["status"] == "draft" and original_draft["selected_ids"] == [], "Expected unselected draft")
        synthetic, evidence = [], []
        for dataset, directory, count, commit in DATASETS:
            print(f"Reconstructing {dataset}", flush=True)
            meta = read(ROOT / directory / "experiment_metadata.json")
            for filename, record in meta["output_files"].items():
                require(filename in ("samples.csv", "compression_results.csv"), "Unexpected experiment output")
                require(paths._read(ROOT / directory / filename)[1] == record["sha256"], "Recorded experiment output hash mismatch")
            require(set(meta["output_files"]) == {"samples.csv", "compression_results.csv"}, "Missing recorded output hash")
            source_records = {}
            for rel in SOURCES:
                data = git("show", f"{commit}:{rel}")
                target = output / "historical_sources" / dataset / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
                source_records[rel] = dict(git_blob_sha1=git("rev-parse", f"{commit}:{rel}").decode().strip(),
                                           sha256=sha(data), snapshot=target.relative_to(output).as_posix(),
                                           current_text_equal_ignoring_crlf=normalized(data) == normalized((ROOT / rel).read_bytes()))
            require(source_records["src/data_generator.py"]["current_text_equal_ignoring_crlf"], "Generator source drift")
            require(source_records["src/experiment_runner.py"]["current_text_equal_ignoring_crlf"], "Runner source drift")
            # The original runner's plan is reviewed and snapshotted, never imported:
            # importing it would load compression/feature modules unnecessarily.
            runner_ast = ast.parse((output / source_records["src/experiment_runner.py"]["snapshot"]).read_bytes())
            require(any(isinstance(n, ast.FunctionDef) and n.name == "build_experiment_plan" for n in runner_ast.body), "Missing historical plan")
            config = read(output / source_records["config/experiment_config.json"]["snapshot"])
            for key, value in config.items():
                require(read(ROOT / "config/experiment_config.json")[key] == value, f"Current historical config field differs: {key}")
            module_name = f"_trusted_overlap_generator_{dataset}"
            spec = importlib.util.spec_from_file_location(module_name, output / source_records["src/data_generator.py"]["snapshot"])
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                rows = list(csv.DictReader(io.StringIO((ROOT / directory / "samples.csv").read_text(encoding="utf-8"))))
                plan = historical_plan((output / source_records["src/experiment_runner.py"]["snapshot"]).read_bytes(),
                                       module, count, meta["base_seed"])
                require(len(plan) == len(rows) and all(
                    spec.sample_id == row["sample_id"] and spec.generator == row["generator"] and
                    spec.seed == int(row["seed"]) and spec.size == int(row["size"])
                    for spec, row in zip(plan, rows)), "Historical plan differs from recorded samples")
                generated = []
                with (output / f"{dataset}_hashes.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
                    for row in reconstruct(meta, rows, module, config, count, commit):
                        row["dataset"] = dataset
                        stream.write(json.dumps(row, sort_keys=True) + "\n")
                        generated.append(row)
            finally:
                del sys.modules[module_name]
            synthetic.extend(generated)
            evidence.append(dict(dataset=dataset, experiment_metadata=f"{directory}/experiment_metadata.json",
                                 recorded_commit=commit, recorded_worktree_dirty=meta["git"]["worktree_dirty"],
                                 python_version=meta["python_version"], python_implementation=meta["python_implementation"],
                                 recorded_os=meta["operating_system"], current_os=platform.platform(),
                                 base_seed=meta["base_seed"], regenerated_count=len(generated),
                                 all_generation_parameters_match=True, sources=source_records,
                                 packages_used_for_generation="Python stdlib only; external package versions not used"))
        checks = compare(candidates, synthetic)
        save(output / "candidate_overlap.json", checks)
        save(output / "reconstruction_evidence.json", evidence)
        _, current, current_issues, current_signatures = paths._scan(raw_root, inventory_bytes)
        require((current, current_issues, current_signatures) == (candidates, issues, signatures), "Candidates changed during audit")
        after = snapshot(expected)
        save(output / "protected_after.json", after)
        require(before == after, "Protected inputs changed")
        overlap_count = sum(bool(c["reconstructed_matches"]) for c in checks)
        digest_counts = Counter(r["input_sha256"] for r in synthetic)
        save(output / "synthetic_duplicate_hashes.json", {h: n for h, n in digest_counts.items() if n > 1})
        artifacts = {p.relative_to(output).as_posix(): paths._read(p)[1] for p in output.rglob("*") if p.is_file() and p.suffix != ".pyc"}
        result = dict(schema_version=1, status="reconstruction_audit_completed", completed_at_utc=datetime.now(timezone.utc).isoformat(),
                      execution_git_head=git("rev-parse", "HEAD").decode().strip(),
                      auditor_sha256=sha(Path(__file__).read_bytes()), corpus_id=inventory["corpus_id"],
                      inventory_path=(REVIEW / "inventory.json").relative_to(ROOT).as_posix(), inventory_sha256=sha(inventory_bytes),
                      reconstructed_inputs=len(synthetic), reconstructed_unique_hashes=len(digest_counts),
                      candidates_checked=len(checks), candidate_exact_overlaps=overlap_count,
                      candidates_without_exact_reconstructed_overlap=len(checks)-overlap_count,
                      protected_files_unchanged=len(before),
                      unseen_overlap_audit="completed_against_reconstructed_synthetic_inputs",
                      original_byte_identity_independently_verified=False, limitation=LIMITATION,
                      stdlib_random=dict(path=random.__file__, sha256=sha(Path(random.__file__).read_bytes())),
                      corpus_frozen=False, selected_files=0, evaluation_ready=False,
                      features_predictions_benchmarks_training_executed=False,
                      artifact_sha256=artifacts)
        save(output / "summary.json", result)
        print(json.dumps({k: v for k, v in result.items() if k != "artifact_sha256"}, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        save(output / "failure.json", dict(status="failed_incomplete", error=repr(exc), traceback=traceback.format_exc(),
                                          evaluation_ready=False, limitation=LIMITATION))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output_dir))
