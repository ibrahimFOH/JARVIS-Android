#!/usr/bin/env python3
"""Print PE CodeView RSDS/PDB hints without third-party modules."""
from __future__ import annotations
import hashlib
import struct
import sys
import uuid
from pathlib import Path

def inspect(path: Path) -> None:
    data = path.read_bytes()
    print(f"FILE: {path}")
    print(f"SIZE: {len(data)}")
    print(f"SHA256: {hashlib.sha256(data).hexdigest()}")
    positions, start = [], 0
    while True:
        pos = data.find(b"RSDS", start)
        if pos < 0:
            break
        positions.append(pos)
        start = pos + 1
    if not positions:
        print("CodeView RSDS record: not found\n")
        return
    for pos in positions:
        if pos + 24 > len(data):
            print(f"RSDS at 0x{pos:x}: truncated record")
            continue
        guid_bytes = data[pos + 4:pos + 20]
        age = struct.unpack_from("<I", data, pos + 20)[0]
        end = data.find(b"\0", pos + 24)
        if end < 0:
            end = min(len(data), pos + 24 + 260)
        pdb_path = data[pos + 24:end].decode("utf-8", "replace")
        print(f"RSDS_OFFSET: 0x{pos:x}")
        print(f"PDB_PATH: {pdb_path}")
        print(f"PDB_GUID: {uuid.UUID(bytes_le=guid_bytes)}")
        print(f"PDB_AGE: {age}")
        if b"LLD PDB." in guid_bytes:
            print("NOTE: GUID contains literal ASCII 'LLD PDB.'; this is unusual and does not prove a usable PDB exists.")
        candidate = path.parent / Path(pdb_path).name
        print(f"LOCAL_PDB_CANDIDATE: {candidate if candidate.is_file() else 'absent (' + str(candidate) + ')'}")
        print()

def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {Path(sys.argv[0]).name} file.exe [more-files...]", file=sys.stderr)
        return 2
    for item in sys.argv[1:]:
        path = Path(item).expanduser()
        if not path.is_file():
            print(f"Missing: {path}", file=sys.stderr)
            continue
        inspect(path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
