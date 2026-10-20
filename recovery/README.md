# Asistan EXE Recovery

This folder stores findings and repeatable tools for the supplied Asistan 0.1.5 executable.

- `ASISTAN_EXE_KURTARMA_RAPORU.md`: initial Turkish analysis.
- `ASISTAN_EXE_KURTARMA_DURUMU.txt`: native strings, embedded asset names and original executable hash.
- `asset-payload-manifest.json`: earlier raw payload offsets, sizes and SHA-256 hashes.
- `RAW_PAYLOADS.md`: raw payload extraction notes and limitations.
- `READABLE_STRINGS_SUMMARY.md`: printable-string observations.
- `PAYLOAD_TRIAGE.md`: early triage results for raw slices; superseded for frontend recovery by the streaming Brotli results below.
- `RECOVERED_RUNTIME_PARTS.md`: runtime-related string fragments.
- `WEBVIEW_CACHE_TRIAGE.md`: profile cache inspection notes.
- `RECOVERED_SOURCE_FILES.md`: current recovered frontend inventory and validation status.
- `FRONTEND_ASSET_RECOVERY_V4.md`: details of the complete frontend asset recovery pass.

## Latest verified findings

The executable contains Brotli-compressed Tauri frontend assets. Feeding the decoder one byte at a time until it reports end-of-stream successfully recovers the HTML entry page, eight JavaScript files, two CSS files, and seven WOFF2 fonts. All eight JavaScript files passed Node.js syntax validation. Recovered output hashes and extraction offsets are recorded in the v4 recovery bundle manifest.

The original EXE SHA-256 is `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`.

Important: the recovered frontend is not the complete original Tauri/Rust project. Rust backend sources and original build configuration have not been fully reconstructed. Browser history, cookies, and unrelated WebView2 profile files are intentionally excluded from this public repository.
