# Asistan 0.1.5 EXE kurtarma raporu

Bu klasör, kullanıcının sağladığı Asistan 0.1.5 Windows EXE'sinden elde edilen doğrulanmış analiz bulgularını içerir. Bu rapor **tam kaynak kodun kurtarıldığı anlamına gelmez**.

## Doğrulananlar
- `asistan.exe`: Windows PE32+ x86-64; SHA-256 `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`
- `Asistan_0.1.5_x64-setup(1).exe`: NSIS 3.13 yükleyici; SHA-256 `485cbd596960754590f80f5c7adb05b96e11961d82a8b7a956fabb426f4f3b09`
- `uninstall.exe`: NSIS kaldırıcı; SHA-256 `ea53e123817670550bccb072d9f61dde1ae8cc723627974ef5668b0b83f9f1c1`
- Uygulama Tauri 2 / Rust tabanlıdır.
- Gömülü web varlık yolları: `/index.html`, `/kaynak.js`, `/uygulama.js`, `/stil.css`, `/sozlesme.js`, `/kopru.js`, `/zeka.js`, `/canli.js`, `/komut.js`, `/kure.js`, `/yazitipi/yazitipi.css`.
- EXE'de Tauri komutları, WebView2 Runtime mesajları ve `src/main.rs` derleme yolu gibi izler bulundu.

## Kurtarma durumu
- Bazı okunabilir metinler ve kaynak yolları çıkartıldı.
- Gömülü varlık payload'ları ham ikili olarak ayrıştırıldı ve SHA-256 değerleri kaydedildi.
- Ham `.bin` payload'ları çözülmüş JavaScript/CSS/HTML değildir.
- Orijinal Rust kaynak projesi ve çalıştırılabilir tam web kaynakları henüz kurtarılmadı.
- Standart Brotli, zlib/gzip ve LZ4 denemeleri varlıkları çözmedi.
- Kullanıcı arşivindeki WebView2 Code Cache kayıtları da potansiyel kurtarma kaynağıdır; bunların kaynak kod olduğu doğrulanmamıştır.

## Önemli
Bu depoya kurtarma raporları ve doğrulanmış bulgular eklenmektedir. Kullanıcı tarayıcı geçmişi, genel WebView2 profili ve kişisel gezinti kayıtları gibi uygulama kaynak kodu olmayan özel veriler herkese açık depoya aktarılmaz.
