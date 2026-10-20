# Payload triage (2026-10-20)

Triage was performed against the recovered payload files and their first bytes.

- `index_html_0049b168.bin` begins with readable HTML/JavaScript-like text, but the complete payload is mixed/garbled and should not be treated as clean source.
- `index_html_0049b7b0.bin` contains readable HTML fragments in its opening bytes, but later content is not consistently readable.
- `index_html_004f7126.bin` begins with text resembling an error/source fragment, followed by binary-looking data.
- Most remaining payloads begin with non-text bytes and did not decode using standard zlib, gzip, bzip2, or LZMA decompression attempts.
- `yazitipi_yazitipi_css_0046e14e.bin` is stored in the repository as a raw binary payload.

## Interpretation

The payloads appear to be packed, transformed, or embedded in a format that cannot be recovered merely by slicing the executable at marker offsets. The offsets and hashes remain useful for reproducible extraction, but this is not yet a working front-end source tree. Further analysis should identify the Tauri asset packaging/encoding used by this exact build before attempting a decoder.

No claim is made that the original app's source code is fully recovered.
