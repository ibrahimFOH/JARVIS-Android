import base64
import html
import json
import os
import re
import requests
from pathli    def __init__(self):
        self.session = requests.Session()
        self.host = "http://127.0.0.1:11434"
        self.model = "qwen3:0.6b"
        self.timeout = 18
        self.web_timeout = 5
        self.settings_path = self._settings_file()
        saved = self._read_settings()

        legacy_ai = {}
        try:
            from utils.config_manager import get_config
            legacy_ai = get_config().get("ai", {}) or {}
        except Exception:
            pass
        if not isinstance(legacy_ai, dict):
            legacy_ai = {}
        legacy_providers = legacy_ai.get("providers", {})
        if not isinstance(legacy_providers, dict):
            legacy_providers = {}

        def legacy_value(name, field, default=""):
            item = legacy_providers.get(name, {})
            return item.get(field, default) if isinstance(item, dict) else default

        self.host = os.environ.get(
            "OLLAMA_HOST", saved.get("ollama_host", legacy_ai.get("ollama_url", self.host))
        ).rstrip("/")
        self.model = os.environ.get(
            "OLLAMA_MODEL", saved.get("ollama_model", legacy_ai.get("ollama_model", self.model))
        )
        self.gemini_model = os.environ.get(
            "GEMINI_MODEL",
            saved.get("gemini_model", legacy_value("gemini", "model", "gemini-2.5-flash"))
        )
        self.gemini_image_model = os.environ.get(
            "GEMINI_IMAGE_MODEL", saved.get("gemini_image_model", "gemini-2.5-flash-image")
        )
        self.gemini_key = os.environ.get(
            "GEMINI_API_KEY",
            self._unprotect_key(saved.get("gemini_api_key", legacy_value("gemini", "api_key", "")))
        ).strip()
        self.groq_key = os.environ.get(
            "GROQ_API_KEY",
            self._unprotect_key(saved.get("groq_api_key", legacy_value("groq", "api_key", "")))
        ).strip()
        self.groq_model = os.environ.get(
            "GROQ_MODEL", saved.get("groq_model", legacy_value("groq", "model", "openai/gpt-oss-20b"))
        )
        self.api_defaults = {
            "openai": ("https://api.openai.com/v1", "gpt-4.1-mini"),
            "grok": ("https://api.x.ai/v1", "grok-4.7"),
            "anthropic": ("https://api.anthropic.com/v1", "claude-sonnet-5"),
            "deepseek": ("https://api.deepseek.com", "deepseek-flash"),
            "perplexity": ("https://api.perplexity.ai", "sonar"),
            "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-4.1-mini"),
            "custom": ("https://api.openai.com/v1", "model-name"),
        }
        self.api_keys = {
            str(k).lower(): self._unprotect_key(v)
            for k, v in saved.get("api_keys", {}).items()
        } if isinstance(saved.get("api_keys", {}), dict) else {}
        self.api_models = dict(saved.get("api_models", {})) if isinstance(saved.get("api_models", {}), dict) else {}
        self.api_base_urls = dict(saved.get("api_base_urls", {})) if isinstance(saved.get("api_base_urls", {}), dict) else {}

        for name in self.api_defaults:
            old_key = legacy_value(name, "api_key", "")
            old_model = legacy_value(name, "model", "")
            old_url = legacy_value(name, "base_url", "")
            if name == "custom" and not old_url:
                old_url = legacy_ai.get("custom_base_url", "")
            if old_key and name not in self.api_keys:
                self.api_keys[name] = self._unprotect_key(old_key)
            if old_model and name not in self.api_models:
                self.api_models[name] = str(old_model)
            if old_url and name not in self.api_base_urls:
                url = str(old_url).strip().rstrip("/")
                for suffix in ("/chat/completions", "/messages"):
                    if url.endswith(suffix):
                        url = url[:-len(suffix)]
                        break
                self.api_base_urls[name] = url

        env_names = {
            "openai": "OPENAI_API_KEY", "grok": "XAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
            "perplexity": "PERPLEXITY_API_KEY", "openrouter": "OPENROUTER_API_KEY",
            "custom": "CUSTOM_API_KEY",
        }
        for name, env_name in env_names.items():
            if os.environ.get(env_name):
                self.api_keys[name] = os.environ[env_name].strip()

        self.provider = str(
            saved.get("provider", os.environ.get("JARVIS_AI_PROVIDER", legacy_ai.get("provider", "ollama")))
        ).strip().lower()
        if self.provider == "ollama_only":
            self.provider = "ollama"
        if self.provider not in ("auto", "gemini", "groq", "ollama", *self.api_defaults.keys()):
            self.provider = "ollama"

    @staticmethod
    def _settings_file():
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        return base / "StagepulseJARVIS" / "ai_settings.json"

    def _read_settings(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    @staticmethod
    def _protect_key(secret):
        if not secret:
            return {"plain": ""}
        try:
            import win32crypt
            encrypted = win32crypt.CryptProtectData(
                secret.encode("utf-8"), "Stagepulse JARVIS API Key",
                None, None, None, 0
            )[1]
            return {"dpapi": base64.b64encode(encrypted).decode("ascii")}
        except Exception:
            return {"plain": secret}

    @staticmethod
    def _unprotect_key(value):
        if isinstance(value, str):
            return value
        if not isinstance(value, dict):
            return ""
        if "dpapi" in value:
            try:
                import win32crypt
                encrypted = base64.b64decode(value["dpapi"])
                return win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode("utf-8")
            except Exception:
                return ""
        return str(value.get("plain", ""))

    def configure(self, provider=None, gemini_key=None, gemini_model=None,
                  gemini_image_model=None, ollama_host=None, ollama_model=None,
                  groq_key=None, groq_model=None, api_keys=None, api_models=None,
                  api_base_urls=None):
        valid = ("auto", "gemini", "groq", "ollama", *self.api_defaults.keys())
        if provider is not None:
            requested = str(provider).strip().lower()
            if requested not in valid:
                raise ValueError("Desteklenmeyen AI sağlayıcısı: " + requested)
            self.provider = requested
        if api_keys is not None:
            self.api_keys.update({
                str(k).lower(): str(v).strip()
                for k, v in api_keys.items() if str(k).lower() in self.api_defaults
            })
        if api_models is not None:
            self.api_models.update({
                str(k).lower(): str(v).strip()
                for k, v in api_models.items()
                if str(k).lower() in self.api_defaults and str(v).strip()
            })
        if api_base_urls is not None:
            self.api_base_urls.update({
                str(k).lower(): str(v).strip().rstrip("/")
                for k, v in api_base_urls.items()
                if str(k).lower() in self.api_defaults and str(v).strip()
            })
        if gemini_key is not None:
            self.gemini_key = gemini_key.strip()
        if gemini_model is not None and gemini_model.strip():
            self.gemini_model = gemini_model.strip()
        if gemini_image_model is not None and gemini_image_model.strip():
            self.gemini_image_model = gemini_image_model.strip()
        if groq_key is not None:
            self.groq_key = groq_key.strip()
        if groq_model is not None and groq_model.strip():
            self.groq_model = groq_model.strip()
        if ollama_host is not None and ollama_host.strip():
            self.host = ollama_host.strip().rstrip("/")
        if ollama_model is not None and ollama_model.strip():
            self.model = ollama_model.strip()

        values = {
            "provider": self.provider,
            "gemini_api_key": self._protect_key(self.gemini_key),
            "gemini_model": self.gemini_model,
            "gemini_image_model": self.gemini_image_model,
            "groq_api_key": self._protect_key(self.groq_key),
            "groq_model": self.groq_model,
            "ollama_host": self.host,
            "ollama_model": self.model,
            "api_keys": {k: self._protect_key(v) for k, v in self.api_keys.items()},
            "api_models": self.api_models,
            "api_base_urls": self.api_base_urls,
        }
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.settings_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temp_path), str(self.settings_path))

    def _compatible_api(self, provider, prompt, context=""):
        key = self.api_keys.get(provider, "")
        base_url, default_model = self.api_defaults[provider]
        base_url = self.api_base_urls.get(provider, base_url).rstrip("/")
        if not key:
            raise RuntimeError(provider.upper() + " API anahtarı boş. AI SETTINGS bölümünden ekleyin.")
        model = self.api_models.get(provider, default_model)
        content = prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")
        if provider == "anthropic":
            response = self.session.post(
                base_url + "/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model, "max_tokens": 1024,
                    "system": "Sen JARVIS'sin. Daima Türkçe yanıt ver; kısa, doğrudan ve işe yarar ol. Bilmediğin bilgiyi uydurma.",
                    "messages": [{"role": "user", "content": content}],
                },
                timeout=min(self.timeout, 60),
            )
        else:
            response = self.session.post(
                base_url + "/chat/completions",
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                json={
                    "model": model, "stream": False, "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": "Sen JARVIS'sin. Daima Türkçe yanıt ver; kısa, doğrudan ve işe yarar ol. Bilmediğin bilgiyi uydurma."},
                        {"role": "user", "content": content},
                    ],
                },
                timeout=min(self.timeout, 60),
            )
        if not response.ok:
            try:
                detail = response.json().get("error", {}).get("message", response.text[:300])
            except (ValueError, AttributeError):
                detail = response.text[:300]
            raise RuntimeError("{} API HTTP {}: {}".format(provider.upper(), response.status_code, detail))
        data = response.json()
        if provider == "anthropic":
            blocks = data.get("content") or []
            answer = " ".join(
                str(block.get("text", "")) for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError(provider.upper() + " boş yanıt döndürdü.")
            answer = (choices[0].get("message") or {}).get("content", "")
            if isinstance(answer, list):
                answer = " ".join(x.get("text", "") for x in answer if isinstance(x, dict))
        answer = str(answer or "").strip()
        if not answer:
            raise RuntimeError(provider.upper() + " metin yanıtı döndürmedi.")
        return answer

    def _gemini_api(self, prompt, context=""):
        if not self.gemini_key:
            raise RuntimeError("Gemini API anahtarı boş. AI SETTINGS bölümünden ekleyin.")
        content = prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + self.gemini_model + ":generateContent"
        response = self.session.post(
            url, params={"key": self.gemini_key},
            json={
                "systemInstruction": {"parts": [{"text": "Sen JARVIS'sin. Daima Türkçe yanıt ver. Kısa, doğrudan ve işe yarar ol."}]},
                "contents": [{"role": "user", "parts": [{"text": content}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
            },
            timeout=min(self.timeout, 60),
        )
        if not response.ok:
            raise RuntimeError("Gemini API HTTP {}: {}".format(response.status_code, response.text[:300]))
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini boş yanıt döndürdü.")
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        answer = " ".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))
        if not answer.strip():
            raise RuntimeError("Gemini metin yanıtı döndürmedi.")
        return answer.strip()

    def test_provider(self, provider=None):
        target = (provider or self.provider).strip().lower()
        try:
            if target == "auto":
                answer = self.ask("Sadece 'Bağlantı başarılı' yaz.")
                return {"success": bool(answer and not answer.startswith("Yapay zekâ yanıtı alınamadı.")), "message": (answer or "Otomatik sağlayıcı yanıt vermedi.")[:1500]}
            if target == "ollama":
                response = self.session.get(self.host + "/api/tags", timeout=8)
                response.raise_for_status()
                names = [x.get("name", "") for x in response.json().get("models", [])]
                if not names:
                    return {"success": False, "message": "Ollama erişilebilir ancak model yüklü değil. CMD'de ollama pull " + self.model + " çalıştırın."}
                if not any(name == self.model or name.startswith(self.model + ":") for name in names):
                    return {"success": False, "message": "Ollama modeli bulunamadı: " + self.model + ". Yüklü modeller: " + ", ".join(names)}
                return {"success": True, "message": "Ollama bağlantısı başarılı: " + self.model}
            if target == "gemini":
                answer = self._gemini_api("Sadece 'Bağlantı başarılı' yaz.")
            elif target == "groq":
                if not self.groq_key:
                    raise RuntimeError("Groq API anahtarı boş. AI SETTINGS bölümünden ekleyin.")
                response = self.session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": "Bearer " + self.groq_key, "Content-Type": "application/json"},
                    json={"model": self.groq_model, "stream": False,
                          "messages": [{"role": "user", "content": "Sadece 'Bağlantı başarılı' yaz."}]},
                    timeout=min(self.timeout, 30),
                )
                if not response.ok:
                    raise RuntimeError("Groq API HTTP {}: {}".format(response.status_code, response.text[:300]))
                choices = response.json().get("choices") or []
                answer = (choices[0].get("message") or {}).get("content", "") if choices else ""
                if not str(answer).strip():
                    raise RuntimeError("Groq boş yanıt döndürdü.")
            elif target in self.api_defaults:
                answer = self._compatible_api(target, "Sadece 'Bağlantı başarılı' yaz.")
            else:
                return {"success": False, "message": "Seçilen sağlayıcı desteklenmiyor."}
            return {"success": bool(answer), "message": target.upper() + " API yanıt verdi: " + answer[:800]}
        except Exception as exc:
            return {"success": False, "message": target.upper() + " bağlantı hatası: " + str(exc)}

n3:0.6b"
        self.timeout=18
        self.web_timeout=5

    def _instant(self,text):
        t=(text or "").strip().lower()
        profile_questions = (
            "ben kimim", "beni tanıyor musun", "beni taniyor musun",
            "hakkımda ne biliyorsun", "hakkimda ne biliyorsun",
            "kendimi tanıt", "kendimi tanit", "profilimi anlat",
            "beni anlat", "benim hakkımda anlat", "benim hakkimda anlat",
            "patron kim", "ibrahim kavasoğlu kim", "ibrahim kavasoglu kim",
        )
        if any(x in t for x in profile_questions):
            return ("Sen İbrahim Kavasoğlu'sun; ses mühendisi ve tonmaister, Hatay/Antakya odaklı "
                    "Stagepulse'un kurucusu ve yürütücüsüsün. Canlı ses, FOH/monitör, RF, IEM, "
                    "Dante, SPL/akustik, sistem tasarımı ve stüdyo işlerinde deneyimlisin. "
                    "Stagepulse için ses, ışık, LED, etkinlik organizasyonu, eğitim ve yazılım "
                    "projeleri geliştiriyorsun. Türkçe yanıt, siyah-altın-beyaz marka görünümü, "
                    "hafif ve çevrimdışı çalışabilen yazılımlar ve test edilmeden tamamlandı "
                    "denmemesi önceliklerin arasında.")
        if any(x in t for x in ("kimsin","sen kimsin","adın ne","ismin ne")):
            return "Ben JARVIS'im, Patron. Türkçe çalışan ve Stagepulse iş akışlarına göre yapılandırılmış asistanınım."
        if any(x in t for x in ("ne yapabilirsin","neler yapabilirsin","yeteneklerin")):
            return "Komutları yönlendirebilir, Ollama ile yanıt üretebilir, webden araştırabilir ve bağlı güvenli araçları kullanabilirim."
        if t in ("merhaba","selam","günaydın","iyi akşamlar","iyi geceler"):
            return "Hazırım Patron."
        return None

    def _needs_web(self,text):
        t=(text or "").lower()
        return any(x in t for x in ("internetten","internette","webde","web'de","araştır","güncel","şu an","bugün","son haber","haberler","fiyat","site","github","youtube","instagram","stagepulse.com","http://","https://"))

    def _clean(self,raw):
        raw=re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>"," ",raw)
        raw=re.sub(r"(?is)<[^>]+>"," ",raw)
        return re.sub(r"\s+"," ",html.unescape(raw)).strip()

    def _web(self,query):
        urls=re.findall(r"https?://[^\s]+",query or "")
        if urls:
            try:
                r=requests.get(urls[0].rstrip(".,)"),timeout=self.web_timeout,headers={"User-Agent":"Mozilla/5.0 JARVIS/1.0"})
                if r.ok: return self._clean(r.text)[:5000]
            except Exception: pass
        for engine in ("https://www.google.com/search?q=","https://www.bing.com/search?q=","https://html.duckduckgo.com/html/?q="):
            try:
                r=requests.get(engine+quote(query),timeout=self.web_timeout,headers={"User-Agent":"Mozilla/5.0 JARVIS/1.0"})
                if r.ok:
                    text=self._clean(r.text)
                    if len(text)>200: return text[:5000]
            except Exception: pass
        return ""

    def _ollama(self,prompt,context=""):
        system_prompt = """Sen JARVIS'sin. Her zaman Türkçe konuş; kısa, doğrudan ve işe yarar ol.
KULLANICI PROFİLİ (kalıcı çalışma bağlamı):
- Kullanıcının adı İbrahim Kavasoğlu; hitap tercihi Patron. Mesleki unvanı: SES MÜHENDİSİ | TONMAİSTER. Hataylı; Hatay/Antakya odaklı çalışır.
- Deneyim geçmişi: Özal Ses Sistemleri (teknik çalışan, 2019-2021), İnArt Müzik Stüdyosu (teknik sorumlu/tonmaister, 2019-2023), Nil Müzik (teknik sorumlu, 2023-2025), Rixos Premium Belek/Antalya (2025-2026).
- Uzmanlıkları: canlı ses, FOH, monitör, sahne sistemi kurulumları, IEM, RF sistemleri, Dante, soundcheck, rider/patch/routing, mikrofon seçimi, line array, ışık, teknik ekip koordinasyonu, konser/etkinlik teknik sorumluluğu, kayıt, miks ve mastering; SPL ölçümü, akustik, kapsama analizi ve sistem tasarımı. Shure sertifikası CV'de belirtilmiş.
- Deneyim geçmişi: Özal Ses Sistemleri (teknik çalışan, 2019-2021), İnArt Müzik Stüdyosu (teknik sorumlu/tonmaister, 2019-2023), Nil Müzik (teknik sorumlu, 2023-2025), Rixos Premium Belek/Antalya (2025-2026). CV unvanı "SES MÜHENDİSİ | TONMAİSTER". Türkçe ana dil; Arapça yabancı dil olarak belirtilmiş. Yanıtlarda Türkçe kullan; sektör terimlerini gerektiğinde İngilizce parantezle açıkla.
- Ekipman/yazılım: Midas M32 Live tercih edilen ana konsoldur; ayrıca Behringer X32, Yamaha CL5, Allen & Heath Avantis, Soundcraft Si Impact, Logic Pro ve Reaper ile çalışır/ilgilenir. Uygun içeriklerde M32'yi öne al; X32'yi ancak açıkça gerekliyse veya kullanıcı isterse ana tercih yap.
- Stagepulse: stagepulse.com.tr; Hatay/Antakya odaklı ses sistemi, ışık ve LED kiralama, organizasyon, FOH mühendisliği, SPL/akustik hizmetleri, uygulamalı dijital ses konsolu eğitimi ve yazılım projeleri. Marka görünümü siyah, altın ve beyaz; cyan/turkuaz varsayma. Logo, yazı tipi ve renkleri gerektiğinde resmî siteden doğrula. Yerel SEO ve tanıtımlarda Hatay odağı korunmalı; kullanıcı Antalya/İstanbul şehir sayfalarını kaldırmak istemişti. İlanlarda otel işlerini öne çıkarmak yerine ses/ışık firmaları, organizasyon şirketleri, sanatçılar ve menajerlere yönelik kurumsal iletişim tercih edilir.
- Rider/sistem tercihleri: aktif PA/line-array tercih edilir, pasif sistem varsayma. Ana konsol Midas M32 Live; önceki taleplerde 4+4 line-array modülü, iki çift 18 inç sub, iki tek 18 inç monitör sub, altı monitör, iki Shure PSM300, iki ULX-D4 ve dört Behringer P2 istenmişti. Tam davul seti yerine yalnızca davul mikrofonları; XLR bağlantısı 3 pin. Belirli projelerde marka/bütçe/adet şartlarını yeniden sor veya doğrula.
- Geçmiş mühendislik projesi: Hatay Serinyol'daki Elif Kır Bahçesi için açık hava, yaklaşık 500-600 kişilik düğün bahçesi; çevredeki evlere ses taşmasını sınırlama önceliği. Eski öneride RCF NX 985-A x2, Turbosound M18B x2, Turbosound Milan M15 monitör x6, Midas M32 Live, dbx DriveRack PA2 x2, dbx RTA-M ve Behringer DI100 x4 bulunuyordu. Eski fiyatı güncelmiş gibi verme; bütçe, fiyat ve kapsama hesabını tekrar doğrula. Monitörleri SPL hesabına dahil etmediği uyarısını hatırla.
- Eğitim dokümanları: Türkçe, kapsamlı, profesyonel; İngilizce sektör terimleri parantez içinde; öğretmen kılavuzu, laboratuvar uygulamaları, değerlendirme anahtarı ve doğrulanabilir EBU R128/AES referansları istenir. Canlı ses mikseri kullanım eğitimi gibi belirli kurslarda kapsam dışına çıkma. Nihai ders/rider materyallerinde Midas M32 tercihine uy.
- Projeler: JARVIS (Türkçe Windows/Android, Ollama qwen3:0.6b ve Android LAN bridge), StageMix, OpenFader ve Stagepulse Plot. StageMix canlı miks kontrol arayüzü, OpenFader X32 OSC protokol denemesi, Stagepulse Plot sahne çizimi projesidir. Proje durumu, derleme ve cihaz uyumluluğunu kaynak/son testlerden doğrulamadan kesin söyleme.
- Bilgisayar bağlamı: Windows 10, Intel Pentium N3710, 4 GB RAM ve SSD; önerileri düşük RAM/CPU tüketimine göre ver. Gerektiğinde kullanıcının elindeki düşük donanımlı Linux makineyi araştırma/test için değerlendirebilirsin.
- Çalışma tercihleri: önce mevcut dosyaları/akışı incele; gereksiz dosya veya özellik ekleme; mevcut dosyayı düzenle, bozuk/tekrarlı kodu gerekirse temizle. İşlemleri /research yaklaşımıyla araştır, testleri çalıştır ve yeşil sonuç görmeden tamamlandı deme. Yapamayacağın işi yapılmış gibi gösterme; kullanıcıya yalnızca gereken durumlarda bilgi ver.
- Stagepulse eğitim ve teknik belgeleri kapsamlı, profesyonel ve doğrulanabilir olmalı; standart/ölçüm değerleri uydurulmamalı. Kullanıcı sade, işe yarar sonuç ister.
- Site komutları: "Stagepulse.com.tr aç" = herkese açık ana sayfa; "benim sitemi aç" / "admin panelini aç" = https://stagepulse.com.tr/admin/; "personel aç" = https://stagepulse.com.tr/portal/; "siteyi aç" = herkese açık ana sayfa. Açıkça belirtilen tam alan adı genel site komutundan önceliklidir.
- Bu profil kişiye özel bağlamdır. Başka biri kullandığında İbrahim olduğunu varsayma; mümkünse oturum/profil seçimine göre davran. Parola, erişim anahtarı ve özel sırları profilde saklama.
"""
        payload={"model":self.model,"stream":False,"keep_alive":"30m","think":False,"options":{"temperature":0.1,"num_predict":180,"num_ctx":4096},"messages":[{"role":"system","content":system_prompt},{"role":"user","content":prompt+(("\n\nWEB VERİSİ:\n"+context) if context else "")}]}
        try:
            r=requests.post(self.host+"/api/chat",json=payload,timeout=self.timeout)
            r.raise_for_status()
            return ((r.json().get("message") or {}).get("content") or "").strip()
        except Exception as e:
            return "Ollama bağlantısında sorun oluştu: "+str(e)

    def ask(self, prompt):
        instant = self._instant(prompt)
        if instant:
            return instant
        needs_web = self._needs_web(prompt)
        context = self._web(prompt) if needs_web else ""
        if self.provider == "auto":
            configured = [name for name in ("groq", "gemini", "openai", "grok", "anthropic", "deepseek", "perplexity", "openrouter", "custom") if (self.groq_key if name == "groq" else self.gemini_key if name == "gemini" else self.api_keys.get(name))]
            order = configured + ["ollama"]
        else:
            order = [self.provider]
        errors = []
        for provider in order:
            try:
                if provider == "ollama":
                    return self._ollama(prompt, context)
                if provider == "gemini":
                    return self._gemini_api(prompt, context)
                if provider == "groq":
                    key = self.groq_key
                    if not key:
                        raise RuntimeError("Groq API anahtarı boş. AI SETTINGS bölümünden ekleyin.")
                    response = self.session.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                        json={"model": self.groq_model, "stream": False, "temperature": 0.2,
                              "messages": [
                                  {"role": "system", "content": "Sen JARVIS'sin. Daima Türkçe yanıt ver; kısa, doğrudan ve işe yarar ol."},
                                  {"role": "user", "content": prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")},
                              ]},
                        timeout=min(self.timeout, 60),
                    )
                    if not response.ok:
                        raise RuntimeError("Groq API HTTP {}: {}".format(response.status_code, response.text[:300]))
                    answer = ((response.json().get("choices") or [{}])[0].get("message") or {}).get("content", "")
                    if not str(answer).strip():
                        raise RuntimeError("Groq boş yanıt döndürdü.")
                    return str(answer).strip()
                if provider in self.api_defaults:
                    return self._compatible_api(provider, prompt, context)
                return "Bilinmeyen JARVIS AI sağlayıcısı: " + provider
            except Exception as exc:
                errors.append("{}: {}".format(provider.upper(), exc))
                if self.provider != "auto":
                    break
        if self.provider == "ollama":
            return "Ollama bağlantısında sorun oluştu. Ollama servisinin çalıştığını ve modelin yüklü olduğunu kontrol et."
        return "Yapay zekâ yanıtı alınamadı. " + " | ".join(errors)

    respond = ask
    generate=ask
    process=ask
