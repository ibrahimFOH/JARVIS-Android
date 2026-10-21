# NSIS kurulum betiği ve payload çıkarma araştırması (V8)

Tarih: 2026-10-21

## Sonuç

Bu proje için iki ayrı hedef var ve bunlar karıştırılmamalı:

1. **Payload çıkarma:** Kurulum paketine gömülü dosyaları bulup çıkarmak. Standart 7-Zip bunu çoğu NSIS paketinde yapabilir.
2. **NSIS script decompilation:** Derlenmiş kurulum akışından `[NSIS].nsi` gibi bir temsil çıkarmayı denemek. Standart 7-Zip'in yeni sürümlerinde bu özellik bulunmayabilir; bunun için özel derleme gerekebilir.

NSIS'in kendi belgeleri tam kaynak betiğin garantili olarak geri alınamayacağını belirtiyor:
https://nsis.sourceforge.io/Can_I_decompile_an_existing_installer

## Bulunan özel araç

GitHub projesi `myfreeer/7z-build-nsis`, NSIS script decompilation özelliği eklenmiş 7-Zip derlemeleri sağlıyor:
https://github.com/myfreeer/7z-build-nsis

Araştırma sırasında GitHub Releases API'sinde `26.04` sürümü görüldü. Linux için kaynak yerine derlenmiş araçları içeren `7z2604.7z` arşivi yayımlanmış:
https://github.com/myfreeer/7z-build-nsis/releases/download/26.04/7z2604.7z

GitHub release metaverisindeki SHA-256:
`2543960f1c05bb941a55017452fabef2902e77909d1c69d34cfe267819343862`

Bu değer indirme sonrasında yerel dosya hash'iyle karşılaştırılmalı. Bu rapor, ikili dosyanın burada çalıştırılarak test edildiği anlamına gelmez.

## Linux üzerinde düşük maliyetli deneme

Önce dağıtımın paket yöneticisinden 7-Zip kurulmalı. Debian/Ubuntu türevlerinde paket adı sürüme göre `7zip` veya `p7zip-full` olabilir.

Özel derleme arşivini indirmek için:

```bash
wget 'https://github.com/myfreeer/7z-build-nsis/releases/download/26.04/7z2604.7z' -O /tmp/7z2604.7z
printf '%s  %s\n' '2543960f1c05bb941a55017452fabef2902e77909d1c69d34cfe267819343862' '/tmp/7z2604.7z' | sha256sum -c -
mkdir -p /tmp/7z2604
7z x /tmp/7z2604.7z -o/tmp/7z2604
find /tmp/7z2604 -type f -name 7zz -print
```

Arşiv içindeki `7zz` dosyasını bulduktan sonra aşağıdaki `/TAM/YOL/7zz` kısmı o gerçek yol ile değiştirilmeli:

```bash
mkdir -p "$HOME/asistan-nsis-script"
"/TAM/YOL/7zz" x "$HOME/asistan-dosyalar/Asistan_0.1.5_x64-setup.exe" '[NSIS].nsi' '[LICENSE].txt' -o"$HOME/asistan-nsis-script"
```

Özel script çıkarma denemesi başarısız olsa bile payload çıkarma ayrı denenmeli:

```bash
mkdir -p "$HOME/asistan-nsis-payload"
"/TAM/YOL/7zz" x "$HOME/asistan-dosyalar/Asistan_0.1.5_x64-setup.exe" -o"$HOME/asistan-nsis-payload"
```

Komut çıktısı, çıkış kodu ve oluşturulan dosyaların listesi saklanmalı. Kurulum dosyasını çalıştırmak veya Wine ile açmak gerekmiyor.

## Beklentiler ve sınırlamalar

- `[NSIS].nsi` çıkarsa bu, orijinal geliştirici kaynak betiğinin birebir geri geldiğini kanıtlamaz; decompiler çıktısıdır.
- Payload dosyaları çıkarılsa bile Tauri/Rust backend kaynak kodu otomatik olarak geri gelmez.
- EXE'de PDB yolu izi bulunması, eşleşen PDB'nin mevcut olduğu anlamına gelmez. Önceki araştırmada eşleşen PDB dosyası bulunamadı.
- Kurulumun ek dosyaları statik olarak çıkarılamazsa, günlükler ve NSIS başlık/komut dizisi analizi sonraki aşamadır.
- Bilinmeyen bir kurulumun hiçbir zaman çalıştırılmaması ve çıkarma çıktısının ayrı klasörde tutulması önerilir.

## Kaynaklar

- NSIS: https://nsis.sourceforge.io/Can_I_decompile_an_existing_installer
- Özel 7-Zip derlemesi: https://github.com/myfreeer/7z-build-nsis
- 26.04 release: https://github.com/myfreeer/7z-build-nsis/releases/tag/26.04
