# Asistan EXE Recovery

This folder stores verified findings for Asistan 0.1.5.

- `ASISTAN_EXE_KURTARMA_RAPORU.md`: detailed Turkish report and limitations.
- `ASISTAN_EXE_KURTARMA_DURUMU.txt`: asset names, native command traces, hashes, and status.
- `asset-payload-manifest.json`: offsets, sizes, and SHA-256 hashes of recovered raw payloads.
- `RAW_PAYLOADS.md`: instructions and limitations for raw payload recovery.
- `READABLE_STRINGS_SUMMARY.md`: readable string-level observations.
- `raw-payloads/`: raw binary payload files that have been committed so far.

Important: raw payload extraction is not the same as recovering valid HTML/JavaScript/CSS. The original complete source project has not been recovered. Do not run the EXE or any extracted commands unless you trust the file and have reviewed the behavior.

The original executable fingerprint is SHA-256:
`03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`
