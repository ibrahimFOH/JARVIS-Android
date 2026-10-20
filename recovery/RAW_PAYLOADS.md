# Raw payloads and reproducible extraction

The original EXE and payload files are not committed as opaque binary blobs in this public repository. Instead, the exact offsets, sizes and SHA-256 hashes are documented in `asset-payload-manifest.json`, and `tools/recover_asistan_assets.py` extracts every recorded payload from the original `asistan.exe`.

## Run

```bash
python tools/recover_asistan_assets.py /path/to/asistan.exe --out recovery/raw-assets
```

The script writes 15 `.bin` files and `extraction-report.json`. Each result is hash-checked against the recorded SHA-256. A hash mismatch stops being a valid recovery result and is reported as such.

## What these files are

These are raw byte ranges from the executable, associated with embedded asset markers. They are **not guaranteed to be valid source files**. Some ranges may contain binary framing, compressed content, or adjacent build artefacts. Do not rename them to `.js` or `.html` until decoding and syntax validation succeeds.

## Other recoverable facts

- Tauri 2 / Rust native executable.
- Embedded web asset names and offsets are in the manifest.
- Native command name traces and known hashes are in `ASISTAN_EXE_KURTARMA_DURUMU.txt`.
- V8 Code Cache files in the supplied user archive were only identified by their paths and sizes; their complete recovered source is not verified.
- No complete original Rust project or valid complete JavaScript source has yet been recovered.

This repository intentionally excludes browser history and general user browsing profile data. Such data is not application source and can expose personal information.
