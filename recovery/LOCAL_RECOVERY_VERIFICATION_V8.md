# Local recovery verification V8

Date: 2026-10-21

## Verification environment

The supplied files were present in the active analysis environment. The following SHA-256 values were recalculated:

- asistan.exe: 03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8
- Asistan_0.1.5_x64-setup(1).exe: 485cbd596960754590f80f5c7adb05b96e11961d82a8b7a956fabb426f4f3b09
- uninstall.exe: ea53e123817670550bccb072d9f61dde1ae8cc723627974ef5668b0b83f9f1c1

All three match the previously recorded sample hashes.

## Frontend extraction rerun

The V5 frontend recovery script was extracted from the supplied recovery ZIP and run against the actual `asistan.exe`.

- 18 of 18 frontend resources recovered successfully.
- All 18 recovered files were compared byte-for-byte with the corresponding files in the V5 ZIP.
- Mismatches: 0.
- All 8 recovered JavaScript files passed `node --check`.

This confirms the extraction is reproducible for the EXE with the recorded hash.

## PE resource extraction rerun

The V5 PE resource extraction tool was run against the same EXE.

- Six PNG icon resources recovered.
- Version information resource recovered.
- Application manifest recovered.
- Multi-size ICO rebuilt from the recovered icon sizes.

The extractor reported successful output for all expected resources. The standalone run was not a comparison against every separately committed GitHub binary because the repository intentionally does not contain all binary resources.

## Setup static triage

The setup installer is identified by `file` as a PE32 x86 Nullsoft Installer self-extracting archive, with the embedded manifest reporting NSIS 3.13. The supplied installer and uninstaller have matching hashes from the prior analysis.

This environment has GNU `objdump`, `strings`, Python Brotli and Python cryptography, but no `7z` or `7zz` executable. Therefore this pass did not extract the NSIS payload or the compiled script. The missing tool is a real blocker for the next setup-extraction step, not evidence that the setup has no useful contents.

## Next high-value step

Run the documented Linux extraction script with 7-Zip on the user's Linux machine, then inspect the generated listing, test and extraction logs. If ordinary extraction succeeds, inventory all files and compare the setup payload to the already recovered application resources. If it fails, test the specialized 7-Zip/NSIS decompiler path documented in `NSIS_SCRIPT_DECOMPILATION_V8.md`.

## Scope and limitations

This is a reproducibility check of frontend and PE-resource extraction, not a full recovery of the original Rust/Tauri source project. The native backend source, Cargo manifest, Tauri config and matching PDB remain unavailable.
