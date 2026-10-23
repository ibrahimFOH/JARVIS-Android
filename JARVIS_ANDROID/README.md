# JARVIS Android

Bağımsız Android JARVIS uygulaması. Bu proje, Windows Asistan 0.1.5 EXE'sinin dönüştürülmüş paketi değildir; Android için ayrı yazılmış bir uygulamadır.

## Güncel doğrulama

- Package/application ID: `com.stagepulse.jarvis`
- Sürüm: `2.4.0-cross-app-voice` (versionCode 240)
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

Android Studio veya [GitHub Actions](https://github.com/ibrahimFOH/JARVIS-Android/actions) üzerinden build edilebilir. Derleme için Android SDK/Gradle paketlerine internet erişimi gerekir; Piper modeli, eSpeak veya NDK/CMake varlıkları indirilmez. Güncel test APK'sı başarılı CI çalışmasının `JARVIS-Android-2.4.1-specialist-agents` artifact'idir. CI başarısı gerçek telefonda elle test yapıldığı anlamına gelmez.


## Android 2.4.1: uygulamalar arası sesli kontrol, profil ve dosyalar

### Ses ve kişisel profil
- Ses girişi Android SpeechRecognizer ile Türkçe `tr-TR` kullanır; çevrimiçi tanıma tercih edilir. Sonuç sağlayıcının kalitesine ve internetine bağlıdır. Alternatif sonuçlar puanlanır ve sık karşılaşılan "Heijan biz" / "eğitim pakeylri baziela" benzeri hatalar için sınırlı normalizasyon uygulanır.
- JARVIS ana uygulamasında **KONUŞ** düğmesiyle sürekli diyalog oturumu başlatılır; yeniden **DURDUR** ile kapatılır. Ana uygulama dışındaki ekranlarda konuşmak için Erişilebilirlik hizmetini etkinleştirip ekrandaki altın **MIC** yüzen düğmesine dokun. Kullanıcı başlatınca görünür bir sürekli mikrofon bildirimi çıkar ve konuşma bu oturum içinde uygulamalar arasında sürer. JARVIS açılışta gizlice/sürekli dinleme yapmaz; yüzen mikrofon düğmesiyle oturum ayrıca başlatılır.
- Profil ilk kullanımda sorulur; kullanıcı adı, meslek/rol, şirket ve seçilen tercihler yalnızca bu cihazda saklanır. "Beni tanıyor musun", "Adımı ... olarak hatırla", "Profil" ve yerel hafıza komutları kullanılabilir.
- **Profil, ses biyometrisi değildir.** Android konuşma tanıma sağlayıcısı konuşmacının kimliğini doğrulamaz. Başka kişi kullanıyorsa cihaz profilini PROFİL ekranından değiştirmek gerekir.
- Android'in kurulu Text-to-Speech hizmeti yanıtları seslendirir. Türkçe ses yoksa Android'in Metin Okuma ayarlarından bir Türkçe ses indir/etkinleştir.

### Telefon ve dosya işlemleri
- "Eğitim paketi hazırla": Windows host bağlıysa isteği ortak Windows komut motoruna/AI yapılandırmasına yollar ve başarılı yanıtı telefondaki dosyaya kaydetmeyi dener. PC bağlantısı yoksa 35 modüllü yerel ses mühendisliği eğitim taslağı oluşturulur.
- "Not al ...", "Dosya oluştur not.txt içeriği ...", "Metin dosyası oluştur ...", "Klasör oluştur ...", "JARVIS dosyalarını listele", "Son dosyayı aç", "Dosya oku ...", "Dosya aç ..." komutları vardır. Modern Android sürümlerinde metin/Markdown/CSV/JSON/HTML/XML dosyaları ortak depolamadaki `İndirilenler/JARVIS/` klasörüne kaydedilir. Diğer dosyaları açmak/okumak için Android dosya seçicisinde kullanıcı dosyayı seçer. Son oluşturulan dosyanın silinmesi için onay gerekir.
- Uygulama açma, Kişiler/Mesajlar/E-posta/Hesap Makinesi/Saat/Dosya Yöneticisi, kamera, harita, medya sesi, fener, zamanlayıcı/alarm ve uygun ayar ekranları için yerel komutlar bulunur. Mesaj gönderme, alarmı başlatma, güç menüsünden telefonu kapatma gibi eylemlerde kullanıcı onayı korunur.
- Wi-Fi, Bluetooth ve mobil verinin doğrudan açılıp kapatılması Android sürümüne göre üçüncü taraf uygulamalara kapalı olabilir. Bu durumda JARVIS ilgili ayarı veya Hızlı Ayarlar panelini açar; gerçek durumu değiştirdiğini iddia etmez.
- Ekran kilidi, Ana ekran/Geri/Bildirimler/Hızlı Ayarlar, görünür ekran metnini oku, "Tıkla Kaydet", "Alana yaz ..." ve kaydırma için Android **Erişilebilirlik** hizmeti isteğe bağlıdır. İlk kullanımda Android ayarlarında kullanıcı tarafından etkinleştirilmelidir. Etkinleştirildiğinde MIC yüzen düğmesi başka uygulamaların üzerindeyken de komut almaya yarar. Ekran metni yalnızca açık komut sırasında okunur; olaylar arka planda kaydedilmez. Bazı güvenli pencereler, DRM ekranları ve uygulamalar erişilebilirlik eylemlerini engelleyebilir. Başka uygulama kontrollerinin sonucu her uygulamada garanti edilemez.
- Ekran parlaklığı için Android'in "Sistem ayarlarını değiştirme" özel izni gerekir. Telefonu zorla kapatmak, başka uygulamaları zorla sonlandırmak, korumalı sistem ayarlarını atlatmak veya bütün uygulamalarda her eylemi garanti etmek mümkün değildir.

### Windows ortak çekirdeği ve gizlilik
- HOST ayarı yapılandırılmış ve ulaşılabilir olduğunda yerel Android kontrolleri cihazda kalır; genel AI/araştırma/üretim istekleri doğrulanmış LAN köprüsü üzerinden Windows JARVIS'e gider. Cihaz profili bağlamı uzak komuta eklenebilir. Ekran metni otomatik olarak PC'ye gönderilmez.
- HOST bağlantısı yoksa Android yerel fonksiyonları, dosya oluşturma ve cihaz eylemleri çalışır; tam Windows pencere/süreç/dosya otomasyonu, Windows AI modeli ve ağır masaüstü iş akışları PC'nin çalışmasını gerektirir.
- Köprüyü internete açma ve token'ı repoya yükleme. Telefon ile bilgisayar aynı güvenilir yerel ağda olmalıdır.
- CI kaynak kontrollerini ve APK derlemesini doğrular. Fiziksel cihazda mikrofon, çevrimiçi Türkçe konuşma, sistem TTS, dosya sağlayıcısı ve Erişilebilirlik izinleri ayrıca test edilmelidir.


## Stagepulse uzman ajan motoru

Uzmanlar menüsü yalnızca görsel bir seçim listesi olarak kullanılmamalıdır. Uzman seçildiğinde Android, uzman kimliğini (agent_id) doğrulanmış Windows HOST köprüsüne gönderir; Windows tarafında core/specialist_agents.py ilgili görev profili ve varsa deterministik hesaplama aracını çalıştırır, ardından sonuç yapılandırılmış Ollama modeline gönderilir. Normal Windows/telefon komutları tanınan işlem niyetlerine göre çalışmaya devam eder. Menüdeki JARVIS / GENEL MOD seçeneği aktif uzmanı kapatır.

### Uzmanlık alanları
- FOH Engineer: gain structure, kanal/patch düzeni, EQ-dinamikler, bus/matrix ve soundcheck.
- Monitor Engineer: wedge/IEM, mix bus, sanatçı ihtiyaçları ve feedback riskleri.
- RF Engineer: frekans koordinasyonu için gerekli girdiler, anten/scan/yedek kanal planı.
- System Tech: sinyal zinciri, aktif PA/sub/monitor, polarite, kablo ve devreye alma kontrolleri.
- Rider Analyst: şartları, ekipman/kanal/personel gereksinimlerini ve çelişkileri yapılandırılmış rapora dönüştürme.
- Stage Plot Engineer: ölçülü sahne yerleşimi, mikrofon/DI/monitör koordinatları ve patch legend.
- SPL Calculator: mesafeye göre idealize seviye tahmini, kaynakların enerji toplamı ve yaklaşık gecikme.
- Audio System Designer: mekân, seyirci, kapsama, PA/sub, kontrol ve risk gereksinimlerinin birlikte değerlendirilmesi.
- Live Sound Troubleshooter: tek değişkenli testlerle arıza teşhisi ve güvenli kontrol sırası.
- Dante Network Engineer: topoloji, IP/alt ağ, clock, subscription ve switch/QoS teşhis akışı.
- Lighting Tech: DMX adres/universe patch'i ve fixture mode doğrulama kontrolü.
- Event Production Manager: ekip, teknik takvim, load-in/show/load-out, risk ve bütçe kalemleri.

### Çalışan deterministik araçlar
- SPL: ref_db=100 ref_m=1 target_m=10 power_ratio=1 sources=1 girdisi idealize serbest alan tahminini hesaplar. power_ratio, referans gücüne oran; sources, basit modelde eşdeğer kaynak sayısıdır.
- Gecikme: delay_distance_m=10 yaklaşık ses gecikmesini 343 m/s varsayımıyla hesaplar.
- FOH headroom: peak_dbfs=-2 target_peak_dbfs=-6 değerlerinden hedefe yaklaşmak için gereken yaklaşık kazanç azaltımını verir.
- Sistem tasarımı geometrisi: throw_m=20 horizontal_coverage_deg=90 ideal açısal genişliği hesaplar; akustik kapsama garantisi değildir.
- DMX: address=501 channels=20 universe=1 geçersiz 512 kanal sınırını yakalar.
- Dante IP: device_ip=192.168.1.10 subnet_mask=255.255.255.0 peer_ip=192.168.2.20 aynı alt ağ kontrolünü çalıştırır.
- Prodüksiyon süresi: duration_min=120 buffer_pct=15 tampon eklenmiş planlama süresini hesaplar.

### Çalışma sınırları ve güvenilirlik
Bu ajanlar ayrı ayrı eğitilmiş 12 bağımsız model değildir; yapılandırılmış tek JARVIS dil modeli, alan başına uzman talimatları, yönlendirme ve kontrollü araçlarla kullanılır. Ayrı modeller veya bir koordinatör/eleştirmen modeli eklemek için ayrı kaynak ve donanım değerlendirmesi gerekir. Küçük yerel model karmaşık mühendislik görevlerinde sınırlı kalabilir.

RF frekansı belirlemek için yasal bölge ve gerçek scan verisi; Dante ağı için cihaz/Controller çıktısı; SPL doğrulaması için kalibreli ölçüm; line-array kapsaması için üretici veri dosyaları ve modelleme/ölçüm; rider analizi için gerçek belge metni gerekir. Bu bilgiler yoksa ajan eksikleri belirtmeli, tahmini ölçüm diye sunmamalıdır. Araç sonuçları tests/test_specialist_agents.py testleriyle doğrulanır. HOST veya Ollama erişilemiyorsa Android uzmanı bağımsız LLM varmış gibi davranmaz; bağlantı gereksinimini söyler.
