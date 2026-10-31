# JARVIS Hızlı Başlangıç

Bu rehber Windows masaüstü JARVIS çekirdeği içindir. Android uygulamasının kurulumu `JARVIS_ANDROID/README.md` dosyasında anlatılır.

## 1. Windows'ta kaynak kodundan çalıştırma

Gereksinimler: Windows 10/11 x64, Python 3.11 x64, mikrofon ve ses çıkışı. Yerel yapay zekâ için Ollama ve en az bir model gerekir. Bulut sağlayıcıları API anahtarı ve internet bağlantısı ister.

Komut İstemi'ni `JARVIS_HOST` klasöründe açın:

```bat
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy config\config.example.json config\config.json
```

`config\config.json` dosyasını düzenleyin. API anahtarlarını arayüzdeki **YAPAY ZEKÂ** ayarlarından girin; kaynak koda veya GitHub deposuna yazmayın.

Başlatmak için:

```bat
run_jarvis.bat
```

Alternatif çalışma kipleri:

```bat
python main.py --mode cli
python main.py --no-voice
python main.py --command "Stagepulse ana sitesini aç"
```

## 2. Tek dosya Windows EXE

Python 3.11 x64 kurulu Windows bilgisayarda `BUILD_JARVIS_EXE.bat` dosyasını çalıştırın. Betik proje klasörüne göre konumlanır, sanal ortamı oluşturur ve `dist\StagepulseJARVIS.exe` çıktısını doğrular. EXE derlemesi Windows ortamında yapılmalıdır.

## 3. Yapay zekâ sağlayıcıları

- **Ollama:** Yerel model; Ollama hizmeti ve model bilgisayarda kurulu olmalıdır.
- **Gemini, OpenAI, Grok/xAI, Anthropic, DeepSeek, Perplexity, Groq ve OpenRouter:** API anahtarı ve internet bağlantısı gerektirir.
- **Özel sağlayıcı:** OpenAI Chat Completions uyumlu uç nokta girilebilir.
- **AUTO:** Önce yerel Ollama'yı dener; başarısızsa yapılandırılmış yedek sağlayıcılara geçer.

API anahtarları Windows DPAPI korumasıyla saklanır. Şifreleme başarısız olursa anahtar düz metin olarak kaydedilmez.

## 4. Sesli kullanım

Arayüzde **Sesli kontrol** ve **Sürekli dinle** anahtarlarını kullanın. Mikrofon iznini ve varsayılan Windows kayıt aygıtını kontrol edin. Varsayılan konuşma tanıma hizmeti internet isteyebilir. Yerel TTS veya yerel Ollama, konuşma tanımanın da çevrimdışı olduğu anlamına gelmez.

## 5. Android bağlantısı

1. Windows JARVIS'i açın.
2. **ANDROID BAĞLANTISI** düğmesini etkinleştirin ve özel ağ uyarısını onaylayın.
3. Gösterilen IP adresi ve `8765` portunu Android uygulamasındaki HOST alanına girin.
4. Erişim token'ını Windows uygulamasından kopyalayıp Android ayarlarına yapıştırın.
5. Telefon ve bilgisayar aynı güvenilir yerel Wi-Fi ağında olmalıdır. TCP 8765 portunu internete açmayın.

## 6. Stagepulse ve GitHub

JARVIS web araması, bağlı yerel Git deposu üzerinde durum/karşılaştırma/commit/push/pull işlemleri ve Stagepulse sayfalarına yönlendirme desteği sunar. Depoda değişiklik yapmadan önce doğru klasörün bağlandığını kontrol edin. Git kimlik doğrulaması Windows Git Credential Manager veya SSH üzerinden yapılır. Oturum gerektiren yönetim sayfalarında kullanıcı girişi kullanıcı tarafından tamamlanmalıdır.

## 7. Sorun giderme

- Mikrofon görünmüyorsa Windows Gizlilik > Mikrofon erişimini ve varsayılan kayıt aygıtını kontrol edin.
- Sürekli dinleme başlamıyorsa Sesli kontrol anahtarını ve mikrofon testini kontrol edin.
- Ollama yanıt vermiyorsa hizmeti, `http://127.0.0.1:11434` adresini ve modelin kurulu olduğunu doğrulayın.
- API isteği başarısızsa sağlayıcı, model adı, API anahtarı ve kota durumunu kontrol edin.
- Android bağlanmıyorsa aynı Wi-Fi, doğru IP/token ve Windows Güvenlik Duvarı'nda özel ağ TCP 8765 iznini kontrol edin.
- Ayrıntılı günlükler kullanıcı günlük klasöründe tutulur.

Gerçek mikrofon, hoparlör, telefon bağlantısı ve güncelleme davranışı fiziksel cihaz üzerinde ayrıca doğrulanmalıdır.