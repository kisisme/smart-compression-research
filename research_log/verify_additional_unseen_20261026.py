"""Independently check the supplemental originals and combined draft, without ML."""
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/results/real_unseen/real_candidates_20261026_02"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def check_font(data):
    assert data[:4] == b"\0\1\0\0" and len(data) >= 12
    tables = struct.unpack(">H", data[4:6])[0]
    assert 12 + 16 * tables <= len(data)
    tags = set()
    for index in range(tables):
        tag, _, offset, length = struct.unpack(">4sIII", data[12 + 16 * index:28 + 16 * index])
        assert offset + length <= len(data)
        assert tag not in tags
        tags.add(tag)
    assert {b"head", b"maxp", b"glyf", b"loca", b"name"} <= tags


def triage_text(text):
    patterns = {
        "email_like": r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "home_path_like": r"(?:[A-Za-z]:\\Users\\|/home/|/Users/)",
        "private_ipv4_like": r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b",
        "private_key_header": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"}
    return {name: [i for i, line in enumerate(text.splitlines(), 1) if re.search(pattern, line)] for name, pattern in patterns.items()}


def main():
    acquisition = read(OUT / "acquisition.json")
    raw = ROOT / acquisition["raw_root"]
    inventory, added = read(OUT / "inventory.json"), read(OUT / "additional_inventory.json")
    plan = read(OUT / "collection_plan_snapshot.json")
    manifest = read(OUT / "draft/manifest.json")
    before, after = read(OUT / "protected_before.json"), read(OUT / "protected_after.json")
    assert before == after and all(sha((ROOT / p).read_bytes()) == h for p, h in before.items())
    assert not acquisition["errors"] and acquisition["status"] == "downloaded_pending_review"
    assert sha((ROOT / "research_log/collect_additional_unseen_20261026.py").read_bytes()) == acquisition["collector_sha256"]
    assert sha((ROOT / "research_log/unseen_additional_collection_plan_20261026.json").read_bytes()) == acquisition["plan_sha256"]
    assert read(OUT / "draft_cli.json")["returncode"] == 0
    assert manifest["status"] == "draft" and not manifest["evaluation_ready"]
    assert manifest["selected_ids"] == [] and manifest["unseen_overlap_audit"] == "not_performed"
    assert manifest["group_issues"] == []
    assert sha((ROOT / "src/unseen_manifest.py").read_bytes()) == manifest["source_sha256"]
    assert (OUT / "inventory.json").read_bytes() == (OUT / "draft/inventory_snapshot.json").read_bytes()
    for name, h in manifest["artifact_sha256"].items():
        assert sha((OUT / "draft" / name).read_bytes()) == h
    records = {r["raw_relative_path"]: r for r in acquisition["records"]}
    assert len(records) == len(acquisition["records"])
    actual_files = {p.relative_to(raw).as_posix() for p in raw.rglob("*") if p.is_file()}
    assert actual_files == set(records)
    for relative, record in records.items():
        data = (raw / relative).read_bytes()
        assert len(data) == record["size"] and sha(data) == record["input_sha256"]
        if "git_blob_sha1" in record:
            assert blob(data) == record["git_blob_sha1"]
        if record["kind"] == "prior_byte_copy":
            assert data == (ROOT / record["prior_relative_path"]).read_bytes()
    original = read(ROOT / "data/results/real_unseen" / plan["base_collection"] / "inventory.json")
    rows, new_rows = inventory["candidates"], added["candidates"]
    old_by_id = {r["candidate_id"]: r for r in original["candidates"]}
    new_by_id = {r["candidate_id"]: r for r in new_rows}
    manifest_by_id = {r["candidate_id"]: r for r in manifest["candidates"]}
    assert set(old_by_id).isdisjoint(new_by_id)
    assert len(rows) == len(manifest_by_id) == 60 and len(new_rows) == 30
    assert {r["candidate_id"] for r in rows} == set(old_by_id) | set(new_by_id)
    github_files = {f["candidate_id"]: (g, f) for g in plan["github_groups"] for f in g["files"]}
    uci_groups = {g["origin_group_id"]: g for g in plan["uci_groups"]}
    triage, sizes, hashes = [], [], []
    for row in rows:
        cid, relative = row["candidate_id"], row["relative_path"]
        data = (raw / relative).read_bytes()
        assert len(data) == row["original_size"] and sha(data) == row["input_sha256"]
        assert 16384 <= len(data) <= 1048576 and not row["is_precompressed"]
        assert row["rights_review_status"] == row["privacy_review_status"] == "pending" and row["reviewed_at_utc"] is None
        m = manifest_by_id[cid]
        assert m["sample_id"] == "uf_" + sha(data) and m["exact_duplicate_of"] is None
        assert m["selection_status"] == "candidate" and set(m["issues"]) == {"review_not_approved", "review_evidence_incomplete"}
        assert all(m[k] == value for k, value in row.items())
        if cid in old_by_id:
            assert row == dict(old_by_id[cid], relative_path="prior/" + old_by_id[cid]["relative_path"])
        else:
            assert row == new_by_id[cid]
            item = dict(candidate_id=cid, format=row["format"], content_review="pending")
            if cid in github_files:
                group, source = github_files[cid]
                assert blob(data) == source["git_blob_sha1"] and len(data) == source["size"]
                assert row["source_version"] == "git:" + group["commit"]
                if row["format"] == "binary":
                    check_font(data)
                    item["format_check"] = "TrueType sfnt header, table bounds/tags; embedded metadata not privacy-approved"
                else:
                    text = data.decode("utf-8")
                    item["triage_flag_lines"] = triage_text(text)
                    if row["format"] == "json":
                        assert isinstance(json.loads(text), dict)
                        item["format_check"] = "UTF-8 JSON object; not executed"
                    else:
                        assert ":::MLLOG" in text
                        item["format_check"] = "UTF-8 published execution log with MLLOG markers; no benchmark metrics evaluated"
            else:
                group = uci_groups[row["origin_group_id"]]
                record = records[relative]
                archive = (raw / record["archive_relative_path"]).read_bytes()
                assert sha(archive) == record["archive_sha256"]
                with zipfile.ZipFile(io.BytesIO(archive)) as z:
                    assert z.read(record["archive_member"]) == data
                    info = z.getinfo(record["archive_member"])
                    assert f"{info.CRC:08x}" == record["member_crc32"]
                assert row["source_version"] == "doi:" + group["doi"] + ";archive_sha256:" + sha(archive)
                text = data.decode(group["encoding"])
                table = list(csv.reader(io.StringIO(text, newline=""), delimiter=group["delimiter"]))
                widths = {len(r) for r in table if r and any(v.strip() for v in r)}
                assert len(widths) == 1 and next(iter(widths)) > 1
                item.update(format_check="Complete original delimited table parsed without rewriting", encoding_for_read_only_check=group["encoding"], delimiter=group["delimiter"], triage_flag_lines=triage_text(text))
            triage.append(item)
        sizes.append(len(data))
        hashes.append(sha(data))
    assert len(hashes) == len(set(hashes))
    for group in plan["github_groups"]:
        for notice in group["notices"]:
            data = (raw / "notices" / group["origin_group_id"] / notice["path"]).read_bytes()
            assert len(data) == notice["size"] and blob(data) == notice["git_blob_sha1"]
    by_format = dict(sorted(Counter(r["format"] for r in rows).items()))
    by_origin = dict(sorted(Counter(r["origin_group_id"] for r in rows).items()))
    format_origins = {fmt: len({r["origin_group_id"] for r in rows if r["format"] == fmt}) for fmt in by_format}
    assert set(by_format.values()) == {10} and len(by_format) == 6
    assert len(by_origin) >= 12 and max(by_origin.values()) <= 5 and min(format_origins.values()) >= 2
    ignored = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, input="\n".join((raw / p).relative_to(ROOT).as_posix() for p in sorted(actual_files)) + "\n", text=True, capture_output=True)
    assert ignored.returncode == 0 and len(ignored.stdout.splitlines()) == len(actual_files)
    evidence = dict(status="additional_acquisition_and_combined_draft_verified", verified_at_utc=datetime.now(timezone.utc).isoformat(),
                    execution_git_head=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), python=sys.version,
                    verifier_sha256=sha(Path(__file__).read_bytes()), new_candidates=len(new_rows), combined_candidates=len(rows),
                    by_format=by_format, by_origin_group=by_origin, format_origin_groups=format_origins,
                    new_origin_groups=len({r["origin_group_id"] for r in new_rows}), total_origin_groups=len(by_origin),
                    original_candidate_fields_preserved=len(old_by_id), protected_files_unchanged=len(before),
                    total_candidate_bytes=sum(sizes), new_candidate_bytes=sum(r["original_size"] for r in new_rows),
                    minimum_bytes=min(sizes), maximum_bytes=max(sizes), exact_duplicate_candidates=0,
                    raw_files_git_ignored=len(actual_files), source_archives=len(acquisition["archive_members"]),
                    source_grouping="Provisional repository/original observation collection groups; distinct collection does not establish statistical independence",
                    rights_pending=len(rows), privacy_pending=len(rows), selected_files=0, count_and_group_quotas_met=True,
                    evaluation_ready=False, unseen_overlap_audit="not_performed", scientific_evaluation_run=False,
                    content_review="Read-only format/pattern triage, not complete rights/privacy/derivative approval. Do not infer safety from absent flags.", content_triage=triage)
    with (OUT / "verification.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in evidence.items() if k not in ("content_triage", "python")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
