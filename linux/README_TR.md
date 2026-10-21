# Linux üzerinde statik kurtarma

Bu yardımcı akış eski/düşük donanımlı bilgisayarlarda komut satırından çalışır. EXE'yi veya NSIS kurulum dosyasını **çalıştırmaz**; yalnızca dosya içeriğini analiz eder.

## 1. Araçları yükle

Önce Linux dağıtımını kontrol edebilirsin:

```bash
cat /etc/os-release
uname -m
free -h
command -v 7z || command -v 7zz || true
```

Debian 13 için genellikle:

```bash
sudo apt update
sudo apt install python3 python3-brotli python3-cryptography file binutils zip 7zip
```

Eski Ubuntu/Debian sürümlerinde `7zip` yerine `p7zip-full` gerekebilir:

```bash
sudo apt update
sudo apt install python3 python3-brotli python3-cryptography file binutils zip p7zip-full
```

Node.js yalnızca JavaScript sözdizimi kontrolü için isteğe bağlıdır. Ghidra ile başlama; bu aşamada gerekli değil ve eski cihazı gereksiz yere yorabilir.

## 2. Dosyaları aktar

Linux'a şunları kopyala:
- `asistan.exe`
- `Asistan_0.1.5_x64-setup.exe` (elindeki dosyanın adı farklıysa gerçek adını kullan)
- varsa `uninstall.exe`

## 3. Kurtarma betiğini çalıştır

Kurtarma ZIP'ini aç ve paket klasörüne gir:

```bash
chmod +x linux/recover_linux.sh
./linux/recover_linux.sh /path/asistan.exe "/path/Asistan_0.1.5_x64-setup.exe" /path/uninstall.exe
```

Kaldırıcı yoksa son argümanı çıkar. Betik:
- Dosya türlerini ve SHA-256 değerlerini kaydeder; bilinen EXE/kurulum/kaldırıcı hash'leriyle eşleşmeyi bildirir.
- 18 web varlığını ve Windows PE kaynaklarını yeniden çıkarır.
- `7z` veya `7zz` komutu varsa kurulum/kaldırıcı dosyasını statik olarak listeler, test eder ve çıkarmayı dener.
- ASCII ve UTF-16LE yazdırılabilir metinleri kaydeder.
- CodeView/PDB yolunu ve GUID/age ipuçlarını raporlar.
- Python `cryptography` paketi varsa setup'ın Tauri updater payload imzasını çevrimdışı doğrular (`setup_signature_verification.txt`).
- Sonuçları otomatik olarak `asistan_linux_kurtarma.zip` arşivlemeyi dener.

Arşiv oluşmazsa:

```bash
zip -r asistan_linux_kurtarma.zip asistan_linux_kurtarma
```

Sonuç ZIP'ini bu sohbete yükle. En faydalı dosyalar `setup_nsis/7z_listing.txt`, `setup_nsis/7z_test.log`, `setup_nsis/7z_extract.log`, `setup_nsis/files/`, `file_fingerprints.txt`, `pe_debug_info.txt` ve `setup_signature_verification.txt`.

## NSIS hakkında

[Resmî NSIS wiki](https://nsis.sourceforge.io/Can_I_decompile_an_existing_installer), orijinal kurulum betiğinin tam olarak geri çıkarılmasının garanti olmadığını açıkça belirtiyor. [7-Zip](https://www.7-zip.org/download.html) çoğu NSIS paketinden dosyaları çıkarmayı deneyebilir, ancak tam `.nsi` kaynak betiğini üretmeyebilir.

7-Zip dosya çıkaramazsa önce günlükleri inceleyeceğiz. Sonraki seçenek [nsis-rs](https://github.com/ATRAPSLLC/nsis-rs) gibi bir parserdır; Rust 1.88+ ve ek derleme gerektirdiği için düşük donanımda ilk adım değil.

## Sınırlar

- Kaynak EXE SHA-256: `03c71a4204fd37f240dabc008742d7ef23938cb1f8bebce24ee79c8cee0b6be8`
- Ön yüzün 18 varlığı ve PE'den çıkan 9 kaynak doğrulandı.
- Özgün Rust/Tauri backend, `Cargo.toml`, `tauri.conf.json` ve eksiksiz derleme zinciri kurtarılmadı.
- Kişisel tarayıcı geçmişi/çerezleri kurtarma akışına dahil edilmez.


## Ek araştırma: NSIS script çıkarma

Standart 7-Zip ile payload dosyalarını çıkarmak ve derlenmiş NSIS kurulum betiğini decompile etmek farklı işlemlerdir. Script çıkarma için özel derleme seçeneği araştırıldı. Ayrıntılı, doğrulanabilir komutlar ve GitHub release hash'i:
[NSIS_SCRIPT_DECOMPILATION_V8.md](../recovery/NSIS_SCRIPT_DECOMPILATION_V8.md)

Özel 7-Zip NSIS derlemesi: https://github.com/myfreeer/7z-build-nsis/releases/tag/26.04

Not: Bu ortamda 7z/7zz kurulu olmadığı için kurulum payload'ı ve `[NSIS].nsi` fiilen çıkarılmış değil. Bu adım, Linux makinede yapılacak sonraki doğrulama olarak duruyor.
