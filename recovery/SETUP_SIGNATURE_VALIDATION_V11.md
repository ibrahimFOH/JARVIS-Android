# Asistan 0.1.5 setup imza doğrulaması (V11)

Tarih: 2026-10-21

## Sonuç

Yerelde bulunan `Asistan_0.1.5_x64-setup.exe`, depodaki mevcut `tools/verify_asistan_setup_signature.py`, imza dosyası ve public key ile doğrulandı.

- Sonuç: `SIGNATURE: VALID`
- Yöntem: Ed25519 imzası, BLAKE2b-512 digest üzerinde
- Anahtar kimliği: `13ADF2DB829F075A`
- Gerçek dosya SHA-256: `485cbd596960754590f80f5c7adb05b96e11961d82a8b7a956fabb426f4f3b09`
- Bilinen SHA-256: `MATCH`
- Doğrulama çıktısı V11 yerel kurtarma paketinde bulunuyor.

## Ne kanıtlıyor?

İmzalı payload, depoda kayıtlı public key ile doğrulanıyor ve test edilen dosyanın hash'i beklenen hash ile aynı. Bu, imzalanan kurulum dosyasının bütünlüğüyle ilgili bir doğrulamadır.

## Ne kanıtlamıyor?

- Yazılımın güvenli, hatasız veya amaca uygun olduğunu tek başına kanıtlamaz.
- Kullanılan doğrulayıcı minisign içindeki ayrı `trusted comment`/global imza kaydını doğrulamıyor.
- Trusted comment içinde `Asistam_0.1.5_x64-setup.exe` yazıyor; bu, gerçek dosya adından farklı bir yazım hatası gibi duruyor. Payload imzası ve SHA-256 geçerliliği bundan bağımsız olarak doğrulandı.

## Tekrarlama

Python `cryptography` paketi kuruluysa:

```bash
python3 tools/verify_asistan_setup_signature.py "/tam/yol/Asistan_0.1.5_x64-setup.exe"
```

Kurulum dosyasını çalıştırmak gerekmez. Script yalnızca dosyanın baytlarını okur.
