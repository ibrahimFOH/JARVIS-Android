# WebView cache triage

The supplied `Asistan.zip` includes a WebView2 profile. Its V8 JavaScript Code Cache contains eight small cache entries whose metadata identifies these application script URLs:

- `http://tauri.localhost/kaynak.js`
- `http://tauri.localhost/uygulama.js`
- `http://tauri.localhost/sozlesme.js`
- `http://tauri.localhost/kopru.js`
- `http://tauri.localhost/zeka.js`
- `http://tauri.localhost/canli.js`
- `http://tauri.localhost/komut.js`
- `http://tauri.localhost/kure.js`

The cache entries are only 239–343 bytes each and expose URL/key metadata, not the original JavaScript source. They do confirm that these scripts were requested by the app's WebView. The cached entries were not committed as binaries because they do not contain recoverable source and add little value beyond this manifest.

The Chromium disk cache files were checked for readable app-source markers and URLs; no usable HTML or JavaScript body was identified in the inspected data blocks. The profile also contains browsing history and other user-specific state. Those files are intentionally excluded from the public repository.

This is an additional recovery lead, not a source-code recovery. The original front-end files remain encoded or otherwise not yet decoded in the executable's embedded asset payloads.
