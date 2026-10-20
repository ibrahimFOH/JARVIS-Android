# Linux üzerinde statik kurtarma

Bu yardımcı akış eski/düşük donanımlı bilgisayarlar için masaüstü arayüzü gerektirmeden çalışır. EXE ve kurulum paketini çalıştırmaz; yalnızca dosya içeriğini inceler.

## Araç kurulumu

Debian/Ubuntu için önce şu komutları dene:

    sudo apt update
    sudo apt install python3 python3-brotli file binutils p7zip-full

Debian 13 gibi sürümlerde güncel paket adı 7zip olabilir:

    sudo apt install 7zip

Kurulumdan sonra 7z komutunun görünmesi gerekir: `7z --help`. Node.js isteğe bağlıdır; yalnızca JavaScript sözdizimini doğrulamak için kullanılır. Ghidra kurma ile başlama; 4 GB RAM'li bilgisayarda bu ilk adım için gereksiz masraf.

## Dosyaları hazırla

Windows'tan Linux'a şu dosyaları kopyala:

- masaüstü uygulaması: asistan.exe
- kurulum paketi: Asistan_0.1.5_x64-setup.exe
- varsa kaldırıcı: uninstall.exe

Dosya adları değişik olabilir; komutta gerçek yolları kullan.

## Tek komutla kurtarma

ZIP'i aç, paket klasörüne gir ve şunu çalıştır:

    chmod +x linux/recover_linux.sh
    ./linux/recover_linux.sh /path/asistan.exe "/path/Asistan_0.1.5_x64-setup.exe" /path/uninstall.exe

Kaldırıcı yoksa son argümanı kaldır. Çıktı, komutu çalıştırdığın klasördeki asistan_linux_kurtarma dizinine yazılır.

Bu dizinde:
- file_fingerprints.txt: hash ve dosya türleri.
- recovered_frontend/: Brotli ile kurtarılan web kaynakları.
- recovered_pe_resources/: Windows ikon/sürüm/manifest dosyaları.
- setup_nsis/: 7z listeleme, test, çıkarım ve strings çıktıları.
- uninstaller_nsis/: isteğe bağlı kaldırıcı çıktıları.

Sonuçları gönderme komutu:

    zip -r asistan_linux_kurtarma.zip asistan_linux_kurtarma

Arşivi bu sohbete yükle; özellikle setup_nsis/7z_listing.txt, extracted_file_list.tsv, 7z_test.log ve files/ dizini önemli.

## NSIS sınırlaması

NSIS'in resmi belgelerine göre yükleyici kaynak betiğinin birebir tam decompile edilmesi garanti değildir; 7-Zip birçok NSIS paketinden gömülü dosyaları çıkarabilir, ancak eski [NSIS].nsi çıktı özelliği güncel resmi sürümlerde bulunmayabilir. Bu nedenle önce paket dosyalarını almaya çalışıyoruz. Daha derin bytecode analizi gerekirse NSIS Reversing Suite veya nsis-rs gibi araçlara geçeriz.

nsis-rs, kurulum içindeki dosyaları, script bytecode kayıtlarını ve komut ipuçlarını analiz edebilir; ancak Rust 1.88+ gerektirir ve düşük donanımda derleme zaman alabilir. Önce 7z sonucu yeterli mi görelim.

## Doğrulanmış sınırlar

Özgün masaüstü EXE'nin 18 ön yüz kaynağı ve 9 Windows PE çıktısı yerel araçlarla yeniden çıkarıldı, paket içindeki dosyalarla bayt bazında karşılaştırıldı. Sekiz JavaScript dosyası Node.js sözdizimi kontrolünden geçti. Bu tam Rust/Tauri kaynak deposu değildir; Cargo.toml, tauri.conf.json ve eksiksiz Rust backend henüz kurtarılmadı.

Kişisel WebView2 geçmişi/çerezleri veya genel tarayıcı profili bu iş akışına dahil edilmez.
