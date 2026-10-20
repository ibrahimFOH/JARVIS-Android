# EXE içinden çıkarılan çalışma zamanı parçaları

2026-10-20 tarihinde `asistan.exe` içindeki sıfır sonlandırmalı JavaScript dizgelerinden bazı Tauri çalışma zamanı parçaları ayrı dosyalara çıkarıldı. Bunlar `window.__TAURI__` köprüsü, IPC, asset protokolü ve sürükleme bölgesi gibi Tauri altyapı parçalarıdır; uygulamanın kendi ekran/iş mantığı değildir.

Çıkarılan parçaların başlangıç ofsetleri:

- `tauri_deep_freeze_fragment.js`: `0x47FE8E` (kısa/kısmi parça)
- `tauri_isolation_runtime.js`: `0x4802F2`
- `tauri_ipc_asset_runtime.js`: `0x48194B`
- `tauri_pattern_drag_runtime.js`: `0x4824F0`
- `tauri_drag_region_runtime.js`: `0x482759`
- `tauri_channel_runtime.js`: `0x506309`
- `tauri_ipc_runtime.js`: `0x507E8E`
- `tauri_plugin_runtime.js`: `0x45B6CB`

Önemli: Bu dosyalar, EXE içindeki metin dizgelerinin son NUL baytına kadar kopyalanmasıyla çıkarılmıştır. Kısa parça kesilmiş olabilir; her dosyanın bir bütün olarak derlenebilir olması garanti edilmez. Uygulamaya ait gömülü HTML/JS/CSS ham payload'larının çözümü hâlâ tamamlanmamıştır. Tam kaynak proje kurtarılmış değildir.