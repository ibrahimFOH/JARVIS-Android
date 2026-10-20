#!/usr/bin/env python3
"""Extract verified Windows PE resources from the analyzed Asistan EXE."""
import argparse, hashlib, json, struct
from pathlib import Path

EXPECTED_SHA256 = "03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8"
PNG_RESOURCES = [
    (1,"icon-16.png",0x584C58,705),
    (2,"icon-24.png",0x584F20,1184),
    (3,"icon-32.png",0x5853C0,1997),
    (4,"icon-48.png",0x585B90,4063),
    (5,"icon-64.png",0x586B70,6414),
    (6,"icon-256.png",0x588480,44422),
]
GROUP_ICON=(0x593208,90)
OTHER=[
 ("version_info_resource.bin",0x584A20,564,b"\x34\x02\x34\x00"),
 ("application.manifest",0x593268,334,b" <assembly"),
]
PNG=b"\x89PNG\r\n\x1a\n"

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("exe",type=Path)
    ap.add_argument("--output",type=Path,default=Path("recovered_pe_resources"))
    a=ap.parse_args()
    data=a.exe.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if digest!=EXPECTED_SHA256:
        ap.error("EXE SHA-256 mismatch; refusing to apply fixed offsets to a different build")
    out=a.output.resolve(); icons=out/"icons"; icons.mkdir(parents=True,exist_ok=True)
    manifest={"source_exe":a.exe.name,"source_exe_sha256":digest,"resources":[]}
    images={}
    for rid,name,off,n in PNG_RESOURCES:
        b=data[off:off+n]
        if len(b)!=n or not b.startswith(PNG): raise SystemExit("PNG validation failed: "+name)
        (icons/name).write_bytes(b); images[rid]=b
        manifest["resources"].append({"path":"icons/"+name,"resource_id":rid,"file_offset":off,"bytes":n,"sha256":hashlib.sha256(b).hexdigest()})
        print("OK",name,n)
    off,n=GROUP_ICON
    group=data[off:off+n]
    if len(group)!=n or struct.unpack_from("<HHH",group,0)!=(0,1,6): raise SystemExit("group icon header mismatch")
    entries=[]; payload=b""; first=6+16*6
    for i in range(6):
        w,h,colors,res,planes,bits,size,rid=struct.unpack_from("<BBBBHHIH",group,6+i*14)
        b=images.get(rid)
        if b is None or len(b)!=size: raise SystemExit("group icon entry mismatch")
        entries.append(struct.pack("<BBBBHHII",w,h,colors,res,planes,bits,size,first+len(payload)))
        payload+=b
    ico=struct.pack("<HHH",0,1,6)+b"".join(entries)+payload
    (out/"asistan.ico").write_bytes(ico)
    manifest["resources"].append({"path":"asistan.ico","file_offset":off,"group_resource_bytes":n,"bytes":len(ico),"sha256":hashlib.sha256(ico).hexdigest()})
    for name,off,n,prefix in OTHER:
        b=data[off:off+n]
        if len(b)!=n or not b.startswith(prefix): raise SystemExit("resource validation failed: "+name)
        (out/name).write_bytes(b)
        manifest["resources"].append({"path":name,"file_offset":off,"bytes":n,"sha256":hashlib.sha256(b).hexdigest()})
        print("OK",name,n)
    (out/"PE_RESOURCE_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("ICO built; manifest saved.")

if __name__=="__main__": main()
