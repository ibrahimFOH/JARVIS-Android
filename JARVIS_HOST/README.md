# Stagepulse J.A.R.V.I.S. Windows Host

J.A.R.V.I.S. masaüstü uygulamasının Windows çekirdeği, tek dosya EXE derlemesi ve Android uygulamasıyla yerel ağ bağlantısı bu klasörde bulunur.

## Bileşenler

- `core/`: komut işleme, ücretsiz yapay zekâ sağlayıcıları, hafıza, güvenli Git/dosya araçları, güncelleme mantığı ve Stagepulse hizmetlerine uygun ücretsiz yazılım araştırıcısı.
- `gui/`: Stagepulse siyah/altın/beyaz masaüstü arayüzü.
- `voice/`: konuşma tanıma ve metin seslendirme katmanı.
- `android_bridge.py`: kullanıcı açıkça etkinleştirdiğinde Android istemcisi için yerel ağ köprüsü.
- `config/`: örnek ve yerel kullanıcı yapılandırması.
- `tests/`: sağlayıcı, güvenlik, komut ve Android köprüsü regresyon testleri.

## Çalıştırma

Windows 10/11 x64 ve Python 3.11 x64 gerekir. `QUICKSTART.md` içindeki adımlarla sanal ortamı kurup `run_jarvis.bat` üzerinden başlatın. Hazır dağıtım için `BUILD_JARVIS_EXE.bat` tek dosyalı `StagepulseJARVIS.exe` üretir.

## Yapay zekâ sağlayıcıları

Yalnızca ücretsiz kullanım kabul edilir. Yerel Ollama varsayılandır ve API ücreti oluşturmaz. Bulut sağlayıcılarında yalnızca Gemini Free Tier ve Groq Free Plan etkinleştirilebilir. Her sağlayıcı için API anahtarına ek olarak ücretsiz plan/faturalandırma kapalı onayı gerekir; JARVIS hesap faturalandırmasını sağlayıcı hesabından okuyamaz. Ücretsiz kota dolarsa istek reddedilir veya durur; ücretli modele, plana ya da başka ücretli API'ye geçiş yapılmaz. xAI Grok API ve diğer ücretli/özel uç noktalar kapalıdır. API anahtarları arayüzden girilir; Windows DPAPI ile korunur ve koruma başarısız olursa düz metin kaydedilmez.

## Ses

Sesli kontrol ve sürekli dinleme kullanıcı tarafından açılıp kapatılabilir. Konuşma tanıma hizmeti internet bağlantısı isteyebilir. Yerel TTS veya Ollama kullanımı tüm ses tanıma ve web işlemlerini çevrimdışı yapmaz.

## Güvenlik

- Bilinmeyen uygulama komutları kabuk üzerinden çalıştırılmaz.
- Android köprüsü varsayılan olarak localhost'ta kalır; LAN erişimi masaüstü arayüzünden açık kullanıcı onayı ister.
- Köprü token'ı yerel kullanıcı yapılandırmasında tutulur. Token'ı paylaşmayın ve TCP 8765'i internete yönlendirmeyin.
- API anahtarlarını kaynak dosyalarına veya GitHub'a koymayın.
- Güncelleyici bu depoya ait sürüm varlıklarını ve özetleri doğrular.

## Android bağlantısı

Android istemcisi `../JARVIS_ANDROID/` klasöründedir. Windows masaüstünde **ANDROID BAĞLANTISI** düğmesini açın; IP, port ve token bilgilerini Android uygulamasına girin. Yalnızca güvendiğiniz özel Wi-Fi ağında kullanın.

## Test ve dağıtım sınırları

GitHub Actions Windows tek dosya EXE ve Android Debug APK derlemelerini çalıştırır. CI derlemesi gerçek mikrofon/hoparlör denemesinin, Windows üzerinde elle kurulumun veya fiziksel Android cihaz testinin yerini tutmaz. Android mağaza/müşteri dağıtımı için kalıcı imzalama anahtarıyla Release APK oluşturulmalıdır.

## Ayrıntılı rehber

Kurulum, sağlayıcı ayarları, sesli komut, GitHub işlemleri ve sorun giderme adımları `QUICKSTART.md` dosyasındadır.