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
