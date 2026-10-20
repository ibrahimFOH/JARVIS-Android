#!/usr/bin/env python3
"""Verify the Asistan 0.1.5 setup against the public Tauri updater signature.
Requires Python package 'cryptography'. Checks the payload signature, not the
separate trusted-comment/global signature.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
from pathlib import Path

KNOWN_SHA256 = "485cbd596960754590f80f5c7adb05b96e11961d82a8b7a956fabb426f4f3b09"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIG = ROOT / "signatures" / "Asistan_0.1.5_x64-setup.exe.sig"
DEFAULT_KEY = ROOT / "signatures" / "asistan_updater_public_key.txt"

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("setup", type=Path)
    ap.add_argument("--signature", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--public-key", type=Path, default=DEFAULT_KEY)
    args = ap.parse_args()
    setup = args.setup.expanduser().resolve()
    if not setup.is_file():
        ap.error(f"Setup file not found: {setup}")
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        print("Missing Python cryptography module. Debian/Ubuntu: sudo apt install python3-cryptography")
        return 2
    raw_lines = args.signature.read_text(encoding="utf-8").splitlines()
    sig_line = next((x for x in raw_lines if x and not x.startswith(("untrusted comment:", "trusted comment:"))), None)
    key_lines = args.public_key.read_text(encoding="utf-8").splitlines()
    pub_line = next((x for x in key_lines if x and not x.startswith("untrusted comment:")), None)
    if not sig_line or not pub_line:
        raise SystemExit("Signature or public key payload line missing")
    sig = base64.b64decode(sig_line, validate=True)
    key = base64.b64decode(pub_line, validate=True)
    if len(sig) != 74 or len(key) != 42 or sig[:2] != b"ED" or key[:2] != b"Ed":
        raise SystemExit("Unexpected minisign key/signature record format")
    if sig[2:10] != key[2:10]:
        raise SystemExit("Signature key ID does not match updater public key")
    data = setup.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    digest = hashlib.blake2b(data, digest_size=64).digest()
    public_key = Ed25519PublicKey.from_public_bytes(key[10:])
    try:
        public_key.verify(sig[10:], digest)
    except Exception:
        print(f"SIGNATURE: FAIL\nSHA256: {sha}")
        return 1
    print("SIGNATURE: VALID")
    print("METHOD: Ed25519 signature over BLAKE2b-512 digest")
    print("KEY_ID: " + key[2:10][::-1].hex().upper())
    print("SHA256: " + sha)
    print("KNOWN_SETUP_SHA256: " + ("MATCH" if sha == KNOWN_SHA256 else "DIFFERENT_FILE_BUT_SIGNATURE_VALID"))
    for line in raw_lines:
        if line.startswith("trusted comment:"):
            print("UPDATER_COMMENT: " + line)
            break
    print("NOTE: The payload signature is verified; the separate trusted-comment signature is not checked by this script.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
