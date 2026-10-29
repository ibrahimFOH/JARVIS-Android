# JARVIS Android

Bağımsız Android JARVIS uygulaması. Bu proje, Windows Asistan 0.1.5 EXE'sinin dönüştürülmüş paketi değildir; Android için ayrı yazılmış bir uygulamadır.

## Güncel doğrulama

- Package/application ID: `com.stagepulse.jarvis`
- Sürüm: `2.2.4` (versionCode 224)
- minSdk 26 (Android 8.0), targetSdk 35
- ABI: `arm64-v8a`, `armeabi-v7a`
- Güncel CI/derleme geçmişi: [GitHub Actions](https://github.com/ibrahimFOH/JARVIS-Android/actions)
- CI, APK'yı derler ve Python komut yönlendirme/güncelleme denetimlerini çalıştırır. Gerçek telefonda/emülatörde elle kurulum testi ayrıca gerekir.

## Otomatik güncelleme

- Android uygulaması açılışta sürüm kontrolü yapar; gereksiz istekleri azaltmak için otomatik denetim 12 saatte bir yapılır. Arayüzdeki **UPDATE** düğmesi denetimi elle başlatır.
- Yeni Android APK'sı yalnızca bu depodaki en son GitHub Release içinden alınır. İndirmeden önce HTTPS kaynağı, indirildikten sonra SHA-256 özeti doğrulanır. Android güvenlik gereği kurulum onayı ister; sessiz kurulum yapılmaz.
- Windows masaüstü JARVIS arayüzü de 12 saatte bir güncelleme kontrol eder; **UPDATE** düğmesi elle kontrol sağlar. Yeni ZIP'in SHA-256 değeri doğrulanır. Güncelleme mevcut klasörde uygulanır; `config/config.json` ve `config/bridge_token.txt` korunur. Eski EXE ve sürüm bilgisi, geri dönüş için yan `StagepulseJARVIS.rollback-*` klasöründe saklanır. Yönetici izni gereken kurulum konumlarında Windows UAC onayı gerekebilir.
- Windows otomatik değiştirme yalnızca yayınlanmış PyInstaller `JARVIS.exe` paketi içinde çalışır. Kaynak kodu/CLI ile çalıştırılan sürüm kendisini dosya üzerine yazarak güncellemez.
- Tek bir GitHub Release, hem `JARVIS-Android-release.apk` hem `JARVIS-Windows.zip` dosyalarını ve ortak `update.json` sürüm manifestini içerir. Release iş akışı yalnızca sürüm etiketi gönderildiğinde çalışır; etiket adı `JARVIS_HOST/VERSION` ve Android `versionName` ile eşleşmelidir.

### İlk sürüme geçiş notu

Daha önce Actions'tan alınmış `debug` APK'sı veya farklı bir anahtarla imzalanmış Windows EXE'si, yeni yayınla her zaman yerinde güncellenemez. Android'in imza kuralı nedeniyle ilk imzalı Android sürümüne geçerken eski debug uygulamasını kaldırıp yeni imzalı APK'yı elle kurmak gerekebilir; kaldırma uygulama içindeki bağlantı ayarlarını siler, bu yüzden Windows host adresini ve erişim token'ını önceden güvenli şekilde sakla. Bundan sonraki sürümler aynı Android keystore ile imzalanır ve uygulama içinden güncellenebilir. Windows'ta updater içermeyen eski paket için de ilk geçişin elle kurulması gerekir.

### İlk imzalı Android yayınını etkinleştirme

Android güncellemesinin mevcut kurulumun üzerine yüklenebilmesi için bütün sürümlerin **aynı kalıcı imzalama anahtarıyla** imzalanması gerekir. Keystore dosyasını Git deposuna koyma.

1. Yerel makinede bir defa keystore oluştur:
   ```powershell
   keytool -genkeypair -v -keystore jarvis-release.jks -alias jarvis-release -keyalg RSA -keysize 2048 -validity 10000
   $bytes = [System.IO.File]::ReadAllBytes("jarvis-release.jks")
   [Convert]::ToBase64String($bytes) | Set-Clipboard
   ```
2. GitHub deposunda **Settings → Secrets and variables → Actions** bölümüne şu sırlarla ekle:
   - `ANDROID_SIGNING_KEYSTORE_BASE64`: panoya alınan Base64 içeriği
   - `ANDROID_SIGNING_STORE_PASSWORD`: keystore parolası
   - `ANDROID_SIGNING_KEY_ALIAS`: `jarvis-release`
   - `ANDROID_SIGNING_KEY_PASSWORD`: anahtar parolası
3. Keystore'un yedek kopyasını güvenli şekilde sakla. Bu anahtar kaybolursa mevcut Android kurulumları yeni sürümle yerinde güncellenemeyebilir.
4. Sürüm etiketini `v2.2.4` biçiminde gönder. İş akışı Android ve Windows paketlerini kurar, özetlerini hesaplar ve tek GitHub Release olarak yayımlar.

İmzalama sırları eklenmeden Android yayın iş akışı bilerek başarısız olur; sabit imzalama anahtarı olmadan güncellenebilir APK yayımlamak doğru değildir. Windows ZIP'i TLS ve manifestteki SHA-256 ile doğrulanır; ayrıca Windows kod imzalama sertifikası kullanılmadığından Windows SmartScreen uyarısı görülebilir.

## Mimari
- Android arayüzü native APK olarak kalır; komutlar isteğe bağlı olarak Windows JARVIS ortak hostuna yönlendirilir.
- HOST ayarlarında Windows IP adresi ve `JARVIS_HOST/config/bridge_token.txt` içindeki token kullanılır.
- Android SpeechRecognizer ile sesli komut alır; dil kullanılabilirliği Android cihazın speech service'ine bağlıdır.
- Piper/eSpeak ve ONNX Runtime kullanılarak yerel Türkçe ses sentezi (TTS) yapılır.
- Piper TTS'nin çevrimdışı olması, konuşma tanıma (ASR) veya büyük dil modelinin de çevrimdışı olduğu anlamına gelmez.
- Stagepulse siyah / altın / beyaz HUD korunur.
- HOST bağlantısı yapılandırılmışsa komutlar Windows `JARVIS_HOST` çekirdeğinde işlenir.
- HOST bağlantısı yapılandırılmamışsa desteklenen temel Android komutları cihaz üzerinde yerel çalışır.
- Windows masaüstü JARVIS ayrı bir uygulama ve ayrı çalışma ortamıdır.

## Windows host bağlantısı

1. Windows'ta `StagepulseJARVIS.exe` uygulamasını aç (kaynak kodundan çalıştırıyorsan `JARVIS_HOST/START_JARVIS_WITH_ANDROID.bat` kullanabilirsin).
2. Masaüstündeki **ANDROID HOST** düğmesine basıp HTTP/özel Wi-Fi uyarısını onayla.
3. Gösterilen `http://WINDOWS_IP:8765` adreslerinden uygun olanı Android uygulamasındaki **HOST** alanına gir.
4. **TOKEN'I KOPYALA** düğmesiyle erişim token'ını kopyala ve Android HOST ayarlarına yapıştır. Token dosyası EXE modunda `%APPDATA%\\StagepulseJARVIS\\config\\bridge_token.txt` altında saklanır.
5. Telefon ve bilgisayar aynı yerel ağda olmalı. Gerekirse Windows Güvenlik Duvarı'nda TCP 8765'e yalnızca özel ağdan izin ver.

**Ağ güvenliği:** Köprü doğrudan `python android_bridge.py` ile çalıştırıldığında yalnızca `127.0.0.1` üzerinde dinler. Telefon bağlantısı için yukarıdaki başlatıcı LAN modunu açıkça etkinleştirir. LAN modu HTTP kullandığından yalnızca güvendiğin özel Wi-Fi üzerinde kullan; TCP 8765'i internete yönlendirme, token'ı paylaşma veya halka açık Wi-Fi'de bağlanma. Android istemcisi HTTP adreslerini özel IPv4 LAN aralıklarıyla sınırlar. Uzaktan erişim gerekiyorsa HTTPS/VPN kullan.

Köprüyü internete açma ve token'ı repoya yükleme. Token dosyası yerel kalmalıdır.

## Build

Android Studio veya [GitHub Actions](https://github.com/ibrahimFOH/JARVIS-Android/actions) üzerinden build edilebilir. Android build'i için internet bağlantısı gerekir; Gradle görevi Piper ses modeli ve eSpeak varlıklarını indirir. GitHub Actions'tan kurulum dosyası almak için başarılı build çalışmasının sayfasındaki `JARVIS-Android-PIPER-debug` artifact'ini indir.
