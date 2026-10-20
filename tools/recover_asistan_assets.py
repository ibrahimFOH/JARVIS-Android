#!/usr/bin/env python3
"""Re-extract the raw embedded asset payloads from the original Asistan EXE.

Usage:
  python tools/recover_asistan_assets.py /path/to/asistan.exe --out recovery/raw-assets

The output files are raw bytes, not necessarily decoded HTML/JavaScript/CSS.
The manifest is intentionally explicit so extraction is reproducible.
"""
import argparse
import hashlib
import json
from pathlib import Path

ASSETS = [
    {"name": "index_html_0045c8b2.bin", "offset": 4573373, "size": 4071, "sha256": "5e384ffdb745b6d7aa71324459b33b3558c1871a434f66ec5e4e4601e263ec20"},
    {"name": "index_html_0046e2f9.bin", "offset": 4645636, "size": 25246, "sha256": "9691d8f50ccf37db948bf91a25c6aad0ca605df4e060d1db87ea2668f0be9617"},
    {"name": "index_html_0049b168.bin", "offset": 4829555, "size": 1597, "sha256": "9b0992d8e77c9e2e5eb3357c538d9fe6611b258b1dbf7765f7b2adfb7bac2521"},
    {"name": "index_html_0049b7b0.bin", "offset": 4831163, "size": 375147, "sha256": "b562fbdd3320d0763e12e4b9256ba0649dc27fca96da86be4fe6b63b22374ba7"},
    {"name": "index_html_004f7126.bin", "offset": 5206321, "size": 662735, "sha256": "ff3f1519bc2dc27bafb173e3da78683a079fb92f140948c2d33149e82d8245b1"},
    {"name": "kaynak_js_0045d8a4.bin", "offset": 4577454, "size": 3546, "sha256": "0a68dcad2fdd34e305739da35501f59e2b6de877bdceb9145de04edc237a2d39"},
    {"name": "uygulama_js_0045e688.bin", "offset": 4581012, "size": 26424, "sha256": "f98b4016757f997155cd1e023e8bdfb0abfdc7550d3012ff6efd35a545417f25"},
    {"name": "stil_css_00464dcc.bin", "offset": 4607445, "size": 6317, "sha256": "5693b689fc30ae3b06493e9050209ff33fd41a3000c6e2c0412975fa0a4727be"},
    {"name": "sozlesme_js_00466682.bin", "offset": 4613774, "size": 6882, "sha256": "b17c1911535bb1cd7f27ec53604f7d84f466eb2e3acd8d53a9b3ee523a2d0918"},
    {"name": "kopru_js_00468170.bin", "offset": 4620665, "size": 1847, "sha256": "db1e99907d962afe1a7b2d499f4d9d014a5a855f433f112cb63baf7a9605278c"},
    {"name": "zeka_js_004688b0.bin", "offset": 4622520, "size": 22678, "sha256": "32dce9ab941cee605c3394425a5adb00d7e5a0c1265d746476836cb064e5b33f"},
    {"name": "canli_js_004745a2.bin", "offset": 4670891, "size": 20672, "sha256": "9bab1f47c4896fe12aaae6bf88886e0e1c6a9b1f8d5aa41ed3aa325f8233b961"},
    {"name": "komut_js_0047966b.bin", "offset": 4691572, "size": 11057, "sha256": "068adcb573c18dd37b5d8b24a9f1fc66eb406566ff925b0cc6e607fb7346608b"},
    {"name": "kure_js_0047c1a5.bin", "offset": 4702637, "size": 126907, "sha256": "ef82f77a87ac6959718a78fb5ae3ccdca243c0ba0d72babab24b96ca1051a6f6"},
    {"name": "yazitipi_yazitipi_css_0046e14e.bin", "offset": 4645220, "size": 405, "sha256": "9c9a8c5377fbde05db8879d990a346c9dbcc14c3c471110a4a59c7ff4deb16d7"},
]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("exe", type=Path)
    p.add_argument("--out", type=Path, default=Path("recovery/raw-assets"))
    args = p.parse_args()
    data = args.exe.read_bytes()
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for item in ASSETS:
        payload = data[item["offset"]:item["offset"] + item["size"]]
        actual = hashlib.sha256(payload).hexdigest()
        ok = len(payload) == item["size"] and actual == item["sha256"]
        if not payload or len(payload) != item["size"]:
            raise SystemExit(f"Invalid extraction length for {item['name']}: {len(payload)}")
        dest = args.out / item["name"]
        dest.write_bytes(payload)
        results.append({**item, "actual_sha256": actual, "verified": ok})
        print(("OK" if ok else "HASH MISMATCH"), dest, len(payload), actual)
    (args.out / "extraction-report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    if not all(x["verified"] for x in results):
        raise SystemExit("At least one extracted payload did not match the recorded hash.")
if __name__ == "__main__":
    main()
