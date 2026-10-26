"""Read-only rights/privacy review material; no automatic approval or ML.

Detailed original contexts stay in ignored data/temp. The published review must
contain decisions and evidence locations, not copies of potential identifiers.
"""
from collections import Counter
from datetime import datetime, timezone
import ast
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tokenize
import zipfile

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "data/results/real_unseen/real_candidates_20261026_02"
DEST = ROOT / "data/temp/unseen_content_review_20261026_01"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, obj):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def risk_contexts(text):
    patterns = {
        "rights": r"(?i)copyright|SPDX|licen[cs]e|public.domain|permission|derived.from|adapted.from|copied.from|based.on.*(?:code|source)|commercial|research.only|redistribut",
        "contact": r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "home_path": r"(?:[A-Za-z]:\\Users\\|/home/|/Users/)",
        "network": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "secret_like": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:ghp_|github_pat_|AKIA|sk-proj-)[A-Za-z0-9_\-]{12,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}",
    }
    lines = text.splitlines()
    output = {}
    for label, pattern in patterns.items():
        output[label] = [dict(line=i+1, context="\n".join(lines[max(0,i-1):min(len(lines),i+2)]))
                         for i, line in enumerate(lines) if re.search(pattern,line)]
    return output


def font_names(data):
    tables = struct.unpack(">H",data[4:6])[0]
    directory = {}
    for i in range(tables):
        tag, checksum, offset, size = struct.unpack(">4sIII",data[12+16*i:28+16*i])
        assert offset+size <= len(data)
        directory[tag.decode("ascii")] = dict(offset=offset,size=size)
    table = directory["name"]
    block = data[table["offset"]:table["offset"]+table["size"]]
    version,count,strings = struct.unpack(">HHH",block[:6])
    names = []
    for i in range(count):
        platform,encoding,language,name_id,size,offset = struct.unpack(">HHHHHH",block[6+i*12:18+i*12])
        value = block[strings+offset:strings+offset+size]
        assert len(value) == size
        text = value.decode("utf-16-be" if platform in (0,3) else "mac_roman")
        item = dict(name_id=name_id,value=text)
        if item not in names:
            names.append(item)
    return dict(table_tags=sorted(directory),name_table_version=version,names=names)


def shapefile(data):
    assert data[:4] == struct.pack(">i",9994)
    assert struct.unpack(">i",data[24:28])[0]*2 == len(data)
    assert struct.unpack("<i",data[28:32])[0] == 1000
    global_type = struct.unpack("<i",data[32:36])[0]
    assert global_type in (3,5)
    offset,records = 100,0
    while offset<len(data):
        number,size = struct.unpack(">ii",data[offset:offset+8])
        end = offset+8+size*2
        assert end<=len(data) and number==records+1
        record = data[offset+8:end]
        shape = struct.unpack("<i",record[:4])[0]
        assert shape in (0,global_type)
        if shape:
            parts,points = struct.unpack("<ii",record[36:44])
            assert parts>=1 and points>=1 and len(record)==44+4*parts+16*points
            indices=struct.unpack("<"+"i"*parts,record[44:44+4*parts])
            assert indices[0]==0 and list(indices)==sorted(indices) and indices[-1]<points
        offset,records=end,records+1
    assert offset==len(data)
    return dict(shape_type=global_type,records_validated=records,record_content="Numeric polyline/polygon geometry only; no DBF attributes included")


def main():
    inv=json.loads((POOL/"inventory.json").read_bytes())
    acquisition=json.loads((POOL/"acquisition.json").read_bytes())
    raw=ROOT/acquisition["raw_root"]
    plan=json.loads((POOL/"collection_plan_snapshot.json").read_bytes())
    uci={g["origin_group_id"]:g for g in plan["uci_groups"]}
    protected=set(json.loads((POOL/"protected_after.json").read_bytes()))
    protected.update(p.relative_to(ROOT).as_posix() for folder in (raw,POOL) for p in folder.rglob("*") if p.is_file())
    before={p:sha((ROOT/p).read_bytes()) for p in sorted(protected)}
    if DEST.exists():
        raise ValueError("Refusing existing inspection output")
    DEST.mkdir(parents=True)
    save(DEST/"protected_before.json",before)
    results=[]
    for row in inv["candidates"]:
        data=(raw/row["relative_path"]).read_bytes()
        assert len(data)==row["original_size"] and sha(data)==row["input_sha256"]
        item=dict(candidate_id=row["candidate_id"],format=row["format"],origin_group_id=row["origin_group_id"],input_sha256=sha(data))
        if row["format"]=="binary":
            item["structured"]=font_names(data) if row["origin_group_id"]=="google_fonts" else shapefile(data)
        else:
            encoding=uci[row["origin_group_id"]]["encoding"] if row["format"]=="csv" else "utf-8"
            text=data.decode(encoding)
            item["contexts"]=risk_contexts(text)
            if row["format"]=="python":
                tree=ast.parse(text)
                item["structured"]=dict(top_level_nodes=[type(n).__name__ for n in tree.body],
                    literal_payloads=[dict(line=n.lineno,length=len(n.value),prefix=n.value[:160]) for n in ast.walk(tree)
                                      if isinstance(n,ast.Constant) and isinstance(n.value,(str,bytes)) and len(n.value)>8192])
                # tokenize traverses the whole original source without execution.
                list(tokenize.generate_tokens(io.StringIO(text).readline))
            elif row["format"]=="csv":
                group=uci[row["origin_group_id"]]
                rows=list(csv.reader(io.StringIO(text,newline=""),delimiter=group["delimiter"]))
                assert rows and len({len(r) for r in rows if r})==1
                # List all non-numeric values, not a sample of rows, for domain review.
                values=sorted({v for r in rows for v in r if not re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?",v.strip())})
                item["structured"]=dict(rows_parsed=len(rows),columns=len(rows[0]),non_numeric_values=values)
            elif row["format"]=="json":
                obj=json.loads(text)
                leaves=[]
                def visit(value,path):
                    if isinstance(value,dict):
                        for k,v in value.items(): visit(v,path+[str(k)])
                    elif isinstance(value,list):
                        for i,v in enumerate(value): visit(v,path+[str(i)])
                    else: leaves.append(("/".join(path),value))
                visit(obj,[])
                item["structured"]=dict(top_level_keys=list(obj),strings_review=[dict(path=k,value=v) for k,v in leaves if isinstance(v,str) and
                    re.search(r"(?i)licen[cs]e|author|publisher|repository|homepage|password|secret|token|api.?key|credential|(?:^|/)default$",k)],
                    contact_or_secret_values=[dict(path=k,value=v) for k,v in leaves if isinstance(v,str) and any(risk_contexts(v)[label] for label in ("contact","home_path","secret_like"))])
            elif row["format"]=="log":
                logs=[]
                other=[]
                for i,line in enumerate(text.splitlines(),1):
                    if ":::MLLOG" in line:
                        payload=line.split(":::MLLOG",1)[1].strip()
                        logs.append((i,json.loads(payload)))
                    elif line.strip(): other.append(dict(line=i,value=line))
                keys=sorted({entry.get("key","") for _,entry in logs})
                files=sorted({str(entry.get("metadata",{}).get("file","")) for _,entry in logs})
                identifiers=[dict(line=i,key=entry.get("key"),value=entry.get("value")) for i,entry in logs
                             if re.search(r"(?i)submission|contact|user|host|node|token|secret|path|directory",entry.get("key",""))]
                item["structured"]=dict(records_parsed=len(logs),record_keys=keys,source_paths=files,identifiers=identifiers,non_mllog_lines=other)
        results.append(item)
    notices=[]
    for path in sorted((raw/"notices").rglob("*")):
        if path.is_file():
            data=path.read_bytes()
            if path.suffix in (".txt",".md") or path.name in ("COPYING","LICENSE"):
                notices.append(dict(path=path.relative_to(raw).as_posix(),input_sha256=sha(data),text=data.decode("utf-8")))
    archive_notes=[]
    for path in sorted((raw/"archives").glob("*.zip")):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir() and re.search(r"(?i)names$|readme|licen[cs]e|copying",info.filename):
                    data=z.read(info)
                    archive_notes.append(dict(archive=path.relative_to(raw).as_posix(),member=info.filename,input_sha256=sha(data),text=data.decode("utf-8",errors="replace")))
    after={p:sha((ROOT/p).read_bytes()) for p in sorted(protected)}
    assert before==after
    save(DEST/"inspection.json",dict(created_at_utc=utc(),execution_git_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        inspector_sha256=sha(Path(__file__).read_bytes()),raw_root=raw.relative_to(ROOT).as_posix(),protected_files=len(before),
        protected_unchanged=True,candidates=results,notices=notices,archive_notes=archive_notes,
        scope="Read-only full-file parsing/scanning plus review contexts, not automatic approval; potential context values remain in ignored output"))
    save(DEST/"protected_after.json",after)
    print(json.dumps(dict(candidates=len(results),by_format=dict(Counter(r["format"] for r in results)),protected_files_unchanged=len(before),output=DEST.relative_to(ROOT).as_posix())))


def utc():
    return datetime.now(timezone.utc).isoformat()


if __name__=="__main__": main()
