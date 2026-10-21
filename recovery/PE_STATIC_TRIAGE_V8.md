# PE static triage: native imports and executable layout (V8)

Date: 2026-10-21

## Sample identity

- File: asistan.exe
- SHA-256: 03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8
- Format: PE32+ / x86-64
- Subsystem: Windows GUI
- Entry point: 0x0000000140425110
- Image base: 0x0000000140000000
- Native imports: 28 DLL/import descriptors reported by GNU objdump -x
- Debug directory includes CodeView RSDS metadata; see PDB_AND_UPDATER_RESEARCH_V7.md.

## PE sections

| Section | Virtual size | RVA | Raw file offset |
|---|---:|---:|---:|
| .text | 0x43f646 | 0x1000 | 0x400 |
| .rdata | 0x12cbd4 | 0x441000 | 0x43fc00 |
| .data | 0x0a00 | 0x56e000 | 0x56c800 |
| .pdata | 0x170a0 | 0x572000 | 0x56d200 |
| .tls | 0x1b9 | 0x58a000 | 0x584400 |
| .rsrc | 0xebb8 | 0x58c000 | 0x584800 |
| .reloc | 0x589c | 0x59b000 | 0x593400 |

Values are copied from objdump -x output for the sample hash above. They should not be reused for a different build.

## Imported Windows libraries

- Core/runtime: kernel32.dll, ntdll.dll, bcryptprimitives.dll, bcrypt.dll
- Registry/security/crypto: advapi32.dll, crypt32.dll
- Windowing/UI: user32.dll, gdi32.dll, comctl32.dll, dwmapi.dll, imm32.dll, shlwapi.dll
- COM/Windows integration: combase.dll, ole32.dll, oleaut32.dll, shell32.dll
- Networking/performance: ws2_32.dll, pdh.dll
- Windows Runtime: api-ms-win-core-winrt-l1-1-0.dll, api-ms-win-core-winrt-error-l1-1-0.dll
- Microsoft C runtime API sets: convert, string, math, runtime, heap, stdio and locale.

Imports alone do not prove which application feature calls a particular API. They provide a navigation map for deeper disassembly, not a substitute for recovering Rust source.

## Interpretation

1. The executable is a native Windows x64 GUI PE, not a standalone Python script.
2. The .pdata section and RSDS metadata offer leads for function-boundary/debug analysis, but a matching PDB has not been found.
3. The import table is small relative to the executable's code section, consistent with substantial statically linked code. This is not sufficient to identify every Rust crate or reproduce the original project.
4. Native command names inferred from the JavaScript bridge remain the most useful map for targeted reverse engineering. See TAURI_COMMAND_SURFACE.md.

## Reproduction

~~~bash
sha256sum asistan.exe
file asistan.exe
objdump -x asistan.exe > asistan_objdump.txt
grep -E 'file format|architecture:|start address|ImageBase|Subsystem|DLL Name:' asistan_objdump.txt
~~~

No EXE execution is required. The above triage was performed statically; it does not recover the missing Rust/Tauri source tree.
