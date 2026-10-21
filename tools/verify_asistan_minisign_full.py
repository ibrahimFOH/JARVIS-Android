#!/usr/bin/env python3
"""Verify both Minisign payload and trusted-comment/global signatures.

Stricter than the repo's Tauri updater payload verifier, which only checks the
artifact signature. This script does not install or run any executable.
"""
from __future__ import annotations
import argparse, base64, hashlib
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("payload", type=Path)
    p.add_argument("--signature", type=Path, required=True)
    p.add_argument("--public-key", type=Path, required=True)
    a = p.parse_args()
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        print("ERROR: install python3-cryptography")
        return 2
    lines = a.signature.read_text(encoding="utf-8").splitlines()
    comments = [x for x in lines if x.startswith("trusted comment: ")]
    payload_lines = [x for x in lines if x and not x.startswith(("untrusted comment:", "trusted comment:"))]
    if len(comments) != 1 or len(payload_lines) < 2:
        print("ERROR: unexpected Minisign signature file structure")
        return 2
    signature = base64.b64decode(payload_lines[0], validate=True)
    global_signature = base64.b64decode(payload_lines[1], validate=True)
    pub_line = next(x for x in a.public_key.read_text(encoding="utf-8").splitlines()
                    if x and not x.startswith("untrusted comment:"))
    public_key = base64.b64decode(pub_line, validate=True)
    if len(public_key) != 42 or len(signature) != 74 or len(global_signature) != 64:
        print(f"ERROR: unexpected record lengths: key={len(public_key)} signature={len(signature)} global={len(global_signature)}")
        return 2
    if public_key[:2] != b"Ed" or signature[:2] != b"ED":
        print("ERROR: unsupported Minisign key/signature algorithm")
        return 2
    if public_key[2:10] != signature[2:10]:
        print("KEY_ID: MISMATCH")
        return 2
    verifier = Ed25519PublicKey.from_public_bytes(public_key[10:])
    data = a.payload.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    try:
        verifier.verify(signature[10:], hashlib.blake2b(data, digest_size=64).digest())
        print("PAYLOAD_SIGNATURE: VALID")
    except Exception:
        print("PAYLOAD_SIGNATURE: INVALID")
        print("SHA256:", sha)
        return 1
    trusted_comment = comments[0].removeprefix("trusted comment: ").encode("utf-8")
    try:
        verifier.verify(global_signature, signature[10:] + trusted_comment)
        print("TRUSTED_COMMENT_SIGNATURE: VALID")
    except Exception:
        print("TRUSTED_COMMENT_SIGNATURE: INVALID")
    print("KEY_ID:", public_key[2:10][::-1].hex().upper())
    print("SHA256:", sha)
    print("TRUSTED_COMMENT:", trusted_comment.decode("utf-8"))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
