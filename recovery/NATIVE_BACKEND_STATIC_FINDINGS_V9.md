# Asistan 0.1.5: yerel çekirdek statik bulguları (V9)

Tarih: 2026-10-21. İnceleme, sağlanan dosyaların çalıştırılmadan analizine dayanır.

## Dosya kimlikleri

- asistan.exe: 5,869,056 bayt
- SHA-256: 03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8
- Asistan_0.1.5_x64-setup.exe: 2,304,183 bayt
- SHA-256: 485cbd596960754590f80f5c7adb05b96e11961d82a8b7a956fabb426f4f3b09
- uninstall.exe: 79,508 bayt
- SHA-256: ea53e123817670550bccb072d9f61dde1ae8cc723627974ef5668b0b83f9f1c1

## Doğrulama

- 18 ön yüz varlığı EXE içinden yeniden çıkarıldı ve V5 arşivindeki karşılıklarıyla byte-byte karşılaştırıldı: 18/18 eşleşti.
- 8/8 JavaScript dosyası Node.js node --check testinden geçti.
- PE kaynaklarından altı PNG simge, ICO, sürüm bilgisi ve manifest çıkarıldı.
- EXE'nin CodeView/PDB kaydı src/main.rs yoluna işaret ediyor; eşleşen PDB veya Rust kaynak dosyası bulunmadı.

## Tauri köprü komutları

Aşağıdaki 34 ad kopru.js içinde gerçek Tauri invoke çağrıları olarak yer alıyor. Bunlar arayüz sözleşmesini kanıtlar, Rust fonksiyon gövdelerinin geri alındığını değil.

dosya_oku, dosya_yaz, sir_oku, sir_yaz, http_istek, baglanti_ac, sistem, konus, sus, sesler, yerel_zeka, oto_baslat_oku, oto_baslat_yaz, brifing_zamani, acilis_sebebi, tam_ekran, tam_ekran_mi, gunluk, klasorler, uygulamalar, uygulama_ac, dosya_ara, yol_ac, cop_ac, silme_hazirla, silme_onayla, silme_vazgec, guc, mikrofon_izni, hatirlatici_kur, hatirlaticilar, hatirlatici_sil, guncelleme_denetle, guncelleme_kur.

Arayüz açıklamaları silme akışını hazırla/onayla/vazgeç adımlarıyla iki aşamalı yapıyor. Backend doğrulama kontrollerinin tamamı kaynak kodu olmadan denetlenemiyor.

## Native teknoloji izleri

EXE içinde derleme dizgileriyle doğrulanan sürümler: Tauri 2.12.1, reqwest 0.13.5, keyring 3.6.3, sysinfo 0.33.1, tauri-plugin-updater 2.13.1, tauri-plugin-autostart 2.7.0, tauri-plugin-notification 2.5.1, tauri-plugin-opener 2.7.0 ve tauri-plugin-global-shortcut 2.4.0.

Uygulama kimliği: com.gurizon.kisiselasistan. Diğer bulgular arasında Windows Credential Manager dizgisi WinCredential, APPDATA, ayar.json, durum.json, hatirlatici.json, başlangıç kayıt anahtarları, explorer.exe ve PowerShell Clear-RecycleBin komutu var. Bunlar yerel özelliklere ilişkin işaretlerdir; tek başına çalışma zamanı testinin yerine geçmez.

## İşlev ve uç noktalar

- AI: Gemini, Anthropic Claude, OpenAI/OpenAI-uyumlu servisler; OpenAI canlı ses oturumu; Kie üzerinden görsel üretimi; cihaz içi AI durum denetimi.
- Veri/brifing: Google News RSS, Open-Meteo, Truncgil finans JSON'u, Frankfurter döviz kuru, Gold API, CoinGecko.
- Windows: durum bilgisi, dosya/klasör arama ve açma, uygulama başlatma, çöp kutusu işlemi, hatırlatıcı, metinden sese, otomatik başlatma, uyutma/kilitleme/kapatma, güncelleme.
- Sağlayıcı uçları: api.openai.com, generativelanguage.googleapis.com, api.anthropic.com, api.kie.ai.
- Ürün uçları: gurizon.com/asistan/guncelleme.json ve gurizon.com/asistan/sozlesme.json/html.

Ön yüzün ham API anahtarları ayar ekranından alıp sir_oku/sir_yaz köprüsüyle sakladığı görülüyor. Örnek ayar.json içinde sağlayıcı/model tercihleri bulunuyor, ham anahtar alanları bulunmuyor. keyring/WinCredential derleme dizgileri de işletim sistemi anahtar deposu kullanımıyla uyumlu.

## Kurulum paketi ve sınırlar

NSIS kurulumunun payload'ı veya [NSIS].nsi bu çalışma ortamında çıkarılmadı: 7z/7zz kurulu değil ve dış ağ/DNS bağlantısı başarısız. Bunların çıkarılmış olduğunu iddia etmiyoruz. Linux tarafında 7-Zip'in NSIS script decompilation seçeneği açık bir sürümünü derlemek için kaynak proje mevcut: https://github.com/Nalinium/7zz-build-nsis-linux. NSIS'in kendi wiki sayfası tam özgün betiğin geri getirilmesini garanti etmediğini açıkça belirtir: https://nsis.sourceforge.io/Can_I_decompile_an_existing_installer.

Asistan.zip, ayarlar dışında WebView/Edge profili, geçmiş, önbellek ve metrikler de içeriyor. Gizlilik nedeniyle bu arşiv repoya veya temiz kurtarma paketine eklenmedi.

Rust/Tauri kaynak kodu, Cargo.toml, tauri.conf.json ve eksiksiz özgün derleme zinciri hâlâ kurtarılmış değil. http_istek, uygulama_ac, dosya_ara, yol_ac, guc ve silme komutlarının izin/argüman doğrulamasını kaynak gövdeleri olmadan bütünüyle denetlemek mümkün değil.
