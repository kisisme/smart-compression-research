"""Independent, byte-only checks of the initial real-file candidate draft."""
from collections import Counter
from datetime import datetime, timezone
import ast
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/results/real_unseen/real_candidates_20261026_01"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    acquisition = read(OUT / "acquisition.json")
    raw = ROOT / acquisition["raw_root"]
    inventory = read(OUT / "inventory.json")
    manifest = read(OUT / "draft/manifest.json")
    plan = read(OUT / "collection_plan_snapshot.json")
    review = read(ROOT / "research_log/unseen_source_review_20261026.json")
    before, after = read(OUT / "protected_before.json"), read(OUT / "protected_after.json")
    assert before == after
    assert all(digest((ROOT / p).read_bytes()) == h for p, h in before.items())
    assert not acquisition["errors"] and read(OUT / "draft_cli.json")["returncode"] == 0
    assert digest((ROOT / "research_log/unseen_collection_plan_20261026.json").read_bytes()) == acquisition["plan_sha256"]
    assert digest((ROOT / "research_log/collect_unseen_candidates_20261026.py").read_bytes()) == acquisition["collector_sha256"]
    assert manifest["status"] == "draft" and manifest["selected_ids"] == []
    assert not manifest["evaluation_ready"] and manifest["unseen_overlap_audit"] == "not_performed"
    assert manifest["source_sha256"] == digest((ROOT / "src/unseen_manifest.py").read_bytes())
    assert not manifest["group_issues"]
    assert read(OUT / "draft/inventory_snapshot.json") == inventory
    assert (OUT / "draft/inventory_snapshot.json").read_bytes() == (OUT / "inventory.json").read_bytes()
    for p, h in manifest["artifact_sha256"].items():
        assert digest((OUT / "draft" / p).read_bytes()) == h
    by_path = {r["raw_relative_path"]: r for r in acquisition["records"]}
    expected = {g["origin_group_id"] + "/" + f["path"]: (g, f) for g in plan["groups"] for f in g["files"]}
    candidates = inventory["candidates"]
    assert set(expected) == {r["relative_path"] for r in candidates}
    manifest_by_id = {r["candidate_id"]: r for r in manifest["candidates"]}
    triage, file_hashes, sizes = [], [], []
    for row in candidates:
        relative = row["relative_path"]
        data = (raw / relative).read_bytes()
        group, planned = expected[relative]
        actual_hash = digest(data)
        blob_hash = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        assert len(data) == planned["size"] == row["original_size"] == by_path[relative]["size"]
        assert blob_hash == planned["git_blob_sha1"] == by_path[relative]["git_blob_sha1"]
        assert actual_hash == row["input_sha256"] == by_path[relative]["input_sha256"]
        m = manifest_by_id[row["candidate_id"]]
        assert m["input_sha256"] == actual_hash and m["exact_duplicate_of"] is None
        assert m["sample_id"] == "uf_" + actual_hash and m["selection_status"] == "candidate"
        assert set(m["issues"]) == {"review_not_approved", "review_evidence_incomplete"}
        assert row["rights_review_status"] == row["privacy_review_status"] == "pending"
        assert row["source_version"] == "git:" + group["commit"] and row["reviewed_at_utc"] is None
        assert 16384 <= len(data) <= 1048576
        item = {"candidate_id": row["candidate_id"], "format_check": "passed", "content_review": "pending"}
        if row["format"] == "binary":
            assert len(data) >= 100 and struct.unpack(">i", data[:4])[0] == 9994
            assert struct.unpack(">i", data[24:28])[0] * 2 == len(data)
            assert struct.unpack("<i", data[28:32])[0] == 1000
            item["format_check_method"] = "Shapefile magic, declared file length and version; no geometric statistics"
        else:
            text = data.decode("utf-8")
            if row["format"] == "python":
                ast.parse(text, filename=relative)
            elif row["format"] == "json":
                assert isinstance(json.loads(text), dict)
            # Triage is deliberately insufficient for approval. Store only categories and line numbers.
            patterns = {
                "email_like": r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                "private_ipv4_like": r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b",
                "private_key_header": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                "home_path_like": r"(?:[A-Za-z]:\\Users\\|/home/|/Users/)",
                "license_notice_like": r"(?i)copyright|SPDX-License-Identifier|licensed under|redistribut"}
            item["triage_flag_lines"] = {name: [i for i, line in enumerate(text.splitlines(), 1) if re.search(pattern, line)]
                                         for name, pattern in patterns.items()}
        triage.append(item)
        file_hashes.append(actual_hash)
        sizes.append(len(data))
    assert len(file_hashes) == len(set(file_hashes))
    licenses = []
    for group in review["groups"]:
        relative = "notices/" + group["origin_group_id"] + "/" + Path(group["license_path"]).name
        data = (raw / relative).read_bytes()
        blob_hash = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        assert blob_hash == group["expected_license_blob_sha1"]
        assert digest(data) == by_path[relative]["input_sha256"]
        licenses.append(dict(origin_group_id=group["origin_group_id"], input_sha256=digest(data), git_blob_sha1=blob_hash))
    actual_raw = {p.relative_to(raw).as_posix() for p in raw.rglob("*") if p.is_file()}
    assert actual_raw == set(by_path)
    ignored = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, text=True, capture_output=True,
                             input="\n".join((raw / p).relative_to(ROOT).as_posix() for p in sorted(actual_raw)) + "\n")
    assert ignored.returncode == 0 and len(ignored.stdout.splitlines()) == len(actual_raw)
    by_format = {fmt: sum(r["format"] == fmt for r in candidates) for fmt in manifest["plan"]["formats"]}
    groups = dict(sorted(Counter(r["origin_group_id"] for r in candidates).items()))
    assert max(groups.values()) <= 5
    result = dict(status="initial_partial_draft_verified", verified_at_utc=datetime.now(timezone.utc).isoformat(),
                  execution_git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                  verifier_sha256=digest(Path(__file__).read_bytes()), python=sys.version,
                  candidates=len(candidates), by_format=by_format, by_origin_group=groups,
                  distinct_origin_groups=len(groups), format_origin_groups={fmt: len({r["origin_group_id"] for r in candidates if r["format"] == fmt}) for fmt in by_format},
                  total_candidate_bytes=sum(sizes), minimum_bytes=min(sizes), maximum_bytes=max(sizes),
                  exact_duplicate_files=len(file_hashes) - len(set(file_hashes)), license_notices=licenses,
                  git_ignored_raw_files=len(actual_raw), protected_files_unchanged=len(before),
                  shortfall_by_format={fmt: 10 - n for fmt, n in by_format.items()},
                  minimum_origin_group_shortfall=max(0, 12 - len(groups)),
                  rights_pending=len(candidates), privacy_pending=len(candidates), selected_files=0,
                  evaluation_ready=False, unseen_overlap_audit="not_performed", research_experiments_run=False,
                  triage_caveat="Pattern/format triage only; no full rights/privacy or derivative review and no inference of safety from absent flags.",
                  content_triage=triage)
    destination = OUT / "verification.json"
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("content_triage", "license_notices", "python")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
