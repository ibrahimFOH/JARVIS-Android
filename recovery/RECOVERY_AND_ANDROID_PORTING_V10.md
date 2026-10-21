# Asistan 0.1.5 kurtarma ve Android'e geçiş raporu (V10)

Tarih: 2026-10-21. EXE statik analiz edildi, çalıştırılmadı.

## Doğrulanan kaynak dosyaları

- Asistan EXE SHA-256: 03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8
- Bilinen 18 web varlığı tekrar doğrulandı; 18/18 dosya V5 paketindeki karşılığıyla bayt bayt aynı.
- 8/8 JavaScript dosyası Node.js sözdizimi denetiminden geçti.
- Kaynak varlık işaretçileri sayıldığında 22 işaretçi görülüyor: /index.html beş konumda, listelenen diğer 17 varlık yolu birer konumda. Beş HTML işaretçisinin sadece birindeki Brotli akışı HTML imza doğrulamasından geçiyor.
- Kaynak haritası göstergeleri sourceMappingURL, webpack://, vite:// ve index.js.map aramaları bu EXE'de eşleşme vermedi. Bu, her ihtimalde kaynak haritası yokluğunun mutlak kanıtı değil, statik metin taraması sonucudur.

## Rust derleme izleri

İkili içindeki .cargo/registry/src... kaynak yolu dizgilerinden 98 farklı crate/sürüm çifti ayrıştırıldı. Bunlar Cargo.toml değildir ve hepsinin doğrudan bağımlılık olduğu sonucuna varılamaz; geçişli derlemeleri de kapsayabilir. Tam liste, V10 yerel JSON manifestinde bulunur.

CodeView kaydı RSDS işaretli, PDB adı asistan.pdb, age 1. GUID Windows biçiminde ee39d7da-5768-ffa2-4c4c-44205044422e, ham baytları dad739ee6857a2ff4c4c44205044422e. Kayıttaki son baytlar ASCII LLD PDB. dizisini içeriyor. Eşleşen PDB veya Rust kaynak dosyası bulunmadı; kaynak gövdelerinin geri alındığı iddia edilmiyor.

## Android derleme doğrulaması

GitHub Actions JARVIS Android Build, run 39581658900 / #126, commit 94e1f72941b17c299bf6c2d1c2b3c8d760b84cb1 üzerinde başarıyla tamamlandı. Artifact ZIP SHA-256: 479e8454df92e10bef866c738c5171b2cfba134358e1acf3c09d92b695aa6058.

- APK: JARVIS-Android-PIPER-debug-2026-10-21.apk
- Boyut: 97,511,083 bayt; SHA-256: e1bd184c84eaa148beaab03b23568088601f16a5365356b67669245444b78835
- Gradle uygulama kimliği com.stagepulse.jarvis, sürüm 2.2.0-piper (versionCode 220), minSdk 26, targetSdk 35.
- APK içeriği bütünlük testinden geçti ve arm64-v8a ile armeabi-v7a kitaplıklarını içeriyor.
- Yerel Türkçe Piper TTS modeli assets/piper/tr_TR-dfki-medium.onnx (63,201,294 bayt) ve ilgili native kitaplıklar APK içinde.
- Cihaz/emülatör testi yapılmadı; ortamda adb/emülatör yok. CI build ve ZIP bütünlüğü doğrulandı.

Önemli ayrım: Bu APK, depodaki ayrı yerel Stagepulse Android uygulamasının debug yapısıdır. Windows Asistan 0.1.5 EXE'sinin otomatik dönüştürülmüş sürümü değildir. İki uygulamanın özellik eşitliği doğrulanmadı.

## Android'e taşınabilirlik

| Desktop özelliği | Android yol haritası |
|---|---|
| index.html, stil.css, kure.js | Native UI veya mobil ekrana uyarlanmış WebView. Tauri pencere kontrolleri yeniden yapılmalı. |
| kopru.js ve Tauri invoke komutları | Java/Kotlin servis katmanı; kopru.js doğrudan kullanılamaz çünkü window.__TAURI__ yoksa hata veriyor. |
| Gemini, Claude, OpenAI uyumlu sohbet | Android HTTP istemcisi; anahtarlar Android Keystore veya eşdeğer güvenli depoda saklanmalı. |
| canli.js, WebRTC canlı ses | Android WebRTC, mikrofon izni ve oturum yönetimi ayrıca uygulanmalı. |
| Haber, hava, finans veri kaynakları | HTTP + önbellek + çevrimdışı hata yönetimi. Veriler internet olmadan yenilenemez. |
| Dosya, klasör ve uygulama açma | Android Intent ve Storage Access Framework; Windows yolları birebir taşınamaz. |
| Windows çöp kutusu, registry, uyut/kapat/yeniden başlat | Android'de normal uygulama için eşdeğer genel yetki yok. Doğrudan kopyalanmamalı; Windows host köprüsü veya kapsam dışı. |
| Windows yerel AI (Apple Intelligence) | Android'e doğrudan aktarılamaz. Offline LLM gerekirse ayrı model/runtime gerekir. |
| Hatırlatıcılar | AlarmManager/WorkManager ve Android bildirim izinleri. |
| Tauri updater | Play dağıtımı veya imzalı APK güncelleme akışı. |
| Sözleşme ve veri aktarımı rızası | API, canlı ses ve görsel üretiminde kullanıcıya açık rıza gösterilmeli. |

Mevcut JARVIS_ANDROID projesi Stagepulse HUD, Android SpeechRecognizer, Piper ile yerel Türkçe ses sentezi, uzman ajan kataloğu ve isteğe bağlı Windows host köprüsü içeriyor. Piper ses sentezi, çevrimdışı konuşma tanıma veya çevrimdışı LLM demek değildir.

## Açık kalanlar

1. NSIS kurulum payload'ı ve [NSIS].nsi henüz çıkarılmadı. Bu ortamda 7z/7zz yok ve yerel shell dış ağ/DNS üzerinden indirme yapamıyor. Linux aracı: https://github.com/Nalinium/7zz-build-nsis-linux
2. Özgün Rust/Tauri komut gövdeleri, Cargo.toml ve tauri.conf.json kurtarılmadı.
3. Android APK gerçek cihazda denenmedi.
4. http_istek, uygulama_ac, dosya_ara, yol_ac, guc ve silme komutlarının orijinal güvenlik denetimleri Rust kaynakları olmadan tamamen incelenemez.

NSIS tam script kurtarma sınırları: https://nsis.sourceforge.io/Can_I_decompile_an_existing_installer