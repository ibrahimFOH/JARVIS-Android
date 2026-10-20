# Asistan EXE Recovery

This folder stores verified findings, recovered frontend assets, and reproducible extraction tools for Asistan 0.1.5.

## Recovery records

- `ASISTAN_EXE_KURTARMA_RAPORU.md`: initial binary analysis.
- `ASISTAN_EXE_KURTARMA_DURUMU.txt`: current Turkish status and known command names.
- `RECOVERED_SOURCE_FILES.md` and `FRONTEND_ASSET_RECOVERY_V4.md`: recovered frontend resource inventory and validation.
- `RECOVERED_FRONTEND_ASSET_MANIFEST.json`: frontend sizes and SHA-256 values.
- `TAURI_COMMAND_SURFACE.md`: desktop native command API inferred from the recovered bridge.
- `PE_RESOURCE_RECOVERY_V5.md`: extracted Windows PE resources (icons, version info, manifest).
- `PE_RESOURCE_MANIFEST.json`: PE resource offsets, sizes, and SHA-256 values.
- `PAYLOAD_TRIAGE.md`, `RAW_PAYLOADS.md`, and `WEBVIEW_CACHE_TRIAGE.md`: prior-stage evidence and limitations.

## Tools

- `../tools/verify_asistan_setup_signature.py`: verifies the v0.1.5 setup payload signature offline when Python `cryptography` is installed.
- `../signatures/`: public updater key and detached signature for the 0.1.5 setup.
- `../tools/inspect_asistan_pe_debug.py`: reads CodeView RSDS/PDB metadata without extra Python modules.
- `../linux/recover_linux.sh`: accepts `7z` or `7zz`, records expected hashes, extracts assets, inspects PDB metadata, and creates a result archive.
- `../linux/recover_linux.sh`: Linux static extraction workflow for the EXE and NSIS setup package.
- `../linux/README_TR.md`: low-resource Linux instructions.
- `../tools/recover_asistan_frontend_v4.py`: decompresses the frontend Brotli streams.
- `../tools/extract_asistan_pe_resources.py`: extracts the Windows icons, icon group, version info and manifest.

- `PDB_AND_UPDATER_RESEARCH_V7.md`: public updater metadata and PDB/debug findings.
- `FRONTEND_API_SURFACE_V7.md`: external services and native command surface found in the recovered frontend.

## Latest verified findings

The v5 local archive includes 18 recovered frontend assets: the HTML entry page, eight JavaScript files, two CSS files and seven WOFF2 fonts. All eight JavaScript files passed Node.js syntax validation. The Windows `.rsrc` section also provided six PNG icon sizes, a reconstructed `.ico`, version metadata and an application manifest. Both extraction passes were re-run against the original executable and compared byte-for-byte with the packaged outputs.

Original EXE SHA-256: `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`.

The complete v5 ZIP contains binary icon/font resources that are not all committed as individual binary files here. The repository records the extraction tools, manifests, core frontend pieces and findings.

## Limitations

This is not the complete original Tauri/Rust project. The full Rust backend sources, `Cargo.toml`, `tauri.conf.json`, and the exact original build pipeline were not recovered. Browser history, cookies and unrelated WebView2 profile state are intentionally excluded because they may contain personal data.


Note: files in `recovered_frontend/` on GitHub include manually curated/transcribed excerpts from earlier steps and are not guaranteed byte-identical. Use the v7 recovery ZIP's `recovered_frontend/` folder as the canonical recovered frontend and its SHA-256 manifest for verification.
