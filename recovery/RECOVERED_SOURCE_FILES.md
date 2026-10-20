# Recovered source files (2026-10-21)

## Latest recovery result

Streaming Brotli decompression now recovers the frontend's actual resource contents from the supplied executable. The earlier v3 state is superseded.

Recovered resources:
- `index.html` (6,846 bytes)
- Eight JavaScript files: `kopru.js` (4,842), `kure.js` (11,679), `kaynak.js` (8,713), `zeka.js` (16,677), `canli.js` (11,540), `komut.js` (32,182), `sozlesme.js` (19,130), `uygulama.js` (87,894)
- Two CSS files: `stil.css` (26,337) and `yazitipi/yazitipi.css` (2,641)
- Seven WOFF2 fonts under `yazitipi/`

All eight JavaScript files passed `node --check`. All local JS/CSS paths referenced by the HTML exist. The seven font outputs begin with the valid WOFF2 magic `wOF2` and match the names referenced by the typography CSS. The full v4 bundle includes the extraction script, hashes and offsets in `analysis/RECOVERY_MANIFEST.json`, and the prior 15 raw payload files for traceability.

The streaming method locates a resource path marker in the EXE, feeds following bytes to Brotli until the stream ends, and validates the result's expected signature. This avoids incorrectly treating following binary data as part of the same compressed stream.

This still does not recover the full original Rust/Tauri project. `Cargo.toml`, `tauri.conf.json`, backend Rust commands and the original complete build pipeline are not present in the recovered source tree. Successful JavaScript syntax checks do not prove that the application runs without the native Tauri backend.
