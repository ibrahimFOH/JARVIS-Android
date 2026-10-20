#!/usr/bin/env python3
"""Extract Brotli-packed frontend assets from the analyzed Asistan Windows EXE."""
import argparse, hashlib, json
from pathlib import Path
import brotli

KNOWN_SHA256 = "03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8"
# output path, embedded resource marker, expected output signature
ASSETS = [
 ("index.html", b"/index.html", b"<!DOCTYPE html"),
 ("kaynak.js", b"/kaynak.js", b"/*"),
 ("uygulama.js", b"/uygulama.js", b"/*"),
 ("stil.css", b"/stil.css", b"/*"),
 ("sozlesme.js", b"/sozlesme.js", b"/*"),
 ("kopru.js", b"/kopru.js", b"/*"),
 ("zeka.js", b"/zeka.js", b"/*"),
 ("canli.js", b"/canli.js", b"/*"),
 ("komut.js", b"/komut.js", b"/*"),
 ("kure.js", b"/kure.js", b"/*"),
 ("yazitipi/yazitipi.css", b"/yazitipi/yazitipi.css", b"/*"),
 ("yazitipi/ShareTechMono-400-latin.woff2", b"/yazitipi/ShareTechMono-400-latin.woff2", b"wOF2"),
 ("yazitipi/Rajdhani-600-latin.woff2", b"/yazitipi/Rajdhani-600-latin.woff2", b"wOF2"),
 ("yazitipi/Rajdhani-700-latin-ext.woff2", b"/yazitipi/Rajdhani-700-latin-ext.woff2", b"wOF2"),
 ("yazitipi/Rajdhani-700-latin.woff2", b"/yazitipi/Rajdhani-700-latin.woff2", b"wOF2"),
 ("yazitipi/Rajdhani-500-latin-ext.woff2", b"/yazitipi/Rajdhani-500-latin-ext.woff2", b"wOF2"),
 ("yazitipi/Rajdhani-500-latin.woff2", b"/yazitipi/Rajdhani-500-latin.woff2", b"wOF2"),
 ("yazitipi/Rajdhani-600-latin-ext.woff2", b"/yazitipi/Rajdhani-600-latin-ext.woff2", b"wOF2"),
]

def decode_after(data, start, max_bytes=2_000_000):
    decoder, out, used = brotli.Decompressor(), bytearray(), 0
    stop = min(len(data), start + max_bytes)
    while start + used < stop:
        out.extend(decoder.process(data[start + used:start + used + 1]))
        used += 1
        if decoder.is_finished():
            return bytes(out), used
    raise ValueError("Brotli stream did not finish")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("exe", type=Path)
    ap.add_argument("--output", type=Path, default=Path("recovered_frontend"))
    ap.add_argument("--allow-different-exe", action="store_true")
    args = ap.parse_args()
    data = args.exe.read_bytes()
    exe_sha = hashlib.sha256(data).hexdigest()
    if exe_sha != KNOWN_SHA256 and not args.allow_different_exe:
        ap.error("EXE SHA-256 differs from the analyzed build; use --allow-different-exe to override")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"source_exe": args.exe.name, "source_exe_sha256": exe_sha, "resources": []}
    for name, marker, signature in ASSETS:
        pos, chosen = 0, None
        while True:
            pos = data.find(marker, pos)
            if pos < 0: break
            try:
                start = pos + len(marker)
                decoded, used = decode_after(data, start)
                if decoded.startswith(signature) or decoded.lstrip().startswith(signature):
                    chosen = (pos, start, used, decoded)
                    break
            except Exception:
                pass
            pos += 1
        if chosen is None:
            raise SystemExit("Could not decode: " + name)
        marker_offset, payload_offset, compressed_bytes, decoded = chosen
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(decoded)
        manifest["resources"].append({
            "path": name, "marker_offset": marker_offset, "payload_offset": payload_offset,
            "compressed_bytes": compressed_bytes, "decoded_bytes": len(decoded),
            "sha256": hashlib.sha256(decoded).hexdigest()
        })
        print(f"OK {name}: {len(decoded)} bytes")
    (args.output / "RECOVERY_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Recovered", len(manifest["resources"]), "assets.")

if __name__ == "__main__":
    main()
