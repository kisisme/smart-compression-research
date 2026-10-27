"""Independently check saved audit links/counts/hashes; no input regeneration."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/results/real_unseen/synthetic_overlap_20261027_01"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def check(ok, label):
    if not ok:
        raise ValueError(label)


def main():
    summary = read(OUT / "summary.json")
    check(summary["status"] == "reconstruction_audit_completed" and not (OUT / "failure.json").exists(), "Completion state")
    for rel, digest in summary["artifact_sha256"].items():
        check(sha((OUT / rel).read_bytes()) == digest, f"Artifact hash: {rel}")
    before, after = read(OUT / "protected_before.json"), read(OUT / "protected_after.json")
    check(before == after, "Preservation snapshots")
    for rel, digest in before.items():
        check(sha((ROOT / rel).read_bytes()) == digest, f"Protected file: {rel}")
    inventory = read(ROOT / summary["inventory_path"])
    check(sha((ROOT / summary["inventory_path"]).read_bytes()) == summary["inventory_sha256"], "Inventory hash")
    evidence = read(OUT / "reconstruction_evidence.json")
    indexes = []
    by_hash = defaultdict(list)
    for e in evidence:
        rows = [json.loads(line) for line in (OUT / f"{e['dataset']}_hashes.jsonl").read_text(encoding="utf-8").splitlines()]
        meta_path = ROOT / e["experiment_metadata"]
        meta = read(meta_path)
        check(len(rows) == e["regenerated_count"] == meta["sample_count"], "Reconstruction coverage")
        check(len({r["sample_id"] for r in rows}) == len(rows), "Duplicate sample identifier")
        for index, row in enumerate(rows):
            check(row["dataset"] == e["dataset"] and row["sample_id"] == f"sample_{index:06d}" and
                  row["seed"] == meta["base_seed"] + index, "Index identities")
            check(len(row["input_sha256"]) == 64 and len(bytes.fromhex(row["input_sha256"])) == 32, "Full hash encoding")
            by_hash[row["input_sha256"]].append({k: row[k] for k in ("dataset", "sample_id", "seed", "size")})
        for rel, source in e["sources"].items():
            data = (OUT / source["snapshot"]).read_bytes()
            check(sha(data) == source["sha256"], "Historical source hash")
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            check(blob == source["git_blob_sha1"], "Historical Git blob hash")
            check(data == subprocess.check_output(["git", "show", f"{e['recorded_commit']}:{rel}"], cwd=ROOT), "Pinned Git source")
        indexes.extend(rows)
    matches = read(OUT / "candidate_overlap.json")
    review_dir = (ROOT / summary["inventory_path"]).parent
    raw = ROOT / read(review_dir / "candidate_review.json")["raw_root"]
    candidates = {r["candidate_id"]: r for r in inventory["candidates"]}
    check(len(matches) == len(candidates) == summary["candidates_checked"], "Candidate coverage")
    check({r["candidate_id"] for r in matches} == set(candidates), "Candidate IDs")
    for match in matches:
        row = candidates[match["candidate_id"]]
        check(match["input_sha256"] == row["input_sha256"] == sha((raw / row["relative_path"]).read_bytes()), "Candidate bytes")
        expected = by_hash.get(row["input_sha256"], [])
        check(match["reconstructed_matches"] == expected, "Full overlap comparison")
        check(match["exclusion_reason"] == ("exact_overlap_with_reconstructed_synthetic_input" if expected else None), "Exclusion reason")
    overlap = sum(bool(r["reconstructed_matches"]) for r in matches)
    check(overlap == summary["candidate_exact_overlaps"], "Overlap total")
    check(len(indexes) == summary["reconstructed_inputs"] and len(by_hash) == summary["reconstructed_unique_hashes"], "Synthetic totals")
    counts = Counter(r["input_sha256"] for r in indexes)
    check(read(OUT / "synthetic_duplicate_hashes.json") == {h: n for h, n in counts.items() if n > 1}, "Duplicate index")
    check(not summary["evaluation_ready"] and not summary["corpus_frozen"] and summary["selected_files"] == 0 and
          not summary["original_byte_identity_independently_verified"], "Scope limitations")
    result = dict(status="saved_reconstruction_audit_verified", verified_at_utc=datetime.now(timezone.utc).isoformat(),
                  verifier_sha256=sha(Path(__file__).read_bytes()), summary_sha256=sha((OUT / "summary.json").read_bytes()),
                  reconstructed_inputs=len(indexes), candidates_checked=len(matches), candidate_exact_overlaps=overlap,
                  protected_files_unchanged=len(before),
                  scope="Independent saved-artifact and comparison verification; no second generation or proof of historical original bytes.")
    with (OUT / "verification.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
