# Asistan 0.1.5 - V12 imza ve kurtarma ek raporu

Tarih: 21.10.2026

## Kurulum dosyası imza kontrolü

Kurulum dosyası `Asistan_0.1.5_x64-setup.exe` için iki ayrı kontrol yapıldı:

- **Payload imzası: VALID.** Ed25519 imzası BLAKE2b-512 dosya özeti üzerinde doğrulanıyor. Public key ID `13ADF2DB829F075A`; dosya SHA-256 `485cbd596960754590f80f5c7adb05b96e11961d82a8b7a956fabb426f4f3b09`, kayıtlı hash ile eşleşiyor.
- **Trusted-comment/global imza: INVALID (standart Minisign doğrulamasına göre).** `global signature = Ed25519(signature_bytes || trusted_comment)` kuralıyla, imza dosyasındaki ham baytlar ve tam yorum metni kullanılarak denendi; ayrı global imza doğrulanmadı.

Bu, payload imzasının geçersiz olduğu anlamına gelmez. Tauri kurulum dosyasının payload imzası geçerli. Ancak `.sig` dosyasındaki `trusted comment` satırının bütünlüğü ayrı kontrol edildiğinde doğrulanmıyor. Yorum satırındaki dosya adı da `Asistam_0.1.5_x64-setup.exe` biçiminde yazılmış; gerçek dosya adı `Asistan_0.1.5_x64-setup.exe`. Bu uyumsuzluk, global imza nedenini tek başına açıklamaz.

İki kontrolü ayıran yeni betik: `tools/verify_asistan_minisign_full.py`. Bu betik dosyayı çalıştırmaz, yalnızca kriptografik kontrol yapar. Standart Minisign'in trusted-comment/global signature hesabı için kaynak: https://github.com/jedisct1/minisign/blob/master/src/minisign.c. Tauri updater dokümanı da payload imzasının güncelleme paketini doğrulamak için kullanıldığını açıklar: https://tauri.app/plugin/updater/.

## Kurtarma doğrulaması

- `asistan.exe` SHA-256: `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`.
- Ön yüz: 18 kaynak/varlık, V5 kurtarma arşiviyle 18/18 birebir byte karşılaştırması.
- JavaScript: 8 dosyanın 8'i `node --check` testinden geçti.
- PE kaynakları: 6 simge boyutu, `.ico`, manifest ve sürüm bilgisi çıkartıldı.
- Rust izleri: 98 farklı crate/sürüm yol çifti. Bu `Cargo.toml` değildir ve doğrudan bağımlılıkların listesi sayılmaz.
- PDB işareti: `asistan.pdb`, age 1, matching PDB/source file bulunamadı.
- Native Tauri çağrı yüzeyi: 34 bridge komutu, `kopru.js` içinden çıkarıldı.

## Android tarafı

Bağımsız `JARVIS_ANDROID` projesinin CI debug APK'sı başarıyla oluşturuldu ve ZIP bütünlüğü doğrulandı. En son doğrulanmış artifact, run #129:
https://github.com/ibrahimFOH/JARVIS-Android/actions/runs/39582942609

APK SHA-256: `85c255ed5ae7f4c0b6bc6a8ef18294b200f3571dea71d7730215f4eda5d004cc`, boyut 97,511,083 bayt. Paket adı `com.stagepulse.jarvis`, sürüm `2.2.0-piper`, minimum Android API 26; `arm64-v8a` ve `armeabi-v7a` içeriyor. Cihazda veya emülatörde test edilmedi. Bu, Windows `Asistan.exe` dosyasının otomatik dönüştürülmüş biçimi değil; ayrı Android uygulamasıdır.

## Hâlâ tamamlanmayanlar

1. NSIS kurulum payload'ı ve `[NSIS].nsi` burada çıkarılamadı. Yerel ortamda `7z/7zz` yok; shell dış ağa/DNS'e çıkamıyor.
2. Özgün Rust/Tauri komut gövdeleri, `Cargo.toml`, `tauri.conf.json` ve özgün build sistemi kurtarılmadı.
3. Android APK gerçek cihazda denenmedi.
4. Payload imzası valid olsa da ayrı `trusted comment` imzası doğrulanmadığı bulgusu çözülmüş değil.

V12 paketi EXE ve kurulum binary'lerini içermez; doğrulanmış arayüz dosyalarını, PE kaynaklarını, imza verisini, doğrulayıcıları ve raporları taşır. Kişisel WebView/Edge profili kurtarma paketine dahil edilmemiştir.
