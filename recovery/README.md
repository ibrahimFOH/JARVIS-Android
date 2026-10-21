# Asistan EXE Recovery

This folder stores verified findings, recovered frontend assets, reproducible extraction tools, and Android porting notes for Asistan 0.1.5.

## Reports

- `ASISTAN_EXE_KURTARMA_RAPORU.md`: initial binary analysis.
- `RECOVERED_SOURCE_FILES.md`, `FRONTEND_ASSET_RECOVERY_V4.md`, `RECOVERED_FRONTEND_ASSET_MANIFEST.json`: recovered frontend inventory and hashes.
- `TAURI_COMMAND_SURFACE.md`: native command surface inferred from the JS bridge.
- `PE_RESOURCE_RECOVERY_V5.md`, `PE_RESOURCE_MANIFEST.json`: extracted Windows icons, version info, manifest and hashes.
- `PDB_AND_UPDATER_RESEARCH_V7.md`, `FRONTEND_API_SURFACE_V7.md`: debug and external-service findings.
- `NSIS_SCRIPT_DECOMPILATION_V8.md`, `PE_STATIC_TRIAGE_V8.md`, `LOCAL_RECOVERY_VERIFICATION_V8.md`: installer format and repeatable static verification.
- `NATIVE_BACKEND_STATIC_FINDINGS_V9.md`, `STATIC_FINDINGS_MANIFEST_V9.json`: Tauri commands, dependencies and credential-storage clues.
- `RECOVERY_AND_ANDROID_PORTING_V10.md`, `REVERSE_ENGINEERING_MANIFEST_V10.json`: Rust crate path inventory, PDB identity and Android porting matrix.
- `SETUP_SIGNATURE_VALIDATION_V11.md`, `REVERSE_ENGINEERING_MANIFEST_V11.json`: Tauri updater payload signature verification.
- `SETUP_SIGNATURE_VALIDATION_V12.md`, `REVERSE_ENGINEERING_MANIFEST_V12.json`: independent Minisign global-signature check.

## Tools

- `../tools/verify_asistan_setup_signature.py`: verifies the setup's payload signature.
- `../tools/verify_asistan_minisign_full.py`: also checks Minisign's trusted-comment/global signature.
- `../signatures/`: public updater key and signature file.
- `../tools/inspect_asistan_pe_debug.py`: reads CodeView RSDS/PDB metadata.
- `../linux/recover_linux.sh`, `../linux/README_TR.md`: static recovery and low-resource Linux workflow.
- `../tools/recover_asistan_frontend_v4.py`: decompresses frontend Brotli streams.
- `../tools/extract_asistan_pe_resources.py`: extracts Windows icons, version info and manifest.

## Latest verified findings

- EXE SHA-256: `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`.
- 18 frontend files were extracted and compared byte-for-byte with the V5 archive; 8/8 JavaScript syntax checks passed.
- The EXE contains 98 distinct Rust crate/version source-path pairs. These are not a recovered `Cargo.toml` and do not prove all are direct dependencies.
- CodeView references `asistan.pdb`; matching PDB and Rust source files were not recovered.
- The setup payload signature is valid and the SHA-256 matches the recorded hash. A separate standard Minisign trusted-comment/global-signature check failed. This does **not** invalidate the payload signature, but the comment's integrity remains unverified. Details are in V12.
- The separate Android app `JARVIS_ANDROID`, package `com.stagepulse.jarvis`, version `2.2.0-piper`, built successfully in [GitHub Actions run #129](https://github.com/ibrahimFOH/JARVIS-Android/actions/runs/39582942609). The APK passed ZIP integrity checks; it has not been tested on a physical device/emulator and is not an automatic conversion of the Asistan Windows EXE.

## Limitations

The original Rust/Tauri function bodies, `Cargo.toml`, `tauri.conf.json`, and exact build pipeline were not recovered. The NSIS setup payload and `[NSIS].nsi` also remain unextracted here: no `7z/7zz` binary is installed and shell DNS/network access failed. A Linux-only 7-Zip NSIS build path is documented in `../linux/README_TR.md`, but is not built/tested in this environment.

The local V12 recovery ZIP contains the verified frontend assets, PE resources, signature material and reports. Earlier files in `recovered_frontend/` are manually curated/transcribed excerpts and are not guaranteed byte-identical; use the validated local package and its manifest as canonical. User WebView/Edge profile data, history, cookies and cache are excluded.
