# JARVIS Android

Bağımsız Android JARVIS uygulaması. Bu proje, Windows Asistan 0.1.5 EXE'sinin dönüştürülmüş paketi değildir; Android için ayrı yazılmış bir uygulamadır.

## Güncel doğrulama

- Package/application ID: `com.stagepulse.jarvis`
- Sürüm: `2.2.2-piper` (versionCode 222)
- minSdk 26 (Android 8.0), targetSdk 35
- ABI: `arm64-v8a`, `armeabi-v7a`
- Güncel CI/derleme geçmişi: [GitHub Actions](https://github.com/ibrahimFOH/JARVIS-Android/actions)
- CI, APK'yı derler ve Python komut yönlendirme/güncelleme denetimlerini çalıştırır. Gerçek telefonda/emülatörde elle kurulum testi ayrıca gerekir.

## Otomatik güncelleme

- Android uygulaması açılışta sürüm kontrolü yapar; gereksiz istekleri azaltmak için otomatik denetim 12 saatte bir yapılır. Arayüzdeki **UPDATE** düğmesi denetimi elle başlatır.
- Yeni Android APK'sı yalnızca bu depodaki en son GitHub Release içinden alınır. İndirmeden önce HTTPS kaynağı, indirildikten sonra SHA-256 özeti doğrulanır. Android güvenlik gereği kurulum onayı ister; sessiz kurulum yapılmaz.
- Windows masaüstü JARVIS arayüzü de 12 saatte bir güncelleme kontrol eder; **UPDATE** düğmesi elle kontrol sağlar. Yeni ZIP'in SHA-256 değeri doğrulanır. Kurulum klasörü değiştirilirken `config/config.json` ve `config/bridge_token.txt` korunur; eski dizin geri dönüş için `rollback` klasöründe tutulur. Yönetici izni gereken kurulum konumlarında Windows UAC onayı gerekebilir.
- Windows otomatik değiştirme yalnızca yayınlanmış PyInstaller `JARVIS.exe` paketi içinde çalışır. Kaynak kodu/CLI ile çalıştırılan sürüm kendisini dosya üzerine yazarak güncellemez.
- Tek bir GitHub Release, hem `JARVIS-Android-release.apk` hem `JARVIS-Windows.zip` dosyalarını ve ortak `update.json` sürüm manifestini içerir. Release iş akışı yalnızca sürüm etiketi gönderildiğinde çalışır; etiket adı `JARVIS_HOST/VERSION` ve Android `versionName` ile eşleşmelidir.

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
4. Sürüm etiketini `v2.2.2-piper` biçiminde gönder. İş akışı Android ve Windows paketlerini kurar, özetlerini hesaplar ve tek GitHub Release olarak yayımlar.

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

1. Windows'ta `JARVIS_HOST/START_JARVIS_WITH_ANDROID.bat` dosyasını çalıştır.
2. `ipconfig` ile Windows IPv4 adresini bul.
3. `JARVIS_HOST/config/bridge_token.txt` içindeki token'ı al.
4. Android uygulamasında **HOST** düğmesine bas; `http://WINDOWS_IP:8765` ve token'ı girip test et.
5. Telefon ve bilgisayar aynı yerel ağda olmalı. Gerekirse Windows Güvenlik Duvarı'nda TCP 8765'e yalnızca özel ağdan izin ver.

Köprüyü internete açma ve token'ı repoya yükleme. Token dosyası yerel kalmalıdır.

## Build

Android Studio veya [GitHub Actions](https://github.com/ibrahimFOH/JARVIS-Android/actions) üzerinden build edilebilir. Android build'i için internet bağlantısı gerekir; Gradle görevi Piper ses modeli ve eSpeak varlıklarını indirir. GitHub Actions'tan kurulum dosyası almak için başarılı build çalışmasının sayfasındaki `JARVIS-Android-PIPER-debug` artifact'ini indir.
