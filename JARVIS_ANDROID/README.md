# JARVIS Android

Bağımsız Android JARVIS uygulaması. Bu proje, Windows Asistan 0.1.5 EXE'sinin dönüştürülmüş paketi değildir; Android için ayrı yazılmış bir uygulamadır.

## Güncel doğrulama

- Package/application ID: `com.stagepulse.jarvis`
- Sürüm: `2.2.0-piper` (versionCode 220)
- minSdk 26 (Android 8.0), targetSdk 35
- ABI: `arm64-v8a`, `armeabi-v7a`
- En son doğrulanmış GitHub Actions build'i: [run #129](https://github.com/ibrahimFOH/JARVIS-Android/actions/runs/39582942609)
- Run #129 içindeki `JARVIS-Android-PIPER-debug` artifact'i başarılı derlemeden alındı. Cihaz/emülatör üzerinde henüz elle test edilmedi.

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
