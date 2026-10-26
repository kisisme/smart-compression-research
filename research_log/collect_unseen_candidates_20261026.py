"""One-off acquisition of pinned original files; never imports research engines.

Run from the project root. A new timestamped path is required for every attempt.
All rights/privacy decisions remain pending for an explicit content review.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "research_log/unseen_collection_plan_20261026.json"


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def download(url, target, expected_size=None, expected_blob=None):
    # Never decode or re-encode downloaded originals. Keep HTTP entity bytes.
    req = Request(url, headers={"User-Agent": "smart-compression-research-source-collection/1",
                               "Accept-Encoding": "identity"})
    started = utc()
    with urlopen(req, timeout=40) as response:
        final_url = response.geturl()
        if urlparse(final_url).scheme != "https" or urlparse(final_url).hostname != "raw.githubusercontent.com":
            raise ValueError("Unexpected download redirect")
        if response.headers.get("Content-Encoding", "identity") != "identity":
            raise ValueError("Unexpected HTTP content encoding")
        data = response.read(1048577)
        if len(data) > 1048576:
            raise ValueError("Download exceeds one MiB")
        headers = {key: response.headers.get(key) for key in ("ETag", "Last-Modified", "Content-Type", "Content-Length")}
    if expected_size is not None and len(data) != expected_size:
        raise ValueError("Pinned Git tree size mismatch")
    git_hash = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
    if expected_blob is not None and git_hash != expected_blob:
        raise ValueError("Pinned Git blob hash mismatch")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
    if target.read_bytes() != data:
        raise ValueError("Saved bytes differ from HTTP bytes")
    return dict(url=url, final_url=final_url, started_at_utc=started, acquired_at_utc=utc(),
                headers=headers, size=len(data), input_sha256=sha(data), git_blob_sha1=git_hash)


def hashes(paths):
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -B research_log/collect_unseen_candidates_20261026.py <new-corpus-id>")
    corpus_id = sys.argv[1]
    if not corpus_id.startswith("real_candidates_") or not all(c.isalnum() or c == "_" for c in corpus_id):
        raise ValueError("Expected safe timestamped corpus ID")
    plan_bytes = PLAN.read_bytes()
    plan = json.loads(plan_bytes)
    old_evidence = json.loads((ROOT / "research_log/unseen_evaluation_design_v1_checks.json").read_bytes())
    protected = set(old_evidence["protected_before"]) | {
        "src/unseen_manifest.py", "tests/test_unseen_manifest.py", "tests/validate_unseen_manifest.py",
        "research_protocol_v2.md", "research_log/unseen_evaluation_design_v1.md"}
    before = hashes(protected)
    baseline_mismatch = [p for p, h in old_evidence["protected_before"].items() if before[p] != h]
    if baseline_mismatch:
        raise ValueError("Pre-existing protected files differ from planning evidence: " + repr(baseline_mismatch))
    raw = ROOT / "data/raw/real_unseen" / corpus_id
    out = ROOT / "data/results/real_unseen" / corpus_id
    if raw.exists() or out.exists():
        raise ValueError("Refusing existing acquisition paths")
    raw.mkdir(parents=True)
    out.mkdir(parents=True)
    save(out / "protected_before.json", before)
    save(out / "collection_plan_snapshot.json", plan)
    records, errors, candidates = [], [], []
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    jobs = []
    for group in plan["groups"]:
        base = f"https://raw.githubusercontent.com/{group['repo']}/{group['commit']}/"
        license_dest = raw / "notices" / group["origin_group_id"] / Path(group["license_path"]).name
        jobs.append((group, None, base + quote(group["license_path"], safe="/"), license_dest))
        for index, item in enumerate(group["files"], 1):
            relative = group["origin_group_id"] + "/" + item["path"]
            jobs.append((group, (index, item, relative), base + quote(item["path"], safe="/"), raw / relative))
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download, url, target,
                                   item[1]["size"] if item else None,
                                   item[1]["git_blob_sha1"] if item else None): (group, item, url, target)
                   for group, item, url, target in jobs}
        for future in as_completed(futures):
            group, item, url, target = futures[future]
            try:
                record = future.result()
                record.update(origin_group_id=group["origin_group_id"], kind="candidate" if item else "license_notice",
                              raw_relative_path=target.relative_to(raw).as_posix())
                records.append(record)
                if item:
                    index, source, relative = item
                    candidates.append(dict(
                        candidate_id=f"{group['origin_group_id']}_{index:02d}", relative_path=relative,
                        format=group["format"], origin_group_id=group["origin_group_id"],
                        source_locator=f"https://github.com/{group['repo']}/blob/{group['commit']}/{source['path']}",
                        source_version="git:" + group["commit"], acquired_at_utc=record["acquired_at_utc"],
                        license_id=group["license_id"], license_evidence=group["license_url"],
                        is_precompressed=False, derivative_of=None, rights_review_status="pending",
                        privacy_review_status="pending", reviewed_at_utc=None, exclusion_reason="",
                        original_filename=Path(source["path"]).name, original_size=record["size"],
                        input_sha256=record["input_sha256"]))
            except Exception as error:
                errors.append(dict(url=url, origin_group_id=group["origin_group_id"],
                                   error_type=type(error).__name__, error=str(error), at_utc=utc()))
    candidates.sort(key=lambda row: row["candidate_id"])
    records.sort(key=lambda row: row["raw_relative_path"])
    inventory = dict(inventory_version=1, corpus_id=corpus_id, data_kind="research_candidate", candidates=candidates)
    save(out / "inventory.json", inventory)
    save(out / "acquisition.json", dict(
        status="downloaded_pending_reviews" if not errors else "partial_download_with_errors",
        started_git_head=head, completed_at_utc=utc(), plan_sha256=sha(plan_bytes),
        collector_sha256=sha(Path(__file__).read_bytes()), python=sys.version,
        raw_root=raw.relative_to(ROOT).as_posix(), output_root=out.relative_to(ROOT).as_posix(),
        records=records, errors=errors, rights_review="pending", privacy_review="pending",
        evaluation_ready=False, source_group_independence="provisional_repository_grouping",
        unseen_overlap_audit="not_performed"))
    command = [sys.executable, "-B", "-m", "src.unseen_manifest", "draft", "--root", str(raw),
               "--inventory", str(out / "inventory.json"), "--output-dir", str(out / "draft")]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    save(out / "draft_cli.json", dict(command=command, returncode=result.returncode,
                                      stdout=result.stdout, stderr=result.stderr, completed_at_utc=utc()))
    after = hashes(protected)
    save(out / "protected_after.json", after)
    save(out / "preservation_check.json", dict(protected_files=len(before), unchanged=before == after,
        legacy_reference_unchanged=not baseline_mismatch, cli_passed=result.returncode == 0))
    print(json.dumps(dict(corpus_id=corpus_id, candidates=len(candidates), downloads=len(records),
                          errors=len(errors), draft_returncode=result.returncode,
                          protected_unchanged=before == after, output=out.relative_to(ROOT).as_posix())))
    if before != after or result.returncode or errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
