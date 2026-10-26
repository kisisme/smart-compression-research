"""Artificial files and review declarations; no fixture is real unseen research data."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src import unseen_manifest as m


def fixture(directory, count=60):
    root = directory/"인위적 원본 🧪"
    root.mkdir()
    rows = []
    for index in range(count):
        form = m.FORMATS[index//10]
        relative = f"{form}/입력 {index:03d} 🧪.dat"
        path = root/relative
        path.parent.mkdir(exist_ok=True)
        header = f"ARTIFICIAL TEST FILE {index:03d} — NOT RESEARCH DATA\n".encode("utf-8")
        path.write_bytes((header*((16384//len(header))+1))[:16384])
        rows.append(dict(candidate_id=f"c{index:03d}",relative_path=relative,format=form,
            origin_group_id=f"g_{form}_{index%10//5}",source_locator=f"fixture://{form}/{index}",
            source_version="artificial-v1",acquired_at_utc="2026-10-26T00:00:00Z",
            license_id="fixture-only-not-a-license",license_evidence="Artificial unit fixture declaration",
            is_precompressed=False,derivative_of=None,rights_review_status="approved",
            privacy_review_status="approved",reviewed_at_utc="2026-10-26T00:00:00Z",exclusion_reason=""))
    inventory = dict(inventory_version=1,corpus_id="artificial_fixture",data_kind="test_fixture",candidates=rows)
    path = directory/"inventory.json"
    path.write_bytes(m._encode(inventory))
    return root,path,inventory


class ManifestTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="unseen_manifest_artificial_")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root,self.inventory_path,self.inventory = fixture(self.directory)
        self.draft,self.frozen = self.directory/"draft",self.directory/"frozen"
        self.selection_path = self.directory/"selection.json"

    def save_inventory(self):
        self.inventory_path.write_bytes(m._encode(self.inventory))

    def draft_and_selection(self):
        self.save_inventory()
        result = m.create_draft(self.root,self.inventory_path,self.draft)
        selection = dict(selection_version=1,corpus_id=self.inventory["corpus_id"],
                         draft_manifest_sha256=result["manifest_sha256"],
                         candidate_ids=[r["candidate_id"] for r in self.inventory["candidates"]])
        self.selection_path.write_bytes(m._encode(selection))
        return result,selection

    def freeze(self):
        return m.freeze_manifest(self.draft,self.selection_path,self.frozen)

    @unittest.skipUnless(os.name=="nt","Windows stat/fstat timestamp semantics")
    def test_windows_path_and_handle_signatures_match_after_modification(self):
        path = self.root/self.inventory["candidates"][0]["relative_path"]
        path.write_bytes(b"Artificial modified file")
        info = path.stat()
        os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+10000000))
        with path.open("rb") as stream:
            self.assertEqual(m._signature(path.stat()),m._signature(os.fstat(stream.fileno())))
        self.assertEqual(m._read(path)[0],len(b"Artificial modified file"))

    def test_complete_fixture_draft_freeze_audit_preserves_bytes_and_is_not_evaluation_ready(self):
        before = {str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        draft,_ = self.draft_and_selection()
        result = self.freeze()
        verified = m.audit_manifest(self.frozen,result["manifest_sha256"])
        self.assertEqual((draft["selected_count"],result["selected_count"]),(0,60))
        self.assertEqual(verified["data_kind"],"test_fixture")
        self.assertFalse(verified["evaluation_ready"])
        self.assertEqual(verified["unseen_overlap_audit"],"not_performed")
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        manifest = json.loads((self.frozen/"manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(all(r["sample_id"]=="uf_"+r["input_sha256"] and len(r["input_sha256"])==64 for r in manifest["candidates"]))
        self.assertEqual((self.frozen/"inventory_snapshot.json").read_bytes(),self.inventory_path.read_bytes())
        self.assertEqual(set(manifest["artifact_sha256"]),{"inventory_snapshot.json","selection_snapshot.json","draft_manifest_snapshot.json",".gitattributes"})

    def test_incomplete_pending_and_empty_inventory_remain_drafts(self):
        self.inventory["candidates"] = self.inventory["candidates"][:1]
        self.inventory["candidates"][0].update(rights_review_status="pending",license_id="",reviewed_at_utc=None)
        self.save_inventory()
        result = m.create_draft(self.root,self.inventory_path,self.draft)
        self.assertEqual(result["status"],"draft")
        record = json.loads((self.draft/"manifest.json").read_text(encoding="utf-8"))
        self.assertIn("review_not_approved",record["candidates"][0]["issues"])
        self.inventory["candidates"] = []
        self.save_inventory()
        empty = m.create_draft(self.root,self.inventory_path,self.directory/"empty_draft")
        self.assertEqual(empty["candidate_count"],0)

    def test_selection_and_unselected_duplicate_reasons_are_preserved_per_candidate(self):
        original_ids = [r["candidate_id"] for r in self.inventory["candidates"]]
        first = self.inventory["candidates"][0]
        extra = {**first,"candidate_id":"extra","relative_path":"text/힣 extra.dat"}
        duplicate = {**first,"candidate_id":"duplicate","relative_path":"text/힣 duplicate.dat","derivative_of":first["candidate_id"]}
        (self.root/extra["relative_path"]).write_bytes(b"ARTIFICIAL EXTRA"*1100)
        (self.root/duplicate["relative_path"]).write_bytes((self.root/first["relative_path"]).read_bytes())
        self.inventory["candidates"].extend([extra,duplicate])
        self.save_inventory()
        drafted = m.create_draft(self.root,self.inventory_path,self.draft)
        selection = dict(selection_version=1,corpus_id=self.inventory["corpus_id"],
            draft_manifest_sha256=drafted["manifest_sha256"],candidate_ids=original_ids)
        self.selection_path.write_bytes(m._encode(selection))
        frozen = self.freeze()
        self.assertTrue(m.audit_manifest(self.frozen,frozen["manifest_sha256"])["verified"])
        rows = {r["candidate_id"]:r for r in json.loads((self.frozen/"manifest.json").read_text(encoding="utf-8"))["candidates"]}
        self.assertEqual(rows["extra"]["selection_status"],"not_selected")
        self.assertEqual(rows["extra"]["exclusion_reason"],"not_selected_in_explicit_selection")
        self.assertEqual(rows["duplicate"]["selection_status"],"excluded")
        self.assertEqual(rows["duplicate"]["exclusion_reason"],"exact_duplicate_of:"+first["candidate_id"])
        self.assertTrue(all(rows[i]["selection_status"]=="selected" for i in original_ids))

    def test_rejects_duplicate_json_nonfinite_and_compression_or_feature_fields(self):
        for content in (b'{"inventory_version":1,"inventory_version":1}',b'{"x":NaN}',b'{"x":Infinity}'):
            self.inventory_path.write_bytes(content)
            with self.assertRaises(ValueError): m.create_draft(self.root,self.inventory_path,self.draft)
            self.assertFalse(self.draft.exists())
        for field in ("score_gzip","features","prediction_confidence"):
            row = self.inventory["candidates"][0]
            row[field] = 0
            self.save_inventory()
            with self.assertRaises(ValueError): m.create_draft(self.root,self.inventory_path,self.draft)
            del row[field]

    def test_rejects_unsafe_relative_paths_before_publication(self):
        for path in ("../outside", "C:/outside", "/absolute", "a\\b", "a//b", "a/./b", "CON.txt", "COM¹.txt", "a:stream", "trailing. ", "bad?.bin"):
            with self.subTest(path=path):
                self.inventory["candidates"][0]["relative_path"] = path
                self.save_inventory()
                with self.assertRaises((ValueError,OSError)): m.create_draft(self.root,self.inventory_path,self.draft)
                self.assertFalse(self.draft.exists())

    def test_rejects_duplicate_ids_case_aliases_and_hardlinks(self):
        original = deepcopy(self.inventory)
        self.inventory["candidates"][1]["candidate_id"] = self.inventory["candidates"][0]["candidate_id"]
        self.save_inventory()
        with self.assertRaisesRegex(ValueError,"Duplicate candidate_id"): m.create_draft(self.root,self.inventory_path,self.draft)
        self.inventory = deepcopy(original)
        self.inventory["candidates"][1]["relative_path"] = self.inventory["candidates"][0]["relative_path"].upper()
        self.save_inventory()
        with self.assertRaises((ValueError,OSError)): m.create_draft(self.root,self.inventory_path,self.draft)
        self.inventory = deepcopy(original)
        first,second = [self.root/r["relative_path"] for r in self.inventory["candidates"][:2]]
        second.unlink()
        os.link(first,second)
        self.save_inventory()
        with self.assertRaisesRegex(ValueError,"same file"): m.create_draft(self.root,self.inventory_path,self.draft)

    def test_symlink_and_directory_junction_cannot_escape_root(self):
        external = self.directory/"external"
        external.mkdir()
        (external/"file.bin").write_bytes(b"Private artificial outside input")
        linked = self.root/"linked"
        if os.name=="nt":
            # Native fixture setup only; no GUI automation and no recursive delete.
            completed = subprocess.run(["cmd","/c","mklink","/J",str(linked),str(external)],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.addCleanup(lambda:os.rmdir(linked) if linked.exists() else None)
        else:
            linked.symlink_to(external,target_is_directory=True)
        self.inventory["candidates"][0]["relative_path"] = "linked/file.bin"
        self.save_inventory()
        with self.assertRaisesRegex(ValueError,"Links/junctions"): m.create_draft(self.root,self.inventory_path,self.draft)
        self.assertFalse(self.draft.exists())
        self.assertEqual((external/"file.bin").read_bytes(),b"Private artificial outside input")

    def test_declared_hash_size_filename_and_metadata_types_must_agree(self):
        changes = ({"input_sha256":"0"*64},{"original_size":True},{"original_filename":"wrong.bin"},
                   {"is_precompressed":1},{"reviewed_at_utc":"2026-10-26T00:00:00"},{"rights_review_status":"yes"})
        original = deepcopy(self.inventory["candidates"][0])
        for change in changes:
            self.inventory["candidates"][0] = {**original,**change}
            self.save_inventory()
            with self.assertRaises(ValueError): m.create_draft(self.root,self.inventory_path,self.draft)

    def test_existing_output_and_output_inside_input_are_never_modified(self):
        self.draft.mkdir()
        marker = self.draft/"preserve.bin"
        marker.write_bytes(b"existing output")
        with self.assertRaises(ValueError): m.create_draft(self.root,self.inventory_path,self.draft)
        self.assertEqual(marker.read_bytes(),b"existing output")
        with self.assertRaises(ValueError): m.create_draft(self.root,self.inventory_path,self.root/"new_manifest")
        self.assertFalse((self.root/"new_manifest").exists())

    def test_selection_requires_draft_digest_known_unique_ids_and_exact_count(self):
        draft,selection = self.draft_and_selection()
        variants = [dict(selection,draft_manifest_sha256="0"*64),dict(selection,corpus_id="wrong"),
                    dict(selection,candidate_ids=selection["candidate_ids"][:-1]),
                    dict(selection,candidate_ids=[*selection["candidate_ids"][:-1],selection["candidate_ids"][0]]),
                    dict(selection,candidate_ids=[*selection["candidate_ids"][:-1],"unknown"])]
        for variant in variants:
            self.selection_path.write_bytes(m._encode(variant))
            with self.assertRaises(ValueError): self.freeze()
            self.assertFalse(self.frozen.exists())

    def test_review_size_and_explicit_exclusion_issues_prevent_freeze(self):
        variants = ({"rights_review_status":"pending"},{"privacy_review_status":"rejected"},
                    {"license_evidence":""},{"reviewed_at_utc":None},{"exclusion_reason":"metadata exclusion"})
        for index,change in enumerate(variants):
            with self.subTest(change=change):
                self.inventory["candidates"][index].update(change)
        self.draft_and_selection()
        with self.assertRaisesRegex(ValueError,"unresolved"): self.freeze()
        self.assertFalse(self.frozen.exists())

    def test_undersize_and_oversize_selected_files_are_not_silently_replaced(self):
        for row,size in zip(self.inventory["candidates"][:2],(0,1048577)):
            (self.root/row["relative_path"]).write_bytes(b"x"*size)
        self.draft_and_selection()
        with self.assertRaisesRegex(ValueError,"unresolved"): self.freeze()

    def test_group_caps_and_format_quotas_are_enforced(self):
        original = deepcopy(self.inventory)
        for row in self.inventory["candidates"][:6]: row["origin_group_id"] = "same_origin"
        self.draft_and_selection()
        with self.assertRaisesRegex(ValueError,"group count/cap"): self.freeze()
        self.draft = self.directory/"draft_two"
        self.inventory = deepcopy(original)
        self.inventory["candidates"][0]["format"] = "csv"
        self.draft_and_selection()
        with self.assertRaisesRegex(ValueError,"quotas"): self.freeze()

    def test_exact_duplicates_and_derivative_relations_require_correct_groups(self):
        first,second = self.inventory["candidates"][:2]
        (self.root/second["relative_path"]).write_bytes((self.root/first["relative_path"]).read_bytes())
        second["origin_group_id"] = "different_origin"
        second["derivative_of"] = first["candidate_id"]
        self.draft_and_selection()
        record = json.loads((self.draft/"manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(record["group_issues"])
        self.assertTrue(any(r["exact_duplicate_of"] for r in record["candidates"]))
        with self.assertRaisesRegex(ValueError,"relationships"): self.freeze()

    def test_unknown_and_cyclic_relations_reject_draft(self):
        self.inventory["candidates"][0]["derivative_of"] = "unknown"
        self.save_inventory()
        with self.assertRaisesRegex(ValueError,"Unknown derivative"): m.create_draft(self.root,self.inventory_path,self.draft)
        first,second = self.inventory["candidates"][:2]
        first["derivative_of"],second["derivative_of"] = second["candidate_id"],first["candidate_id"]
        self.save_inventory()
        with self.assertRaisesRegex(ValueError,"Cyclic"): m.create_draft(self.root,self.inventory_path,self.draft)

    def test_changed_candidate_between_draft_and_freeze_is_rejected(self):
        self.draft_and_selection()
        (self.root/self.inventory["candidates"][0]["relative_path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"snapshots differ"): self.freeze()
        self.assertFalse(self.frozen.exists())

    def test_changed_input_during_publication_preserves_failure_evidence(self):
        original = m._write
        path = self.root/self.inventory["candidates"][0]["relative_path"]
        def changing(target,data):
            original(target,data)
            if target.name=="inventory_snapshot.json": path.write_bytes(b"changed by fixture")
        with patch.object(m,"_write",side_effect=changing), self.assertRaises(ValueError):
            m.create_draft(self.root,self.inventory_path,self.draft)
        self.assertTrue((self.draft/"publication_failed.json").is_file())
        self.assertFalse((self.draft/"manifest.json").exists())
        self.assertEqual(path.read_bytes(),b"changed by fixture")

    def test_metadata_change_and_source_change_during_publication_are_rejected(self):
        original = m._write
        def changing(target,data):
            original(target,data)
            if target.name=="inventory_snapshot.json": self.inventory_path.write_bytes(b"{}")
        with patch.object(m,"_write",side_effect=changing), self.assertRaises(ValueError):
            m.create_draft(self.root,self.inventory_path,self.draft)
        self.assertTrue((self.draft/"publication_failed.json").exists())
        self.save_inventory()
        self.draft = self.directory/"source_changed"
        read = Path.read_bytes
        count = [0]
        def source_changed(path):
            if path==Path(m.__file__):
                count[0] += 1
                if count[0]>1: return b"artificial changed builder"
            return read(path)
        with patch.object(Path,"read_bytes",source_changed), self.assertRaisesRegex(ValueError,"source changed"):
            m.create_draft(self.root,self.inventory_path,self.draft)
        self.assertTrue((self.draft/"publication_failed.json").exists())

    def test_publication_error_after_manifest_write_is_not_a_valid_success(self):
        self.draft_and_selection()
        original = m._write
        def failing(target,data):
            original(target,data)
            if target.name=="manifest.json": raise OSError("Artificial storage failure")
        with patch.object(m,"_write",side_effect=failing), self.assertRaises(OSError): self.freeze()
        self.assertTrue((self.frozen/"manifest.json").exists())
        self.assertTrue((self.frozen/"publication_failed.json").exists())
        digest = hashlib.sha256((self.frozen/"manifest.json").read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,"failure marker"): m.audit_manifest(self.frozen,digest)

    def test_audit_requires_expected_digest_and_rechecks_artifacts_and_inputs(self):
        self.draft_and_selection()
        frozen = self.freeze()
        for missing in (None,"",True):
            with self.assertRaisesRegex(ValueError,"SHA-256"): m.audit_manifest(self.frozen,missing)
        with self.assertRaisesRegex(ValueError,"SHA-256"): m.audit_manifest(self.frozen,"0"*64)
        with self.assertRaises(ValueError): m.audit_manifest(self.draft,frozen["manifest_sha256"])
        (self.frozen/"selection_snapshot.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError,"Artifact hash"): m.audit_manifest(self.frozen,frozen["manifest_sha256"])

    def test_audit_rejects_forged_policy_even_with_updated_external_digest(self):
        self.draft_and_selection()
        self.freeze()
        path = self.frozen/"manifest.json"
        raw = path.read_bytes()
        for field,value in (("evaluation_ready",True),("draft_manifest_sha256","0"*64),("selected_ids",[])):
            record = json.loads(raw)
            record[field] = value
            path.write_bytes(m._encode(record))
            with self.assertRaises(ValueError): m.audit_manifest(self.frozen,hashlib.sha256(path.read_bytes()).hexdigest())

    def test_manifest_builder_import_and_cli_help_do_not_import_research_or_gui_engines(self):
        code = '''import sys, importlib.abc
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'numpy','pandas','sklearn','zstandard','tkinter','pickle'} or fullname in {'src.feature_extractor','src.compressors','src.scoring','src.train_model','smart_compress'}:
   raise AssertionError('Forbidden research import: '+fullname)
sys.meta_path.insert(0,Deny())
from src import unseen_manifest
try: unseen_manifest.main(['--help'])
except SystemExit as exc: assert exc.code==0
'''
        result = subprocess.run([sys.executable,"-B","-c",code],cwd=m.ROOT,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors="replace"))


if __name__=="__main__":
    unittest.main()
