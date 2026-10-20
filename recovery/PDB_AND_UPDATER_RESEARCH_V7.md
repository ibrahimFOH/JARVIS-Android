# PDB/debug and updater research (2026-10-21)

## Public updater manifest

The public updater metadata at [guncelleme.json](https://gurizon.com/asistan/guncelleme.json) reports version `0.1.5`, publication time `2026-10-08T07:10:37.998Z`, and the Windows x86-64 setup URL:

`https://gurizon.com/asistan/surum/Asistan_0.1.5_x64-setup.exe`

The supplied setup file SHA-256 is `485cbd596960754590f80f5c7adb05b96e11961d82a8b7a956fabb426f4f3b09`. We have not downloaded the public binary in this environment to byte-compare it with the supplied setup. The Linux helper now records the hash and identifies whether the local setup matches this known file.

## CodeView/PDB information

A CodeView `RSDS` record was found at file offset `0x55d414` in the application EXE. It names `asistan.pdb`, age `1`, and GUID `ee39d7da-5768-ffa2-4c4c-44205044422e`. The last eight GUID bytes decode as ASCII `LLD PDB.`, so this is an unusual debug marker; do not assume it points to a recoverable full-symbol PDB without checking the symbol file's identity. A PDB was not present next to the supplied EXE. The plausible public URLs `https://gurizon.com/asistan/asistan.pdb` and `https://gurizon.com/asistan/surum/asistan.pdb` returned 404.

The CodeView RSDS structure conventionally stores a GUID, age and PDB path. A symbol file is useful only if it matches the executable's identity. References: [PDB format overview](https://github.com/PascalBeyer/PDB-Documentation), [LLVM PDB Info Stream](https://llvm.org/docs/PDB/PdbStream.html), and [LLD Windows support](https://releases.llvm.org/18.1.8/tools/lld/docs/windows_support.html).

## Native reverse-engineering limits

The application contains Rust/Tauri strings and frontend-to-native command names. It does not contain a usable complete Rust source tree, `Cargo.toml`, or the original Tauri build configuration. The PE's regular symbol table is stripped. Without an actual matching PDB or object files, full reconstruction of optimized Rust functions is unlikely; targeted disassembly and mapping native commands remain practical.

## What to do next

Run `linux/recover_linux.sh` on the low-spec Linux machine after installing 7-Zip. The new helper accepts either `7z` or `7zz`, collects file fingerprints, probes CodeView metadata, statically lists/tests/extracts the NSIS setup and optional uninstaller, and automatically packages logs into `asistan_linux_kurtarma.zip`.

If 7-Zip does not expose the embedded files, upload that report first. Only then consider [nsis-rs](https://github.com/ATRAPSLLC/nsis-rs), a deeper NSIS parser that requires Rust 1.88+ and more installation/compile effort.
