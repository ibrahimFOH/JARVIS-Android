# JARVIS Android

Bağımsız Android JARVIS uygulaması. Bu proje, Windows Asistan 0.1.5 EXE'sinin dönüştürülmüş paketi değildir; Android için ayrı yazılmış bir uygulamadır.

## Güncel doğrulama

- Package/application ID: `com.stagepulse.jarvis`
- Sürüm: `2.3.0-device-actions` (versionCode 230)
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
4. Sürüm etiketini `v2.2.2-piper` biçiminde gönder. İş akışı Android ve Windows paketlerini kurar, özetlerini hesaplar ve tek GitHub Release olarak yayımlar.

İmzalama sırları eklenmeden Android yayın iş akışı bilerek başarısız olur; sabit imzalama anahtarı olmadan güncellenebilir APK yayımlamak doğru değildir. Windows ZIP'i TLS ve manifestteki SHA-256 ile doğrulanır; ayrıca Windows kod imzalama sertifikası kullanılmadığından Windows SmartScreen uyarısı görülebilir.

## Mimari
- Android arayüzü native APK olarak kalır; komutlar isteğe bağlı olarak Windows JARVIS ortak hostuna yönlendirilir.
- HOST ayarlarında Windows IP adresi ve `JARVIS_HOST/config/bridge_token.txt` içindeki token kullanılır.
- Android SpeechRecognizer ile sesli komut alır; dil kullanılabilirliği Android cihazın speech service'ine bağlıdır.
- Ses girişi Android SpeechRecognizer (Türkçe `tr-TR`, çevrimiçi tanıma tercihli) ile; ses çıkışı Android sistem TTS motoruyla çalışır. Piper/eSpeak/ONNX paketlenmez.
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

Android Studio veya [GitHub Actions](https://github.com/ibrahimFOH/JARVIS-Android/actions) üzerinden build edilebilir. Derleme için Android SDK/Gradle paketlerine internet erişimi gerekir; Piper modeli, eSpeak veya NDK/CMake varlıkları indirilmez. Güncel test APK'sı başarılı CI çalışmasının `JARVIS-Android-2.3.0-device-actions` artifact'idir. CI başarısı gerçek telefonda elle test yapıldığı anlamına gelmez.


## Android 2.3.0: profil, dosyalar ve cihaz eylemleri

### Ses ve kişisel profil
- Ses girişi Android SpeechRecognizer ile Türkçe `tr-TR` kullanır; çevrimiçi tanıma tercih edilir. Sonuç sağlayıcının kalitesine ve internetine bağlıdır. Alternatif sonuçlar puanlanır ve sık karşılaşılan "Heijan biz" / "eğitim pakeylri baziela" benzeri hatalar için sınırlı normalizasyon uygulanır.
- "Hey JARVIS" tek başına algılanırsa asistan yanıt verir ve ön planda sonraki komutu dinlemeyi dener. Uygulama arka planda gizlice sürekli dinleme yapmaz; önce kullanıcının mikrofon düğmesine basması gerekir.
- Profil ilk kullanımda sorulur; kullanıcı adı, meslek/rol, şirket ve seçilen tercihler yalnızca bu cihazda saklanır. "Beni tanıyor musun", "Adımı ... olarak hatırla", "Profil" ve yerel hafıza komutları kullanılabilir.
- **Profil, ses biyometrisi değildir.** Android konuşma tanıma sağlayıcısı konuşmacının kimliğini doğrulamaz. Başka kişi kullanıyorsa cihaz profilini PROFİL ekranından değiştirmek gerekir.
- Android'in kurulu Text-to-Speech hizmeti yanıtları seslendirir. Türkçe ses yoksa Android'in Metin Okuma ayarlarından bir Türkçe ses indir/etkinleştir.

### Telefon ve dosya işlemleri
- "Eğitim paketi hazırla": Windows host bağlıysa isteği ortak Windows komut motoruna/AI yapılandırmasına yollar ve başarılı yanıtı telefondaki dosyaya kaydetmeyi dener. PC bağlantısı yoksa 35 modüllü yerel ses mühendisliği eğitim taslağı oluşturulur.
- "Not al ...", "Dosya oluştur not.txt içeriği ...", "Metin dosyası oluştur ...", "Klasör oluştur ...", "JARVIS dosyalarını listele", "Son dosyayı aç", "Dosya oku ...", "Dosya aç ..." komutları vardır. Modern Android sürümlerinde metin/Markdown/CSV/JSON/HTML/XML dosyaları ortak depolamadaki `İndirilenler/JARVIS/` klasörüne kaydedilir. Diğer dosyaları açmak/okumak için Android dosya seçicisinde kullanıcı dosyayı seçer. Son oluşturulan dosyanın silinmesi için onay gerekir.
- Uygulama açma, Kişiler/Mesajlar/E-posta/Hesap Makinesi/Saat/Dosya Yöneticisi, kamera, harita, medya sesi, fener, zamanlayıcı/alarm ve uygun ayar ekranları için yerel komutlar bulunur. Mesaj gönderme, alarmı başlatma, güç menüsünden telefonu kapatma gibi eylemlerde kullanıcı onayı korunur.
- Wi-Fi, Bluetooth ve mobil verinin doğrudan açılıp kapatılması Android sürümüne göre üçüncü taraf uygulamalara kapalı olabilir. Bu durumda JARVIS ilgili ayarı veya Hızlı Ayarlar panelini açar; gerçek durumu değiştirdiğini iddia etmez.
- Ekran kilidi, Ana ekran/Geri/Bildirimler/Hızlı Ayarlar, görünür ekran metnini oku, "Tıkla Kaydet", "Alana yaz ..." ve kaydırma için Android **Erişilebilirlik** hizmeti isteğe bağlıdır. İlk kullanımda Android ayarlarında kullanıcı tarafından etkinleştirilmelidir. Bu güçlü izinle ekran metni yalnızca açık bir kullanıcı komutu sırasında okunur; olaylar arka planda kaydedilmez. Bazı güvenli pencereler ve uygulamalar erişilebilirlik eylemlerini engelleyebilir.
- Ekran parlaklığı için Android'in "Sistem ayarlarını değiştirme" özel izni gerekir. Telefonu zorla kapatmak, başka uygulamaları zorla sonlandırmak, korumalı sistem ayarlarını atlatmak veya bütün uygulamalarda her eylemi garanti etmek mümkün değildir.

### Windows ortak çekirdeği ve gizlilik
- HOST ayarı yapılandırılmış ve ulaşılabilir olduğunda yerel Android kontrolleri cihazda kalır; genel AI/araştırma/üretim istekleri doğrulanmış LAN köprüsü üzerinden Windows JARVIS'e gider. Cihaz profili bağlamı uzak komuta eklenebilir. Ekran metni otomatik olarak PC'ye gönderilmez.
- HOST bağlantısı yoksa Android yerel fonksiyonları, dosya oluşturma ve cihaz eylemleri çalışır; tam Windows pencere/süreç/dosya otomasyonu, Windows AI modeli ve ağır masaüstü iş akışları PC'nin çalışmasını gerektirir.
- Köprüyü internete açma ve token'ı repoya yükleme. Telefon ile bilgisayar aynı güvenilir yerel ağda olmalıdır.
- CI kaynak kontrollerini ve APK derlemesini doğrular. Fiziksel cihazda mikrofon, çevrimiçi Türkçe konuşma, sistem TTS, dosya sağlayıcısı ve Erişilebilirlik izinleri ayrıca test edilmelidir.
