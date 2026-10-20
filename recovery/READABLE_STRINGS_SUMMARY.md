# Recovered readable strings from Asistan 0.1.5

This file records readable text recovered from the Windows executable. It is a string-level recovery, not reconstructed source code.

## Confirmed application/implementation clues

- The executable appears to be a Tauri 2 / Rust desktop application.
- Embedded web asset names include `/index.html`, `/kaynak.js`, `/uygulama.js`, `/stil.css`, `/sozlesme.js`, `/kopru.js`, `/zeka.js`, `/canli.js`, `/komut.js`, and `/kure.js`.
- Windows speech APIs are referenced, including PowerShell `System.Speech` and selection of a Turkish (`tr-TR`) voice.
- Readable strings include Turkish confirmation and cancellation messages, device state/status text, and references to opening local application paths.
- The executable contains command strings associated with system settings and process management. These strings alone do not prove that every command is invoked in normal use.

## Recovery limitations

The embedded payloads currently extracted by the recovery script are raw byte ranges. Several look compressed or otherwise encoded and are not directly valid HTML, JavaScript, or CSS. Do not rename them to source extensions and assume they are recovered source. Verify format and hashes before attempting decoding.

## Source executable fingerprint

- File: `asistan.exe`
- SHA-256: `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`

## Reproduce

Run `python tools/recover_asistan_assets.py /path/to/asistan.exe --output recovery/raw-payloads` if using the exact CLI supported by the current script; consult the script's help output if the options differ.
