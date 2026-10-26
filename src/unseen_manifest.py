"""Inventory and freeze explicit real-file candidates without running research engines.

Standard library only. A frozen manifest locks inputs; it does not establish that
they are unseen, legally usable, independent, or ready for scientific evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
FORMATS = ("text", "csv", "json", "python", "log", "binary")
PLAN = dict(plan_id="real_unseen_v1",files=60,formats=list(FORMATS),files_per_format=10,
            minimum_origin_groups=12,maximum_files_per_origin_group=5,
            minimum_origin_groups_per_format=2,minimum_bytes=16384,maximum_bytes=1048576)
FIELDS = {"candidate_id", "relative_path", "format", "origin_group_id", "source_locator", "source_version",
          "acquired_at_utc", "license_id", "license_evidence", "is_precompressed", "derivative_of",
          "rights_review_status", "privacy_review_status", "reviewed_at_utc", "exclusion_reason"}
OPTIONAL = {"original_filename", "original_size", "input_sha256"}
RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
            *(p+n for p in ("COM", "LPT") for n in "123456789¹²³")}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _encode(value):
    return (json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,indent=2)+"\n").encode("utf-8")


def _json(data):
    def pairs(items):
        result = {}
        for key,value in items:
            _require(key not in result,f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    value = json.loads(data.decode("utf-8-sig"),object_pairs_hook=pairs,parse_constant=invalid)
    _require(type(value) is dict,"Expected a JSON object")
    return value


def _identifier(value, label):
    _require(type(value) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}",value)
             and value.upper() not in RESERVED,f"Invalid {label}")


def _text(value, label, *, empty=False):
    _require(type(value) is str and (empty or bool(value.strip())) and "\0" not in value,f"Invalid {label}")


def _utc(value, label, *, optional=False):
    if optional and value is None:
        return
    _text(value,label)
    parsed = datetime.fromisoformat(value.replace("Z","+00:00"))
    _require(parsed.utcoffset() is not None and parsed.utcoffset().total_seconds()==0,f"{label} must be UTC")


def _linked(path):
    return path.is_symlink() or path.is_junction() or bool(
        path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT) if os.name=="nt" else path.is_symlink()


def _no_links(path):
    """Reject reparse points in every existing component, including the root."""
    path = Path(path).absolute()
    for component in (*reversed(path.parents),path):
        if component.exists() or component.is_symlink():
            _require(not _linked(component),f"Links/junctions are not allowed: {component}")
    return path


def _root(path):
    path = _no_links(Path(path).expanduser())
    _require(path.is_dir(),"Input root must be an existing directory")
    return path.resolve(strict=True)


def _relative(value):
    _text(value,"relative_path")
    parts = value.split("/")
    _require(not PureWindowsPath(value).drive and "\\" not in value and not value.startswith("/"),
             "Expected a portable relative path")
    for part in parts:
        _require(part not in ("", ".", "..") and not part.endswith(("."," ")) and len(part)<=255
                 and not any(ord(c)<32 or ord(c)==127 or c in '<>:"|?*' for c in part)
                 and part.split(".",1)[0].upper() not in RESERVED,"Unsafe relative path component")
    return parts


def _signature(info):
    # On Windows/Python 3.14, path stat ctime can mean creation while fstat
    # ctime means metadata change. Birth time is consistent for both APIs.
    stamp = info.st_birthtime_ns if os.name=="nt" else info.st_ctime_ns
    return info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,stamp


def _handle_path(stream, path):
    """Resolve the open handle before reading, so a replaced directory cannot escape."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        call = ctypes.WinDLL("kernel32",use_last_error=True).GetFinalPathNameByHandleW
        call.argtypes = [wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
        call.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        count = call(msvcrt.get_osfhandle(stream.fileno()),buffer,len(buffer),0)
        if not count or count>=len(buffer):
            raise ctypes.WinError(ctypes.get_last_error())
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\"+value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return Path(value).resolve(strict=True)
    proc = Path("/proc/self/fd")/str(stream.fileno())
    return proc.resolve(strict=True) if proc.exists() else path.resolve(strict=True)


def _read(path, *, input_root=None, collect=False):
    path = _no_links(path)
    before = path.stat()
    _require(stat.S_ISREG(before.st_mode),f"Expected a regular file: {path}")
    digest, chunks = hashlib.sha256(), []
    with path.open("rb") as stream:
        actual = _handle_path(stream,path)
        _require(os.path.normcase(str(actual))==os.path.normcase(str(path.resolve(strict=True))),"Open file path changed")
        if input_root is not None:
            _require(actual.is_relative_to(input_root),"Open file escaped input root")
        _require(_signature(before)==_signature(os.fstat(stream.fileno())),"File changed before reading")
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
            if collect:
                _require(sum(map(len,chunks))+len(chunk)<=16*1024*1024,"Metadata file exceeds 16 MiB")
                chunks.append(chunk)
        _require(_signature(before)==_signature(os.fstat(stream.fileno())),"File changed while reading")
    _no_links(path)
    _require(_signature(before)==_signature(path.stat()),"File changed after reading")
    return before.st_size,digest.hexdigest(),b"".join(chunks),_signature(before)


def _capture(path):
    path = Path(path).expanduser().absolute()
    size,digest,data,signature = _read(path,collect=True)
    return path,data,digest,signature


def _check_capture(snapshot):
    path,data,digest,signature = snapshot
    size,now,raw,current = _read(path,collect=True)
    _require(now==digest and raw==data and current==signature,f"Metadata changed: {path}")


def _scan(root, raw):
    inventory = _json(raw)
    _require(set(inventory)=={"inventory_version","corpus_id","data_kind","candidates"},"Unexpected inventory fields")
    _require(type(inventory["inventory_version"]) is int and inventory["inventory_version"]==1,"Unsupported inventory version")
    _identifier(inventory["corpus_id"],"corpus_id")
    _require(inventory["data_kind"] in ("research_candidate","test_fixture"),"Explicit data_kind is required")
    _require(type(inventory["candidates"]) is list,"candidates must be a list")
    rows,paths,identities,ids = [],set(),set(),set()
    signatures = {}
    for candidate in inventory["candidates"]:
        _require(type(candidate) is dict and FIELDS<=set(candidate)<=FIELDS|OPTIONAL,"Unexpected/missing candidate fields")
        row = dict(candidate)
        _identifier(row["candidate_id"],"candidate_id")
        _identifier(row["origin_group_id"],"origin_group_id")
        _require(row["candidate_id"] not in ids,"Duplicate candidate_id")
        ids.add(row["candidate_id"])
        _require(row["format"] in FORMATS,"Unsupported format")
        for field in ("source_locator","source_version"):
            _text(row[field],field)
        for field in ("license_id","license_evidence","exclusion_reason"):
            _text(row[field],field,empty=True)
        _utc(row["acquired_at_utc"],"acquired_at_utc")
        _utc(row["reviewed_at_utc"],"reviewed_at_utc",optional=True)
        for field in ("rights_review_status","privacy_review_status"):
            _require(row[field] in ("pending","approved","rejected"),f"Invalid {field}")
        _require(type(row["is_precompressed"]) is bool,"is_precompressed must be boolean")
        if row["derivative_of"] is not None:
            _identifier(row["derivative_of"],"derivative_of")
        parts = _relative(row["relative_path"])
        path = _no_links(root.joinpath(*parts))
        _require(path.resolve(strict=True).is_relative_to(root),"Candidate escaped input root")
        canonical = str(path.resolve(strict=True)).casefold()
        _require(canonical not in paths,"Duplicate/aliased candidate path")
        paths.add(canonical)
        size,digest,_,signature = _read(path,input_root=root)
        identity = signature[:2]
        if identity[1]:
            _require(identity not in identities,"Multiple paths refer to the same file")
            identities.add(identity)
        signatures[row["relative_path"]] = signature
        _require("original_filename" not in row or row["original_filename"]==path.name,"Filename differs from input")
        _require("original_size" not in row or type(row["original_size"]) is int and row["original_size"]==size,"Declared size mismatch")
        _require("input_sha256" not in row or row["input_sha256"]==digest,"Declared hash mismatch")
        row.update(original_filename=path.name,original_size=size,input_sha256=digest,
                   sample_id="uf_"+digest,exact_duplicate_of=None,issues=[],
                   selection_status="excluded" if row["exclusion_reason"].strip() else "candidate")
        if not PLAN["minimum_bytes"]<=size<=PLAN["maximum_bytes"]:
            row["issues"].append("size_outside_plan")
        if row["rights_review_status"]!="approved" or row["privacy_review_status"]!="approved":
            row["issues"].append("review_not_approved")
        if not row["license_id"].strip() or not row["license_evidence"].strip() or row["reviewed_at_utc"] is None:
            row["issues"].append("review_evidence_incomplete")
        if row["exclusion_reason"].strip():
            row["issues"].append("explicitly_excluded")
        rows.append(row)
    rows.sort(key=lambda r:(r["format"],r["origin_group_id"],r["input_sha256"],r["relative_path"]))
    indexed = {r["candidate_id"]:r for r in rows}
    seen = {}
    group_issues = []
    for row in rows:
        digest = row["input_sha256"]
        if digest in seen:
            first = seen[digest]
            row["exact_duplicate_of"] = first["candidate_id"]
            row["issues"].append("exact_duplicate")
            row["selection_status"] = "excluded"
            if not row["exclusion_reason"].strip():
                row["exclusion_reason"] = "exact_duplicate_of:"+first["candidate_id"]
            if row["origin_group_id"]!=first["origin_group_id"]:
                group_issues.append("Exact duplicates must share an origin group")
        else:
            seen[digest] = row
        parent = row["derivative_of"]
        _require(parent is None or parent in indexed,"Unknown derivative_of candidate")
        visited = {row["candidate_id"]}
        while parent is not None:
            _require(parent not in visited,"Cyclic derivative relation")
            visited.add(parent)
            ancestor = indexed[parent]
            if ancestor["origin_group_id"]!=row["origin_group_id"]:
                group_issues.append("Related candidates must share an origin group")
            parent = ancestor["derivative_of"]
            _require(parent is None or parent in indexed,"Unknown derivative_of candidate")
    return inventory,rows,sorted(set(group_issues)),signatures


def _selected(rows, group_issues, selection, corpus_id, draft_digest):
    _require(set(selection)=={"selection_version","corpus_id","draft_manifest_sha256","candidate_ids"},"Unexpected selection fields")
    _require(type(selection["selection_version"]) is int and selection["selection_version"]==1,"Unsupported selection version")
    _require(selection["corpus_id"]==corpus_id and selection["draft_manifest_sha256"]==draft_digest,"Selection is not bound to this draft")
    ids = selection["candidate_ids"]
    _require(type(ids) is list and all(type(i) is str for i in ids),"candidate_ids must be a list of strings")
    _require(len(ids)==len(set(ids))==PLAN["files"],"Select exactly 60 unique candidate IDs")
    indexed = {r["candidate_id"]:r for r in rows}
    _require(set(ids)<=set(indexed),"Unknown selected candidate ID")
    _require(not group_issues,"Origin group relationships require correction")
    chosen = [indexed[i] for i in ids]
    _require(all(not r["issues"] for r in chosen),"Selected candidates have unresolved size/review/exclusion/duplicate issues")
    counts = Counter(r["format"] for r in chosen)
    _require(all(counts[f]==PLAN["files_per_format"] for f in FORMATS),"Format quotas differ from plan")
    groups = Counter(r["origin_group_id"] for r in chosen)
    _require(len(groups)>=PLAN["minimum_origin_groups"] and max(groups.values())<=PLAN["maximum_files_per_origin_group"],"Origin group count/cap differs from plan")
    _require(all(len({r["origin_group_id"] for r in chosen if r["format"]==f})>=PLAN["minimum_origin_groups_per_format"] for f in FORMATS),"Each format needs two origin groups")
    return sorted(ids)


def _fence(root, raw, expected, signatures, captures, source):
    _,rows,issues,current = _scan(root,raw)
    _require((rows,issues)==expected and current==signatures,"Candidate files changed during operation")
    for snapshot in captures:
        _check_capture(snapshot)
    _require(Path(__file__).read_bytes()==source,"Manifest builder source changed")


def _destination(path, excluded):
    destination = _no_links(Path(path).expanduser())
    _require(not destination.exists() and not destination.is_symlink(),"Output already exists")
    resolved = destination.resolve()
    _require(all(not resolved.is_relative_to(p.resolve()) for p in excluded),"Output must be outside input/package directories")
    return destination.resolve()


def _write(path,data):
    _no_links(path.parent)
    with path.open("xb") as stream:
        _require(os.path.normcase(str(_handle_path(stream,path)))==os.path.normcase(str(path.absolute())),"Output path changed")
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _require(path.read_bytes()==data,"Saved bytes differ")


def _publish(destination, manifest, artifacts, fence):
    destination.parent.mkdir(parents=True,exist_ok=True)
    _no_links(destination.parent)
    destination.mkdir(exist_ok=False)
    try:
        artifacts = {**artifacts,".gitattributes":b"* -text\n"}
        for name,data in artifacts.items():
            _write(destination/name,data)
        fence()
        manifest["artifact_sha256"] = {n:_sha(b) for n,b in artifacts.items()}
        encoded = _encode(manifest)
        _write(destination/"manifest.json",encoded)
        fence()
        _require(all((destination/n).read_bytes()==b for n,b in artifacts.items()),"Saved artifacts changed")
        _require((destination/"manifest.json").read_bytes()==encoded,"Saved manifest changed")
        _no_links(destination)
        return dict(status=manifest["status"],corpus_id=manifest["corpus_id"],data_kind=manifest["data_kind"],
                    output_dir=str(destination),manifest_sha256=_sha(encoded),selected_count=len(manifest["selected_ids"]),
                    candidate_count=len(manifest["candidates"]),evaluation_ready=False)
    except BaseException as exc:
        try:
            _write(destination/"publication_failed.json",_encode(dict(status="publication_failed",error=f"{type(exc).__name__}: {exc}")))
        except BaseException as marker:
            exc.add_note(f"Failure marker could not be saved: {marker}")
        raise


def _selection_rows(rows,status,selected):
    presented = [dict(row) for row in rows]
    if status=="frozen":
        for row in presented:
            if row["candidate_id"] in selected:
                row["selection_status"] = "selected"
            elif row["selection_status"]!="excluded":
                row["selection_status"] = "not_selected"
                row["exclusion_reason"] = "not_selected_in_explicit_selection"
    return presented


def _manifest(root,inventory,rows,issues,status,selected,source):
    try:
        commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        commit = None
    return dict(manifest_version=1,status=status,corpus_id=inventory["corpus_id"],data_kind=inventory["data_kind"],
        input_root=str(root),created_at_utc=datetime.now(timezone.utc).isoformat(),git_head=commit,
        source_sha256=_sha(source),plan=PLAN,candidates=_selection_rows(rows,status,selected),group_issues=issues,selected_ids=selected,
        evaluation_ready=False,unseen_overlap_audit="not_performed",provenance_review="declared_metadata_only",
        scope="Input manifest only; no features, models, compression, training or scientific evaluation")


def create_draft(input_root,inventory_path,output_dir):
    root = _root(input_root)
    destination = _destination(output_dir,[root])
    source = Path(__file__).read_bytes()
    snapshot = _capture(inventory_path)
    inventory,rows,issues,signatures = _scan(root,snapshot[1])
    manifest = _manifest(root,inventory,rows,issues,"draft",[],source)
    fence = lambda:_fence(root,snapshot[1],(rows,issues),signatures,[snapshot],source)
    return _publish(destination,manifest,{"inventory_snapshot.json":snapshot[1]},fence)


def _package(directory, status, *, expected_sha256=None):
    directory = _root(directory)
    _require(not (directory/"publication_failed.json").exists(),"Publication failure marker exists")
    capture = _capture(directory/"manifest.json")
    if expected_sha256 is not None:
        _require(type(expected_sha256) is str and re.fullmatch("[0-9a-f]{64}",expected_sha256) and capture[2]==expected_sha256,"Manifest SHA-256 mismatch")
    manifest = _json(capture[1])
    _require(type(manifest.get("manifest_version")) is int and manifest["manifest_version"]==1 and manifest.get("status")==status,"Unexpected manifest version/status")
    _require(manifest.get("plan")==PLAN and manifest.get("evaluation_ready") is False
             and manifest.get("unseen_overlap_audit")=="not_performed" and manifest.get("provenance_review")=="declared_metadata_only","Manifest policy differs")
    _require(manifest.get("source_sha256")==_sha(Path(__file__).read_bytes()),"Builder source differs from published manifest")
    names = {"inventory_snapshot.json",".gitattributes"}
    if status=="frozen":
        names |= {"selection_snapshot.json","draft_manifest_snapshot.json"}
    _require(type(manifest.get("artifact_sha256")) is dict and set(manifest["artifact_sha256"])==names,"Artifact set differs")
    _require({p.name for p in directory.iterdir()}==names|{"manifest.json"},"Unexpected package files")
    captures = {n:_capture(directory/n) for n in names}
    _require(all(c[2]==manifest["artifact_sha256"][n] for n,c in captures.items()),"Artifact hash mismatch")
    _require(captures[".gitattributes"][1]==b"* -text\n","Raw artifact preservation rule differs")
    _utc(manifest.get("created_at_utc"),"created_at_utc")
    root = _root(manifest["input_root"])
    inventory,rows,issues,signatures = _scan(root,captures["inventory_snapshot.json"][1])
    _require(manifest["corpus_id"]==inventory["corpus_id"] and manifest["data_kind"]==inventory["data_kind"],"Corpus identity differs")
    _require(issues==manifest["group_issues"],"Candidate group snapshots differ")
    selected = []
    if status=="draft":
        _require(manifest["selected_ids"]==[],"Draft cannot contain selected IDs")
    else:
        draft_raw = captures["draft_manifest_snapshot.json"][1]
        draft = _json(draft_raw)
        _require(_sha(draft_raw)==manifest.get("draft_manifest_sha256"),"Draft digest differs")
        _require(draft.get("status")=="draft" and type(draft.get("manifest_version")) is int and draft.get("manifest_version")==1 and draft.get("plan")==PLAN
                 and draft.get("input_root")==str(root) and draft.get("corpus_id")==inventory["corpus_id"]
                 and draft.get("data_kind")==inventory["data_kind"] and draft.get("source_sha256")==manifest["source_sha256"]
                 and draft.get("candidates")==rows and draft.get("group_issues")==issues
                 and draft.get("selected_ids")==[] and draft.get("evaluation_ready") is False
                 and draft.get("unseen_overlap_audit")=="not_performed"
                 and draft.get("provenance_review")=="declared_metadata_only"
                 and draft.get("artifact_sha256")=={n:manifest["artifact_sha256"][n] for n in ("inventory_snapshot.json",".gitattributes")},"Frozen draft reference differs")
        selection = _json(captures["selection_snapshot.json"][1])
        selected = _selected(rows,issues,selection,inventory["corpus_id"],_sha(draft_raw))
        _require(selected==manifest["selected_ids"],"Published selection differs")
    _require(_selection_rows(rows,status,selected)==manifest["candidates"],"Candidate snapshots differ")
    return root,inventory,rows,issues,signatures,[capture,*captures.values()],manifest


def freeze_manifest(draft_dir,selection_path,output_dir):
    source = Path(__file__).read_bytes()
    root,inventory,rows,issues,signatures,captures,draft = _package(draft_dir,"draft")
    destination = _destination(output_dir,[root,Path(draft_dir)])
    selection = _capture(selection_path)
    selected = _selected(rows,issues,_json(selection[1]),inventory["corpus_id"],captures[0][2])
    manifest = _manifest(root,inventory,rows,issues,"frozen",selected,source)
    manifest["draft_manifest_sha256"] = captures[0][2]
    artifacts = {"inventory_snapshot.json":next(c[1] for c in captures if c[0].name=="inventory_snapshot.json"),
                 "draft_manifest_snapshot.json":captures[0][1],"selection_snapshot.json":selection[1]}
    fence = lambda:_fence(root,artifacts["inventory_snapshot.json"],(rows,issues),signatures,[*captures,selection],source)
    return _publish(destination,manifest,artifacts,fence)


def audit_manifest(manifest_dir,expected_sha256):
    _require(type(expected_sha256) is str and re.fullmatch("[0-9a-f]{64}",expected_sha256),"Expected an independently recorded SHA-256")
    source = Path(__file__).read_bytes()
    root,inventory,rows,issues,signatures,captures,manifest = _package(manifest_dir,"frozen",expected_sha256=expected_sha256)
    raw = next(c[1] for c in captures if c[0].name=="inventory_snapshot.json")
    _fence(root,raw,(rows,issues),signatures,captures,source)
    _require(not (Path(manifest_dir)/"publication_failed.json").exists(),"Publication failure marker exists")
    return dict(verified=True,status="frozen",corpus_id=inventory["corpus_id"],data_kind=inventory["data_kind"],
                manifest_sha256=captures[0][2],selected_count=len(manifest["selected_ids"]),evaluation_ready=False,
                unseen_overlap_audit="not_performed")


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation",required=True)
    draft = sub.add_parser("draft",help="Hash an explicit metadata inventory into a new draft")
    draft.add_argument("--root",required=True,type=Path)
    draft.add_argument("--inventory",required=True,type=Path)
    draft.add_argument("--output-dir",required=True,type=Path)
    freeze = sub.add_parser("freeze",help="Validate explicit IDs against a draft and lock a new manifest")
    freeze.add_argument("--draft-dir",required=True,type=Path)
    freeze.add_argument("--selection",required=True,type=Path)
    freeze.add_argument("--output-dir",required=True,type=Path)
    audit = sub.add_parser("audit",help="Verify a frozen manifest against an independently recorded SHA-256")
    audit.add_argument("--manifest-dir",required=True,type=Path)
    audit.add_argument("--expected-sha256",required=True)
    args = parser.parse_args(arguments)
    try:
        if args.operation=="draft":
            result = create_draft(args.root,args.inventory,args.output_dir)
        elif args.operation=="freeze":
            result = freeze_manifest(args.draft_dir,args.selection,args.output_dir)
        else:
            result = audit_manifest(args.manifest_dir,args.expected_sha256)
    except (OSError,ValueError,TypeError,KeyError,RecursionError) as exc:
        print(f"Manifest operation failed: {type(exc).__name__}: {exc}",file=sys.stderr)
        return 1
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
