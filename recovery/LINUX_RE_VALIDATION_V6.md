# Linux reverse-engineering workflow v6

The v6 recovery bundle adds linux/recover_linux.sh and linux/README_TR.md for offline/static analysis on a low-spec Linux system. It runs the existing frontend and PE extractors, records SHA-256 and file-type fingerprints, and, if 7z is installed, lists/tests/extracts the NSIS setup and optional uninstaller into isolated output directories. It also records ASCII and UTF-16LE printable strings.

Validation performed in the current environment:
- Python tools compile successfully.
- All 18 frontend resources extracted from the supplied EXE and match the v5 bundle byte-for-byte.
- All 8 JavaScript files pass Node.js --check.
- All 9 PE resource outputs match the v5 bundle byte-for-byte.
- The shell script passes bash -n and degrades cleanly when 7z is absent.

Limitation: this environment has no 7z/7zz binary, and DNS resolution prevented downloading the official Linux binary. Therefore the NSIS setup payload has not yet been extracted here. Run the helper on the user's Linux with 7zip installed and return the resulting archive to continue the analysis.

The official NSIS wiki explains that extraction of files is possible with tools such as 7-Zip, but that fully decompiling the original installer script is not guaranteed. A deeper follow-up option is the Rust nsis-rs parser; it supports NSIS 3.x structures and embedded-file extraction but requires Rust 1.88+.
