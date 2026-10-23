# JARVIS Android Adaptasyonu

Bu paket, mevcut JARVIS.zip ve Downloads.zip içeriğinin Android'e uyarlanmış sürümüdür.

Mimari:
- **JARVIS_HOST/**: Mevcut Windows JARVIS, Ollama-only yapı ve Android LAN bridge.
- **JARVIS_ANDROID/**: Native Android APK. Türkçe STT + TTS + Stagepulse altın/beyaz HUD; komutları LAN üzerinden ortak Windows çekirdeğine yollar.
- Android, ağır Python masaüstü otomasyonunu telefona taşımak yerine `JARVIS_HOST` içindeki aynı komut motoru ve Ollama yapılandırmasını kullanır. 4 GB RAM'li makinede Ollama `qwen3:0.6b` korunur.

## Android + Windows ortak çekirdek

1. Windows bilgisayarda `JARVIS_HOST/START_JARVIS_WITH_ANDROID.bat` dosyasını çalıştırın.
2. İlk çalıştırmada `JARVIS_HOST/config/bridge_token.txt` dosyası otomatik oluşturulur. Token'ı kimseyle paylaşmayın.
3. Windows bilgisayarının yerel IPv4 adresini öğrenin (`ipconfig`). Telefon ve bilgisayar aynı Wi-Fi/LAN üzerinde olmalı.
4. APK'de **HOST** düğmesine basın; adres olarak `http://WINDOWS_IP:8765`, token olarak `bridge_token.txt` içeriğini girip bağlantıyı test edin.
5. Windows Güvenlik Duvarı bağlantıyı engellerse yalnızca özel ağ profili için TCP 8765'e izin verin.

Android komutları bağlandığında Windows hostuna gönderilir; böylece komutlar aynı Python komut işleyicisini ve AI yapılandırmasını kullanır. Host ayarı boş bırakılırsa Android yerel komutlarına döner. Köprü token doğrulaması kullanır; bu servis internete/port yönlendirmesiyle dış ağa açılmamalıdır.

Android gereksinimi: Android Studio.
Host gereksinimi: Mevcut Python/venv + Ollama `qwen3:0.6b`.


## Windows tek dosya EXE

Windows kaynak kodu JARVIS_HOST/, Android uygulaması JARVIS_ANDROID/ altında tutulur. İki yapı aynı mevcut depoda kalır; ikinci bir depo oluşturulmaz.

Windows arayüzünde:
- UZMANLAR: APK'deki uzman kataloğuna karşılık gelen FOH, Monitor, RF, System Tech, Rider, Stage Plot, SPL, Audio System Design, Live Sound Troubleshooting, Dante, Lighting ve Event Production rollerini içerir. Ek olarak yazılım, Windows/Linux, stüdyo, SEO, araştırma ve dokümantasyon profilleri bulunur.
- AI PROVIDER: Ollama, otomatik seçim, Gemini, Groq, OpenAI, xAI/Grok, Anthropic, DeepSeek, Perplexity, OpenRouter ve özel OpenAI uyumlu uç nokta seçilebilir.
- Varsayılan sağlayıcı Ollama'dır (qwen3:0.6b). Bulut sağlayıcıları için ilgili API anahtarını AI PROVIDER ekranından girin. Mevcut config.json içindeki eski sağlayıcı/model ayarları da yeni çekirdeğe aktarılır.
- API ayarları %APPDATA%\StagepulseJARVIS\ai_settings.json dosyasında tutulur. Windows DPAPI kullanılabildiğinde anahtarlar işletim sistemi kullanıcı hesabıyla korunur; bu dosyayı ya da köprü token'ını depoya eklemeyin.

### Tek EXE oluşturma

1. Windows 10/11 x64 üzerinde Python 3.11 x64 kurulu olmalı.
2. JARVIS_HOST/BUILD_JARVIS_EXE.bat dosyasını çalıştırın.
3. Çıktı: JARVIS_HOST/dist/StagepulseJARVIS.exe.

GitHub Actions üzerindeki JARVIS Windows Single-EXE Build akışı da tek dosyalı Windows x64 EXE üretir ve StagepulseJARVIS-Windows-x64-EXE adlı artifact olarak yayınlar. Akış; sözdizimi kontrolünü, uzman paneli kontrolünü, AI sağlayıcı regresyon testlerini ve PyInstaller derlemesini çalıştırır.

Tek EXE uygulamanın dosya biçimini birleştirir; Ollama modeli EXE içine gömülü değildir. Yerel AI için Ollama servisi ve seçilen model bilgisayarda kurulu olmalıdır. Alternatif olarak AI PROVIDER ekranından API sağlayıcısı yapılandırılabilir.
