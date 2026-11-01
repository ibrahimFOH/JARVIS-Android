import base64
import json
import os
import re
import html
import logging
import copy
import requests
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)


class AIBrain:
    """Yalnızca ücretsiz katmanları ve yerel modeli kullanır."""

    FREE_PROVIDERS = frozenset({"auto", "ollama", "gemini", "groq"})
    FREE_MODELS = {
        "gemini": "gemini-3.8-flash",
        "groq": "openai/gpt-oss-20b",
    }

    def __init__(self):
        self.session = requests.Session()
        self.host = "http://127.0.0.1:11434"
        self.model = "qwen3:0.6b"
        self.timeout = 18
        self.web_timeout = 5
        self.settings_path = self._settings_file()
        saved = self._read_settings()
        legacy_ai = {}
        legacy_config_manager = None
        try:
            from utils.config_manager import get_config
            legacy_config_manager = get_config()
            legacy_ai = legacy_config_manager.get("ai", {}) or {}
        except Exception:
            pass
        if not isinstance(legacy_ai, dict):
            legacy_ai = {}
        legacy_providers = legacy_ai.get("providers", {})
        if not isinstance(legacy_providers, dict):
            legacy_providers = {}

        def legacy_value(name, field, default=""):
            provider_settings = legacy_providers.get(name, {})
            return provider_settings.get(field, default) if isinstance(provider_settings, dict) else default

        # Ücretli veya fiyatlandırması kullanıcı hesabına bağlı genel sağlayıcılar
        # bu sürümde özellikle etkinleştirilmez. Bulut sağlayıcıları yalnızca
        # kendi ücretsiz plan/katmanlarında kullanılmalıdır.
        self.api_defaults = {}
        self.gemini_key = os.environ.get(
            "GEMINI_API_KEY", self._unprotect_key(saved.get("gemini_api_key", legacy_value("gemini", "api_key", "")))
        ).strip()
        requested_gemini_model = os.environ.get(
            "GEMINI_MODEL", saved.get("gemini_model", legacy_value("gemini", "model", self.FREE_MODELS["gemini"]))
        )
        self.gemini_model = self.FREE_MODELS["gemini"]
        if requested_gemini_model != self.gemini_model:
            logger.warning("Gemini modeli ücretsiz izin listesi dışındaydı; güvenli ücretsiz model seçildi.")
        self.groq_key = os.environ.get(
            "GROQ_API_KEY", self._unprotect_key(saved.get("groq_api_key", legacy_value("groq", "api_key", "")))
        ).strip()
        requested_groq_model = os.environ.get(
            "GROQ_MODEL", saved.get("groq_model", legacy_value("groq", "model", self.FREE_MODELS["groq"]))
        )
        self.groq_model = self.FREE_MODELS["groq"]
        if requested_groq_model != self.groq_model:
            logger.warning("Groq modeli izin listesi dışındaydı; sabit ücretsiz plan modeli seçildi.")
        self.gemini_free_confirmed = bool(saved.get("gemini_free_confirmed", False))
        self.groq_free_confirmed = bool(saved.get("groq_free_confirmed", False))
        self.host = os.environ.get("OLLAMA_HOST", saved.get("ollama_host", legacy_ai.get("ollama_url", self.host))).rstrip("/")
        self.model = os.environ.get("OLLAMA_MODEL", saved.get("ollama_model", legacy_ai.get("ollama_model", self.model)))
        # Önceki sürümlerde kaydedilmiş genel/ücretli sağlayıcı anahtarları
        # yeni çalışma oturumuna alınmaz. Ücretsiz sağlayıcıların kendi anahtar
        # alanları (Gemini/Groq) yukarıda ayrı şekilde okunur.
        self.api_keys = {}
        self.api_models = {}
        self.api_base_urls = {}
        for name in self.api_defaults:
            old_provider = legacy_providers.get(name, {})
            if not isinstance(old_provider, dict):
                continue
            if not self.api_keys.get(name) and old_provider.get("api_key"):
                self.api_keys[name] = self._unprotect_key(old_provider.get("api_key"))
            if name not in self.api_models and old_provider.get("model"):
                self.api_models[name] = str(old_provider["model"])
            old_url = str(old_provider.get("base_url", "") or "").strip().rstrip("/")
            if name not in self.api_base_urls and old_url:
                for suffix in ("/chat/completions", "/messages"):
                    if old_url.endswith(suffix):
                        old_url = old_url[:-len(suffix)]
                        break
                self.api_base_urls[name] = old_url

        # Migrate retired provider aliases in saved settings to current defaults.
        for name, obsolete in {
            "openai": {"gpt-4.1-mini", "gpt-4.1-mini-2025-04-14", "gpt-4.1", "gpt-4.1-2025-04-14"},
            "grok": {"grok-4.1"},
            "anthropic": {"claude-sonnet-4-5"},
            "deepseek": {"deepseek-chat", "deepseek-reasoner"},
            "openrouter": {"openai/gpt-4.1-mini", "openai/gpt-4.1-mini-2025-04-14", "openai/gpt-4.1"},
        }.items():
            if self.api_models.get(name) in obsolete:
                self.api_models[name] = self.api_defaults[name][1]

        self.provider = str(
            saved.get("provider", os.environ.get("JARVIS_AI_PROVIDER", legacy_ai.get("provider", "ollama")))
        ).strip().lower()
        if self.provider not in self.FREE_PROVIDERS:
            logger.warning("Önceki ayarlarda ücretli/desteklenmeyen sağlayıcı bulundu; güvenli yerel Ollama seçildi.")
            self.provider = "ollama"

        # Older releases stored provider API keys as cleartext in ai_settings.json
        # and config.json. Migrate those values to DPAPI before retaining them.
        self._migrate_plaintext_credentials(saved, legacy_ai, legacy_config_manager)
        # Eski sürümlerdeki ücretli sağlayıcı kayıtlarını etkin ayar dosyasından
        # çıkar; API anahtarları hiçbir ücretli uç noktaya gönderilmez.
        if saved.get("api_keys") or saved.get("api_models") or saved.get("api_base_urls") or saved.get("provider") not in self.FREE_PROVIDERS:
            try:
                self._persist_settings()
            except Exception as exc:
                # A DPAPI problem must not make the app fall back to, or call,
                # a legacy paid provider. In-memory allowlisting remains active.
                logger.warning("Eski sağlayıcı ayarları temizlenemedi; bu oturumda yine de devre dışı: %s", exc)

    @staticmethod
    def _settings_file():
        if os.name == "nt":
            root = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        else:
            root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        return root / "StagepulseJARVIS" / "ai_settings.json"

    def _read_settings(self):
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    @staticmethod
    def _protect_key(secret):
        if not secret:
            return {"plain": ""}
        try:
            import win32crypt
            protected_result = win32crypt.CryptProtectData(
                secret.encode("utf-8"), "Stagepulse JARVIS API Key",
                None, None, None, 0
            )
            # PyWin32 versions differ: some return the encrypted bytes directly,
            # others expose a (description, bytes) tuple.
            protected = protected_result[-1] if isinstance(protected_result, tuple) else protected_result
            if not isinstance(protected, (bytes, bytearray, memoryview)):
                raise TypeError("DPAPI şifreli veriyi bytes olarak döndürmedi.")
            return {"dpapi": base64.b64encode(bytes(protected)).decode("ascii")}
        except Exception as exc:
            # Never silently downgrade a credential to cleartext on disk.
            raise RuntimeError(
                "API anahtarı güvenli biçimde şifrelenemedi. Windows DPAPI desteğini kontrol et; "
                "şifreleme olmadan anahtar diske kaydedilmedi."
            ) from exc

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
                result = win32crypt.CryptUnprotectData(
                    encrypted, None, None, None, 0
                )
                plaintext = result[-1] if isinstance(result, tuple) else result
                if isinstance(plaintext, str):
                    return plaintext
                if not isinstance(plaintext, (bytes, bytearray, memoryview)):
                    raise TypeError("DPAPI çözülmüş veriyi bytes olarak döndürmedi.")
                return bytes(plaintext).decode("utf-8")
            except Exception:
                return ""
        return str(value.get("plain", ""))

    @staticmethod
    def _is_plaintext_credential(value):
        if isinstance(value, str):
            return bool(value.strip())
        return isinstance(value, dict) and bool(str(value.get("plain", "")).strip())

    def _migrate_plaintext_credentials(self, saved, legacy_ai, legacy_config_manager):
        saved_plaintext = any(
            self._is_plaintext_credential(saved.get(key))
            for key in ("gemini_api_key", "groq_api_key")
        )
        saved_keys = saved.get("api_keys", {})
        if isinstance(saved_keys, dict):
            saved_plaintext = saved_plaintext or any(
                self._is_plaintext_credential(value) for value in saved_keys.values()
            )

        legacy = legacy_ai if isinstance(legacy_ai, dict) else {}
        legacy_providers = legacy.get("providers", {})
        if not isinstance(legacy_providers, dict):
            legacy_providers = {}
        legacy_plaintext = any(
            isinstance(provider, dict) and self._is_plaintext_credential(provider.get("api_key"))
            for provider in legacy_providers.values()
        )
        if not saved_plaintext and not legacy_plaintext:
            return

        try:
            # Prepare migrated legacy values before writing anything. If DPAPI
            # is unavailable, leave both original files untouched.
            migrated_providers = copy.deepcopy(legacy_providers)
            for name, settings in migrated_providers.items():
                if not isinstance(settings, dict):
                    continue
                raw = settings.get("api_key")
                if self._is_plaintext_credential(raw):
                    secret = self._unprotect_key(raw)
                    settings["api_key"] = self._protect_key(secret) if secret else {"plain": ""}
            self._persist_settings()
        except Exception as exc:
            logger.warning("Eski API anahtarı şifrelenemedi; kaynak yapılandırma korunuyor: %s", exc)
            return

        if legacy_plaintext and legacy_config_manager is not None:
            try:
                # Keep the same keys available to this version, but only as
                # DPAPI envelopes, so an interrupted migration won't lose them.
                saved_ok = legacy_config_manager.set("ai.providers", migrated_providers)
                if saved_ok is False:
                    logger.warning("API anahtarları ai_settings.json dosyasına taşındı ancak eski config.json temizlenemedi.")
            except Exception as exc:
                logger.warning("Eski config.json içindeki API anahtarları şifrelenemedi: %s", exc)

    def _persist_settings(self):
        payload = {
            "provider": self.provider,
            "gemini_free_confirmed": bool(self.gemini_free_confirmed),
            "groq_free_confirmed": bool(self.groq_free_confirmed),
            "gemini_api_key": self._protect_key(self.gemini_key),
            "gemini_model": self.gemini_model,
            "groq_api_key": self._protect_key(self.groq_key),
            "groq_model": self.groq_model,
            "ollama_host": self.host,
            "ollama_model": self.model,
            "api_keys": {k: self._protect_key(v) for k, v in self.api_keys.items()},
            "api_models": self.api_models,
            "api_base_urls": self.api_base_urls,
        }
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.settings_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(self.settings_path))

    def configure(self, provider=None, gemini_key=None, gemini_model=None,
                  ollama_host=None, ollama_model=None,
                  groq_key=None, groq_model=None, api_keys=None, api_models=None,
                  api_base_urls=None, gemini_free_confirmed=None,
                  groq_free_confirmed=None):
        if provider is not None:
            value = str(provider).strip().lower()
            if value not in self.FREE_PROVIDERS:
                raise ValueError(
                    "Bu JARVIS sürümünde yalnızca ücretsiz sağlayıcılar kullanılabilir: "
                    "Ollama, Gemini ücretsiz katmanı ve Groq Free Plan."
                )
            self.provider = value
        if gemini_key is not None:
            self.gemini_key = gemini_key.strip()
        if gemini_model and gemini_model.strip() != self.FREE_MODELS["gemini"]:
            raise ValueError("Yalnızca izin verilen ücretsiz Gemini Flash modeli kullanılabilir.")
        self.gemini_model = self.FREE_MODELS["gemini"]
        if groq_key is not None:
            self.groq_key = groq_key.strip()
        if groq_model and groq_model.strip() != self.FREE_MODELS["groq"]:
            raise ValueError("Yalnızca izin verilen Groq Free Plan modeli kullanılabilir.")
        self.groq_model = self.FREE_MODELS["groq"]
        if gemini_free_confirmed is not None:
            self.gemini_free_confirmed = bool(gemini_free_confirmed)
        if groq_free_confirmed is not None:
            self.groq_free_confirmed = bool(groq_free_confirmed)
        if ollama_host and ollama_host.strip():
            self.host = ollama_host.strip().rstrip("/")
        if ollama_model and ollama_model.strip():
            self.model = ollama_model.strip()
        if isinstance(api_keys, dict):
            for key, value in api_keys.items():
                name = str(key).lower()
                if name in self.api_defaults:
                    self.api_keys[name] = str(value).strip()
        if isinstance(api_models, dict):
            for key, value in api_models.items():
                name = str(key).lower()
                if name in self.api_defaults and str(value).strip():
                    self.api_models[name] = str(value).strip()
        if isinstance(api_base_urls, dict):
            for key, value in api_base_urls.items():
                name = str(key).lower()
                if name in self.api_defaults and str(value).strip():
                    self.api_base_urls[name] = str(value).strip().rstrip("/")
        self._persist_settings()

    def _compatible_api(self, provider, prompt, context=""):
        """Genel/ücretli API uç noktalarına ağ isteği gönderilmesini engeller."""
        raise RuntimeError(
            "Genel/ücretli API uç noktaları devre dışı. Yalnızca Ollama, "
            "ücretsiz katmanı onaylanmış Gemini ve Groq Free Plan kullanılabilir."
        )

    @staticmethod
    def _output_token_limit(value=None, default=1200):
        try:
            requested = int(value) if value is not None else int(default)
        except (TypeError, ValueError):
            requested = int(default)
        return max(64, min(requested, 4096))

    def _gemini_api(self, prompt, context="", max_output_tokens=None):
        if not self.gemini_free_confirmed:
            raise RuntimeError("Gemini isteği engellendi: ücretsiz katman ve faturalandırmanın kapalı olduğu onaylanmalı.")
        if self.gemini_model != self.FREE_MODELS["gemini"]:
            raise RuntimeError("Gemini model izin listesi dışındaki istek engellendi.")
        if not self.gemini_key:
            raise RuntimeError("Gemini API anahtarı boş. AI PROVIDER ayarlarından ekleyin.")
        user_text = prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + self.gemini_model + ":generateContent"
        response = self.session.post(
            url, params={"key": self.gemini_key},
            json={
                "systemInstruction": {"parts": [{"text": "Sen JARVIS'sin. Daima Türkçe yanıt ver."}]},
                "contents": [{"role": "user", "parts": [{"text": user_text}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": self._output_token_limit(max_output_tokens, 1200),
                },
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
        answer = " ".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
        if not answer.strip():
            raise RuntimeError("Gemini metin yanıtı döndürmedi.")
        return answer.strip()

    def ask_with_images(self, prompt, image_paths, max_output_tokens=1200):
        """Analyze local image files only through a confirmed, free Gemini tier."""
        if self.provider not in ("auto", "gemini"):
            raise RuntimeError(
                "Görsel analizi için yalnızca ücretsiz katmanı onaylanmış Gemini bağlantısı kullanılabilir."
            )
        if not self.gemini_free_confirmed:
            raise RuntimeError(
                "Görsel Gemini'ye gönderilmedi. Önce Gemini Free Tier ve faturalandırmanın kapalı olduğunu onayla."
            )
        if self.gemini_model != self.FREE_MODELS["gemini"] or not self.gemini_key:
            raise RuntimeError("Görsel analizi için izinli Gemini modeli ve API anahtarı gerekli.")

        if isinstance(image_paths, (str, os.PathLike)):
            image_paths = [image_paths]
        image_paths = list(image_paths or [])
        if not image_paths or len(image_paths) > 5:
            raise ValueError("En fazla 5 görsel aynı istekte analiz edilebilir.")

        parts = [{"text": str(prompt or "")}]
        total_bytes = 0
        allowed_mimes = {"image/jpeg", "image/png", "image/webp"}
        for raw_path in image_paths:
            path = Path(raw_path).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError("Görsel bulunamadı: " + str(path))
            mime_type, _encoding = mimetypes.guess_type(str(path))
            if mime_type not in allowed_mimes:
                raise ValueError("Yalnızca JPEG, PNG veya WebP görselleri destekleniyor: " + path.name)
            size = path.stat().st_size
            if size <= 0 or size > 8 * 1024 * 1024:
                raise ValueError("Her görsel 8 MB sınırında ve boş olmayan bir dosya olmalı: " + path.name)
            total_bytes += size
            if total_bytes > 15 * 1024 * 1024:
                raise ValueError("Görsellerin toplam boyutu 15 MB sınırını aşıyor.")
            with path.open("rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode("ascii")
            parts.append({"inline_data": {"mime_type": mime_type, "data": encoded}})

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + self.gemini_model + ":generateContent"
        )
        response = self.session.post(
            url,
            params={"key": self.gemini_key},
            json={
                "systemInstruction": {
                    "parts": [{
                        "text": (
                            "Sen JARVIS'sin. Görselde ölçü, çizim, yazı veya ekipman görünmüyorsa "
                            "uydurma. Okunamayan değerleri bilinmiyor olarak işaretle. Daima Türkçe yanıt ver."
                        )
                    }]
                },
                "contents": [{"role": "user", "parts": parts}],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": self._output_token_limit(max_output_tokens, 1200),
                },
            },
            timeout=min(self.timeout, 60),
        )
        if not response.ok:
            raise RuntimeError(
                "Gemini görsel API HTTP {}: {}".format(response.status_code, response.text[:300])
            )
        candidates = response.json().get("candidates") or []
        response_parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        answer = " ".join(
            str(part.get("text", "")) for part in response_parts if isinstance(part, dict)
        ).strip()
        if not answer:
            raise RuntimeError("Gemini görsel analizi boş yanıt döndürdü.")
        return answer

    def test_provider(self, provider=None):
        target = (provider or self.provider).strip().lower()
        if target not in self.FREE_PROVIDERS:
            return {
                "success": False,
                "message": "Ücretli veya izin verilmeyen sağlayıcı engellendi: " + target,
            }
        if target == "gemini" and not self.gemini_free_confirmed:
            return {
                "success": False,
                "message": "Gemini isteği gönderilmedi. Ücretsiz katmanı ve faturalandırmanın kapalı olduğunu onayla.",
            }
        if target == "groq" and not self.groq_free_confirmed:
            return {
                "success": False,
                "message": "Groq isteği gönderilmedi. Free Plan'da olduğunu ve faturalandırmanın kapalı olduğunu onayla.",
            }
        try:
            if target == "auto":
                answer = self.ask("Sadece 'Bağlantı başarılı' yaz.")
                failed_prefixes = (
                    "Yapay zekâ yanıtı alınamadı.",
                    "Ollama bağlantısında sorun",
                    "Ollama yanıt üretilemedi",
                )
                ok = bool(answer and not answer.startswith(failed_prefixes))
                return {"success": ok, "message": answer[:1200]}
            if target == "ollama":
                response = self.session.get(self.host + "/api/tags", timeout=8)
                response.raise_for_status()
                models = [item.get("name", "") for item in response.json().get("models", [])]
                if not models:
                    return {"success": False, "message": "Ollama erişilebilir ancak model listesi boş."}
                if not any(name == self.model or name.startswith(self.model + ":") for name in models):
                    return {"success": False, "message": "Model bulunamadı: " + self.model + ". Yüklü: " + ", ".join(models)}
                return {"success": True, "message": "Ollama bağlantısı başarılı: " + self.model}
            if target == "gemini":
                answer = self._gemini_api("Sadece 'Bağlantı başarılı' yaz.")
            elif target == "groq":
                if not self.groq_key:
                    raise RuntimeError("Groq API anahtarı boş.")
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
            elif target in self.api_defaults:
                answer = self._compatible_api(target, "Sadece 'Bağlantı başarılı' yaz.")
            else:
                return {"success": False, "message": "Seçilen sağlayıcı desteklenmiyor: " + target}
            return {"success": bool(str(answer or "").strip()), "message": target.upper() + " yanıt verdi: " + str(answer)[:900]}
        except Exception as exc:
            return {"success": False, "message": target.upper() + " bağlantı hatası: " + str(exc)}


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
            return ("Kişisel profil bilgileri kaynak koda sabitlenmiyor. Profilini yerel "
                    "ayarlarından veya açıkça kaydettiğin kişisel hafıza kayıtlarından "
                    "sağlamadıkça kimliğin ya da geçmişin hakkında varsayım yapmam.")
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

    def _ollama(self,prompt,context="",max_output_tokens=None):
        system_prompt = """Sen JARVIS'sin. Daima Türkçe ve doğrudan yanıt ver.
Kullanıcı tarafından bu istekte verilen bilgileri esas al. Kaydedilmiş bağlam bulunuyorsa
onu yalnızca ilgili olduğunda kullan; eski bilgileri kesin gerçek sayma. Kaynak, ölçüm,
dosya işlemi, donanım testi veya ağ erişimi gerçekten yapılmadıysa yapılmış gibi söyleme.
Belirsizliği, varsayımları ve doğrulama adımlarını açıkça belirt. Gizli anahtar veya kişisel
profil bilgilerini gereksiz yere yanıta kopyalama."""
        payload={"model":self.model,"stream":False,"keep_alive":"30m","think":False,"options":{"temperature":0.1,"num_predict":self._output_token_limit(max_output_tokens,180),"num_ctx":4096},"messages":[{"role":"system","content":system_prompt},{"role":"user","content":prompt+(("\n\nWEB VERİSİ:\n"+context) if context else "")}]}
        try:
            r=requests.post(self.host+"/api/chat",json=payload,timeout=self.timeout)
            r.raise_for_status()
            return ((r.json().get("message") or {}).get("content") or "").strip()
        except Exception as e:
            return "Ollama bağlantısında sorun oluştu: "+str(e)

    def ask(self, prompt, memory_context="", max_output_tokens=None):
        instant = self._instant(prompt)
        if instant and not memory_context:
            return instant
        # Search only the user's actual request; saved memory must never leak into web queries.
        context = self._web(prompt) if self._needs_web(prompt) else ""
        if memory_context:
            prompt = (
                "KALICI KULLANICI BAĞLAMI (yalnızca isteğe bağlı olarak kaydedilmiş bilgiler; "
                "güncel olmayan bilgileri kesin gerçek sayma):\n" + str(memory_context) +
                "\n\nKULLANICI İSTEĞİ:\n" + str(prompt or "")
            )
        if self.provider not in self.FREE_PROVIDERS:
            return "Ücretli veya izin verilmeyen AI sağlayıcısı güvenlik nedeniyle engellendi."
        available = []
        if self.groq_free_confirmed and self.groq_key:
            available.append("groq")
        if self.gemini_free_confirmed and self.gemini_key:
            available.append("gemini")
        # AUTO yalnızca yerel Ollama ve ücretsiz katmanlarda açıkça yapılandırılmış
        # Gemini/Groq bağlantılarını dener. Kota dolduğunda başka ücretli servise
        # geçmez; istek başarısız olarak raporlanır.
        if self.provider == "auto":
            order = ["ollama"] + available
        else:
            order = [self.provider]
        errors = []
        for selected in dict.fromkeys(order):
            try:
                if selected == "ollama":
                    answer = (
                        self._ollama(prompt, context)
                        if max_output_tokens is None
                        else self._ollama(prompt, context, max_output_tokens=max_output_tokens)
                    )
                    if not answer or answer.startswith("Ollama bağlantısında sorun oluştu:"):
                        raise RuntimeError(answer or "Ollama boş yanıt döndürdü.")
                    return answer
                if selected == "gemini":
                    return (
                        self._gemini_api(prompt, context)
                        if max_output_tokens is None
                        else self._gemini_api(prompt, context, max_output_tokens=max_output_tokens)
                    )
                if selected == "groq":
                    return (
                        self._compatible_groq(prompt, context)
                        if max_output_tokens is None
                        else self._compatible_groq(prompt, context, max_output_tokens=max_output_tokens)
                    )
                if selected in self.api_defaults:
                    return self._compatible_api(selected, prompt, context)
                raise RuntimeError("Bilinmeyen sağlayıcı: " + selected)
            except Exception as exc:
                errors.append(selected.upper() + ": " + str(exc))
        return "Yapay zekâ yanıtı alınamadı. Denenen sağlayıcılar: " + " | ".join(errors)

    def _compatible_groq(self, prompt, context="", max_output_tokens=None):
        if not self.groq_free_confirmed:
            raise RuntimeError("Groq isteği engellendi: hesabın Free Plan üzerinde olduğu onaylanmalı.")
        if self.groq_model != self.FREE_MODELS["groq"]:
            raise RuntimeError("Groq model izin listesi dışındaki istek engellendi.")
        if not self.groq_key:
            raise RuntimeError("Groq Free Plan API anahtarı tanımlı değil.")
        user_text = prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")
        response = self.session.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + self.groq_key, "Content-Type": "application/json"},
            json={
                "model": self.groq_model,
                "stream": False,
                "temperature": 0.2,
                "max_tokens": self._output_token_limit(max_output_tokens, 1024),
                  "messages": [
                      {"role": "system", "content": "Sen JARVIS'sin. Daima Türkçe yanıt ver; kısa, doğru ve işe yarar ol."},
                      {"role": "user", "content": user_text},
                  ]},
            timeout=min(self.timeout, 60),
        )
        if not response.ok:
            raise RuntimeError("Groq API HTTP {}: {}".format(response.status_code, response.text[:300]))
        choices = response.json().get("choices") or []
        answer = (choices[0].get("message") or {}).get("content", "") if choices else ""
        if not str(answer or "").strip():
            raise RuntimeError("Groq boş yanıt döndürdü.")
        return str(answer).strip()

    respond = ask
    generate=ask
    process=ask
