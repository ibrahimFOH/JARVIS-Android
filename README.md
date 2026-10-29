# JARVIS Android Adaptasyonu

Bu paket, mevcut JARVIS.zip ve Downloads.zip içeriğinin Android'e uyarlanmış sürümüdür.

Mimari:
- **JARVIS_HOST/**: Windows JARVIS, yerel/isteğe bağlı bulut AI sağlayıcıları ve açıkça etkinleştirilen Android LAN köprüsü.
- **JARVIS_ANDROID/**: Native Android APK. Türkçe STT + TTS + Stagepulse altın/beyaz HUD; komutları LAN üzerinden ortak Windows çekirdeğine yollar.
- Android, ağır Python masaüstü otomasyonunu telefona taşımak yerine `JARVIS_HOST` içindeki aynı komut motorunu ve AI sağlayıcı yapılandırmasını kullanır. Yerel kullanım için Ollama `qwen3:0.6b` varsayılandır; `auto` modu önce Ollama'yı, başarısız olursa yapılandırılmış alternatifleri dener.

## Android + Windows ortak çekirdek

1. Windows bilgisayarda `StagepulseJARVIS.exe` uygulamasını açın (kaynak kurulumunda `JARVIS_HOST/START_JARVIS_WITH_ANDROID.bat` kullanılabilir).
2. Masaüstü arayüzündeki **ANDROID HOST** düğmesine basın ve HTTP/özel Wi-Fi güvenlik uyarısını onaylayın.
3. Gösterilen `http://WINDOWS_IP:8765` adreslerinden uygun olanı Android uygulamasındaki **HOST** alanına girin.
4. Arayüzdeki **TOKEN'I KOPYALA** düğmesine basıp token'ı Android HOST ayarlarına yapıştırın. Token dosyası Windows kullanıcı profilinde saklanır; kimseyle paylaşmayın.
5. Gerekirse Windows Güvenlik Duvarı'nda TCP 8765'e yalnızca özel ağ profili için izin verin.

**Ağ güvenliği:** `android_bridge.py` doğrudan çalıştırıldığında yalnızca `127.0.0.1` üzerinde dinler. Masaüstündeki **ANDROID HOST** düğmesi, kullanıcı onayından sonra LAN dinleyicisini açar. LAN modu HTTP kullandığından yalnızca güvendiğin özel Wi-Fi üzerinde kullan; TCP 8765'i internete yönlendirme ve token'ı paylaşma. Android istemcisi düz HTTP adreslerini özel IPv4 LAN aralıklarıyla sınırlar. Uzaktan erişim gerekiyorsa HTTPS/VPN kullan.

Android komutları bağlandığında Windows hostuna gönderilir; böylece komutlar aynı Python komut işleyicisini ve AI yapılandırmasını kullanır. Host ayarı boş bırakılırsa Android yerel komutlarına döner. Köprü token doğrulaması kullanır; bu servis internete/port yönlendirmesiyle dış ağa açılmamalıdır.

Android derlemek için Android Studio/Gradle gerekir. Windows EXE'yi çalıştırmak için Python kurulumu gerekmez. Kaynak kodundan çalıştırmak için Python 3.11 x64 ve proje gereksinimleri gerekir. Yerel AI kullanımı için ayrıca Ollama servisi ve `qwen3:0.6b` modeli kurulmalıdır.


## Windows tek dosya EXE

Windows kaynak kodu JARVIS_HOST/, Android uygulaması JARVIS_ANDROID/ altında tutulur. İki yapı aynı mevcut depoda kalır; ikinci bir depo oluşturulmaz.

Windows arayüzünde:
- UZMANLAR: APK'deki uzman kataloğuna karşılık gelen FOH, Monitor, RF, System Tech, Rider, Stage Plot, SPL, Audio System Design, Live Sound Troubleshooting, Dante, Lighting ve Event Production rollerini içerir. Ek olarak yazılım, Windows/Linux, stüdyo, SEO, araştırma ve dokümantasyon profilleri bulunur.
- AI PROVIDER: Ollama, otomatik seçim, Gemini, Groq, OpenAI, xAI/Grok, Anthropic, DeepSeek, Perplexity, OpenRouter ve özel OpenAI uyumlu uç nokta seçilebilir.
- Varsayılan sağlayıcı Ollama'dır (qwen3:0.6b). Bulut sağlayıcıları için ilgili API anahtarını AI PROVIDER ekranından girin. Mevcut config.json içindeki eski sağlayıcı/model ayarları da yeni çekirdeğe aktarılır.
- API ayarları %APPDATA%\StagepulseJARVIS\ai_settings.json dosyasında tutulur. API anahtarları Windows DPAPI ile şifrelenir; DPAPI başarısız olursa düz metin olarak kaydedilmez. Bu dosyayı ya da köprü token'ını depoya eklemeyin.

### Tek EXE oluşturma

1. Windows 10/11 x64 üzerinde Python 3.11 x64 kurulu olmalı.
2. JARVIS_HOST/BUILD_JARVIS_EXE.bat dosyasını çalıştırın.
3. Çıktı: JARVIS_HOST/dist/StagepulseJARVIS.exe.

GitHub Actions üzerindeki JARVIS Windows Single-EXE Build akışı da tek dosyalı Windows x64 EXE üretir ve StagepulseJARVIS-Windows-x64-EXE adlı artifact olarak yayınlar. Akış; sözdizimi kontrolünü, uzman paneli kontrolünü, AI sağlayıcı regresyon testlerini ve PyInstaller derlemesini çalıştırır.

Tek EXE uygulamanın dosya biçimini birleştirir; Ollama modeli EXE içine gömülü değildir. Yerel AI için Ollama servisi ve seçilen model bilgisayarda kurulu olmalıdır. Alternatif olarak AI PROVIDER ekranından API sağlayıcısı yapılandırılabilir.
