# Asistan EXE Recovery

This folder stores verified findings, recovered frontend assets, reproducible extraction tools, and Android porting notes for Asistan 0.1.5.

## Recovery records

- `ASISTAN_EXE_KURTARMA_RAPORU.md`: initial binary analysis.
- `ASISTAN_EXE_KURTARMA_DURUMU.txt`: current Turkish status and known command names.
- `RECOVERED_SOURCE_FILES.md` and `FRONTEND_ASSET_RECOVERY_V4.md`: recovered frontend resource inventory and validation.
- `RECOVERED_FRONTEND_ASSET_MANIFEST.json`: frontend sizes and SHA-256 values.
- `TAURI_COMMAND_SURFACE.md`: desktop native command API inferred from the recovered bridge.
- `PE_RESOURCE_RECOVERY_V5.md` and `PE_RESOURCE_MANIFEST.json`: extracted Windows icons, version info, manifest and hashes.
- `PDB_AND_UPDATER_RESEARCH_V7.md`: public updater metadata and PDB/debug findings.
- `FRONTEND_API_SURFACE_V7.md`: external services and native command surface found in the recovered frontend.
- `NSIS_SCRIPT_DECOMPILATION_V8.md`: difference between payload extraction and script decompilation.
- `PE_STATIC_TRIAGE_V8.md`: PE format, section layout and imported Windows library inventory.
- `LOCAL_RECOVERY_VERIFICATION_V8.md`: fresh rerun confirms 18/18 frontend files byte-identical to the V5 archive and all 8 JavaScript files pass syntax checks.
- `NATIVE_BACKEND_STATIC_FINDINGS_V9.md`: 34 Tauri bridge commands, dependency/version traces and credential-storage evidence.
- `STATIC_FINDINGS_MANIFEST_V9.json`: machine-readable V9 findings.
- `RECOVERY_AND_ANDROID_PORTING_V10.md`: exhaustive asset-path scan, Rust crate/version-path inventory, PDB identity and Android porting matrix.
- `REVERSE_ENGINEERING_MANIFEST_V10.json`: machine-readable V10 recovery and APK CI verification record.

## Tools

- `../tools/verify_asistan_setup_signature.py`: verifies the v0.1.5 setup payload signature offline when Python `cryptography` is installed.
- `../signatures/`: public updater key and detached signature for the 0.1.5 setup.
- `../tools/inspect_asistan_pe_debug.py`: reads CodeView RSDS/PDB metadata.
- `../linux/recover_linux.sh`: static extraction workflow for EXE and NSIS setup package.
- `../linux/README_TR.md`: low-resource Linux instructions, including the Linux-specific NSIS script-decompilation build path.
- `../tools/recover_asistan_frontend_v4.py`: decompresses frontend Brotli streams.
- `../tools/extract_asistan_pe_resources.py`: extracts Windows icons, icon group, version info and manifest.

## Latest verified findings

- Original EXE SHA-256: `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`.
- 18 frontend resources were extracted and compared byte-for-byte with the V5 archive; 8/8 JavaScript syntax checks passed.
- The EXE has 98 distinct Rust crate/version source-path pairs in debug strings. These are not a recovered `Cargo.toml` and must not be interpreted as direct dependencies only.
- CodeView references `asistan.pdb`; no matching PDB or Rust source files were recovered.
- GitHub Actions successfully built the separate `JARVIS_ANDROID` app as `com.stagepulse.jarvis` (version `2.2.0-piper`). The CI APK was structurally checked, but has not been tested on a physical device/emulator.

## Important limitations

This is not the complete original Tauri/Rust project. The full Rust backend function bodies, `Cargo.toml`, `tauri.conf.json`, and original build pipeline were not recovered. The NSIS setup payload and `[NSIS].nsi` also remain unextracted in this environment; there is no `7z/7zz` binary here and shell DNS/network access failed.

The original EXE's exact frontend sources and assets are in the locally downloadable V10 package produced for this investigation. Binary fonts/icons are not all committed as individual source files here. Earlier files in `recovered_frontend/` are manually curated/transcribed excerpts and are not guaranteed byte-identical; use the validated V10 local recovery package and its manifests as canonical.

The user's supplied `Asistan.zip` includes a WebView/Edge profile with history/cache/metrics. Personal profile contents are excluded from recovery bundles and repository commits.
