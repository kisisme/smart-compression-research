"""Acquire the planned supplemental originals and publish a combined draft only.

Standard library only. Never executes downloaded code, transforms inputs, imports
research engines, approves candidates, freezes a corpus, or computes performance.
Each invocation requires a new output ID; failed attempts are retained.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "research_log/unseen_additional_collection_plan_20261026.json"
MINIMUM, MAXIMUM = 16384, 1048576


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    if path.read_bytes() != data:
        raise ValueError("Saved bytes mismatch")


def download(url, target, limit=MAXIMUM, expected_size=None, expected_blob=None):
    hosts = {"raw.githubusercontent.com", "archive.ics.uci.edu", "www.archive.ics.uci.edu", "creativecommons.org"}
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts:
        raise ValueError("Unexpected source host")
    started = utc()
    request = Request(url, headers={"User-Agent": "smart-compression-research-acquisition/2", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=45) as response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in hosts:
            raise ValueError("Unexpected redirect")
        if response.headers.get("Content-Encoding", "identity") != "identity":
            raise ValueError("Unexpected HTTP content encoding")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("HTTP entity exceeds acquisition bound")
        headers = {key: response.headers.get(key) for key in ("ETag", "Last-Modified", "Content-Type", "Content-Length")}
        final_url = response.geturl()
    if expected_size is not None and len(data) != expected_size:
        raise ValueError("Pinned Git tree size mismatch")
    if expected_blob is not None and blob(data) != expected_blob:
        raise ValueError("Pinned Git blob hash mismatch")
    write(target, data)
    return data, dict(url=url, final_url=final_url, started_at_utc=started, acquired_at_utc=utc(),
                      headers=headers, size=len(data), input_sha256=sha(data), git_blob_sha1=blob(data))


def candidate(group, candidate_id, relative, data, acquired, locator, version, license_url):
    return dict(candidate_id=candidate_id, relative_path=relative, format=group["format"],
                origin_group_id=group["origin_group_id"], source_locator=locator, source_version=version,
                acquired_at_utc=acquired, license_id=group["license_id"], license_evidence=license_url,
                is_precompressed=False, derivative_of=None, rights_review_status="pending",
                privacy_review_status="pending", reviewed_at_utc=None, exclusion_reason="",
                original_filename=PurePosixPath(relative).name, original_size=len(data), input_sha256=sha(data))


def github_group(group, raw):
    records, rows = [], []
    base = f"https://raw.githubusercontent.com/{group['repo']}/{group['commit']}/"
    for notice in group["notices"]:
        relative = "notices/" + group["origin_group_id"] + "/" + notice["path"]
        _, record = download(base + quote(notice["path"], safe="/"), raw / relative,
                             expected_size=notice["size"], expected_blob=notice["git_blob_sha1"])
        records.append(dict(record, kind="license_notice", raw_relative_path=relative, origin_group_id=group["origin_group_id"]))
    for item in group["files"]:
        relative = "additional/" + group["origin_group_id"] + "/" + item["path"]
        data, record = download(base + quote(item["path"], safe="/"), raw / relative,
                                expected_size=item["size"], expected_blob=item["git_blob_sha1"])
        if not MINIMUM <= len(data) <= MAXIMUM:
            raise ValueError("Planned original outside size range")
        records.append(dict(record, kind="candidate", raw_relative_path=relative, origin_group_id=group["origin_group_id"]))
        declaration = dict(group, license_id=item["license_id"])
        rows.append(candidate(declaration, item["candidate_id"], relative, data, record["acquired_at_utc"],
                              f"https://github.com/{group['repo']}/blob/{group['commit']}/{item['path']}",
                              "git:" + group["commit"], f"https://github.com/{group['repo']}/blob/{group['commit']}/{item['license_path']}"))
    return rows, records, []


def uci_group(group, raw):
    records, rows, members = [], [], []
    notice_relative = "notices/" + group["origin_group_id"] + "/source_page.html"
    page, record = download(group["page_url"], raw / notice_relative, limit=8 * MAXIMUM)
    if b"creativecommons.org/licenses/by/4.0" not in page.lower():
        raise ValueError("Expected CC-BY-4.0 link missing in saved source page")
    records.append(dict(record, kind="source_page", raw_relative_path=notice_relative, origin_group_id=group["origin_group_id"]))
    archive_relative = "archives/" + group["origin_group_id"] + ".zip"
    archive_data, archive_record = download(group["archive_url"], raw / archive_relative, limit=8 * MAXIMUM)
    records.append(dict(archive_record, kind="source_archive", raw_relative_path=archive_relative, origin_group_id=group["origin_group_id"]))
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        members = [dict(name=i.filename, original_size=i.file_size, archived_size=i.compress_size, crc32=f"{i.CRC:08x}") for i in archive.infolist()]
        for index, basename in enumerate(group["members"], 1):
            matches = [i for i in archive.infolist() if not i.is_dir() and PurePosixPath(i.filename).name == basename]
            if len(matches) != 1:
                raise ValueError("Expected exactly one original archive member: " + basename)
            info = matches[0]
            parts = PurePosixPath(info.filename).parts
            if not parts or info.filename.startswith("/") or any(p in (".", "..") or ":" in p or "\\" in p for p in parts):
                raise ValueError("Unsafe member path")
            if stat.S_ISLNK(info.external_attr >> 16) or not MINIMUM <= info.file_size <= MAXIMUM:
                raise ValueError("Member link/size constraint failed")
            with archive.open(info) as member:
                data = member.read(MAXIMUM + 1)
            if len(data) != info.file_size:
                raise ValueError("Incomplete archive member")
            relative = "additional/" + group["origin_group_id"] + "/" + info.filename
            write(raw / relative, data)
            acquired = archive_record["acquired_at_utc"]
            rows.append(candidate(group, f"{group['origin_group_id']}_{index:02d}", relative, data, acquired,
                                  group["archive_url"] + "#member=" + quote(info.filename, safe="/"),
                                  "doi:" + group["doi"] + ";archive_sha256:" + sha(archive_data), group["page_url"]))
            records.append(dict(kind="candidate", raw_relative_path=relative, origin_group_id=group["origin_group_id"],
                                url=group["archive_url"], archive_relative_path=archive_relative, archive_sha256=sha(archive_data),
                                archive_member=info.filename, member_crc32=f"{info.CRC:08x}", acquired_at_utc=acquired,
                                size=len(data), input_sha256=sha(data)))
    return rows, records, members


def main():
    corpus_id = sys.argv[1] if len(sys.argv) == 2 else ""
    if not re.fullmatch(r"real_candidates_\d{8}_\d{2,}", corpus_id):
        raise ValueError("A new timestamped acquisition ID is required")
    plan_bytes = PLAN.read_bytes()
    plan = json.loads(plan_bytes)
    old_out = ROOT / "data/results/real_unseen" / plan["base_collection"]
    old_inventory = json.loads((old_out / "inventory.json").read_bytes())
    old_raw = ROOT / "data/raw/real_unseen" / plan["base_collection"]
    baseline = json.loads((old_out / "protected_after.json").read_bytes())
    paths = set(baseline)
    paths.update(p.relative_to(ROOT).as_posix() for directory in (old_out, old_raw) for p in directory.rglob("*") if p.is_file())
    paths.update(["research_log/collect_unseen_candidates_20261026.py", "research_log/verify_unseen_collection_20261026.py",
                  "research_log/unseen_collection_plan_20261026.json", "research_log/unseen_source_review_20261026.json",
                  "research_log/unseen_collection_20261026.md", "research_log/unseen_collection_report_checks_20261026.json"])
    before = {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}
    if any(before[p] != value for p, value in baseline.items()):
        raise ValueError("Protected baseline mismatch before acquisition")
    raw = ROOT / "data/raw/real_unseen" / corpus_id
    out = ROOT / "data/results/real_unseen" / corpus_id
    if raw.exists() or out.exists():
        raise ValueError("Refusing existing output path; retain prior attempts")
    raw.mkdir(parents=True)
    out.mkdir(parents=True)
    save(out / "protected_before.json", before)
    save(out / "collection_plan_snapshot.json", plan)
    records, errors, additions, copied, archive_members = [], [], [], [], {}
    # Create independent regular files, never hardlinks; leave the first pool untouched.
    for path in sorted(old_raw.rglob("*")):
        if path.is_file():
            relative = "prior/" + path.relative_to(old_raw).as_posix()
            data = path.read_bytes()
            write(raw / relative, data)
            records.append(dict(kind="prior_byte_copy", raw_relative_path=relative,
                                prior_relative_path=path.relative_to(ROOT).as_posix(), size=len(data), input_sha256=sha(data), copied_at_utc=utc()))
    for row in old_inventory["candidates"]:
        copied.append(dict(row, relative_path="prior/" + row["relative_path"]))
    groups = [*plan["github_groups"], *plan["uci_groups"]]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(github_group if group["kind"] == "github" else uci_group, group, raw): group for group in groups}
        for future in as_completed(futures):
            group = futures[future]
            try:
                rows, evidence, members = future.result()
                additions.extend(rows)
                records.extend(evidence)
                if members:
                    archive_members[group["origin_group_id"]] = members
                print(json.dumps(dict(group=group["origin_group_id"], candidates=len(rows), status="downloaded_pending_review")), flush=True)
            except Exception as error:
                errors.append(dict(origin_group_id=group["origin_group_id"], error_type=type(error).__name__, error=str(error), at_utc=utc()))
                print(json.dumps(dict(group=group["origin_group_id"], status="failed", error_type=type(error).__name__)), flush=True)
    try:
        relative = "notices/CC-BY-4.0/legalcode.en.html"
        _, notice = download("https://creativecommons.org/licenses/by/4.0/legalcode.en", raw / relative, limit=8 * MAXIMUM)
        records.append(dict(notice, kind="common_license_notice", raw_relative_path=relative))
    except Exception as error:
        errors.append(dict(origin_group_id="common_cc_by_notice", error_type=type(error).__name__, error=str(error), at_utc=utc()))
    additions.sort(key=lambda row: row["candidate_id"])
    candidates = sorted([*copied, *additions], key=lambda row: row["candidate_id"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    for name, subset in (("inventory.json", candidates), ("additional_inventory.json", additions)):
        save(out / name, dict(inventory_version=1, corpus_id=corpus_id, data_kind="research_candidate", candidates=subset))
    save(out / "acquisition.json", dict(status="downloaded_pending_review" if not errors else "partial_acquisition_with_errors",
         completed_at_utc=utc(), execution_git_head=head, collector_sha256=sha(Path(__file__).read_bytes()), plan_sha256=sha(plan_bytes),
         raw_root=raw.relative_to(ROOT).as_posix(), output_root=out.relative_to(ROOT).as_posix(), python=sys.version,
         base_collection=plan["base_collection"], records=sorted(records, key=lambda r: r["raw_relative_path"]), errors=errors,
         archive_members=archive_members, acquisition_review="source_context_checked_only; individual rights/privacy/derivation pending",
         evaluation_ready=False, unseen_overlap_audit="not_performed"))
    save(out / "attributions.json", dict(uci=[{key: g[key] for key in ("origin_group_id", "doi", "citation", "page_url", "license_id", "role")} for g in plan["uci_groups"]],
         github=[{key: g[key] for key in ("repo", "origin_group_id", "commit", "role", "notices")} for g in plan["github_groups"]],
         grouping="Entire repositories and distinct original UCI observation collections. Shared UCI host/creators or MLCommons organization/vendor are not hidden; cross-source derivation/independence remains pending."))
    command = [sys.executable, "-B", "-m", "src.unseen_manifest", "draft", "--root", str(raw),
               "--inventory", str(out / "inventory.json"), "--output-dir", str(out / "draft")]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    save(out / "draft_cli.json", dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr, completed_at_utc=utc()))
    after = {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}
    save(out / "protected_after.json", after)
    save(out / "preservation_check.json", dict(unchanged=before == after, protected_files=len(paths), original_pool_preserved=True,
                                               original_baseline_preserved=True, draft_returncode=result.returncode))
    print(json.dumps(dict(corpus_id=corpus_id, new_candidates=len(additions), combined_candidates=len(candidates),
                          errors=len(errors), draft_returncode=result.returncode, protected_unchanged=before == after)), flush=True)
    if errors or result.returncode or before != after:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
