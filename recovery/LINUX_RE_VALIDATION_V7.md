# Linux recovery v7 validation (2026-10-21)

Validated in the current work environment:

- `bash -n linux/recover_linux.sh`: passed.
- `py_compile` passed for the Python recovery tools.
- 18 frontend resources were recovered from the known EXE and compared byte-for-byte with the packaged resources.
- All eight JavaScript files passed Node.js `--check` (`js_ok=8`, `js_bad=0`).
- PE extraction emitted six PNG sizes, an ICO, version information and an application manifest; outputs matched the saved files.
- The Linux helper ran end-to-end against the supplied EXE, setup and uninstaller. Known SHA-256 values matched, the output ZIP passed `unzip -t`, and the logs included PDB hints and signature result.
- Offline updater payload signature verification returned `SIGNATURE: VALID` using the public key embedded in the known app EXE. SHA-256 of the supplied setup matches the known setup hash.
- The helper supports `7z` or `7zz`, never launches the installer, and auto-creates an output archive.

Pending:

- This environment has no `7z`/`7zz` binary and cannot download one due to DNS/network restrictions. The NSIS setup's embedded file tree has not been extracted here.
- Run the helper on the user's Linux with 7-Zip installed and upload `asistan_linux_kurtarma.zip`.
- The lightweight verifier checks the payload signature but not the separate trusted-comment/global signature.
