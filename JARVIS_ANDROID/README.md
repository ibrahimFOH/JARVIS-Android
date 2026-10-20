# JARVIS Android

Bağımsız Android JARVIS uygulaması.

## Mimari
- Android arayüzü native APK olarak kalır; komutlar isteğe bağlı olarak Windows JARVIS ortak hostuna yönlendirilir.
- HOST ayarlarında Windows IP adresi ve `JARVIS_HOST/config/bridge_token.txt` içindeki token kullanılır.
- Android SpeechRecognizer ile Türkçe sesli komut alır.
- Android TextToSpeech ile Türkçe yanıt verir.
- Stagepulse siyah / altın / beyaz HUD korunur.
- HOST bağlantısı yapılandırılmışsa komutlar Windows `JARVIS_HOST` çekirdeğinde işlenir.
- HOST bağlantısı yapılandırılmamışsa temel Android komutları cihaz üzerinde yerel çalışır.
- Windows masaüstü JARVIS ayrı bir uygulama ve ayrı çalışma ortamıdır.

## Windows host bağlantısı

1. Windows'ta `JARVIS_HOST/START_JARVIS_WITH_ANDROID.bat` dosyasını çalıştır.
2. `ipconfig` ile Windows IPv4 adresini bul.
3. `JARVIS_HOST/config/bridge_token.txt` içindeki token'ı al.
4. Android uygulamasında **HOST** düğmesine bas; `http://WINDOWS_IP:8765` ve token'ı girip test et.
5. Telefon ve bilgisayar aynı yerel ağda olmalı. Gerekirse Windows Güvenlik Duvarı'nda TCP 8765'e yalnızca özel ağdan izin ver.

Köprüyü internete açma ve token'ı repoya yükleme. Token dosyası yerel kalmalıdır.

## Build
Android Studio veya GitHub Actions üzerinden build edilebilir. Android build'i için internet bağlantısı gerekir; Gradle görevi Piper ses modeli ve eSpeak varlıklarını indirir.
