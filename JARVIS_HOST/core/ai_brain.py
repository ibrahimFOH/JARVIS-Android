import base64
import html
import json
import mimetypes
import os
import re
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


class AIBrain:
    """Gemini + Ollama assistant with persisted user settings and image workflows."""

    def __init__(self):
        self.session = requests.Session()
        self.timeout = 60
        self.web_timeout = 6
        self.settings_path = self._settings_file()
        saved = self._read_settings()
        self.host = os.environ.get("OLLAMA_HOST", saved.get("ollama_host", "http://127.0.0.1:11434")).rstrip("/")
        self.model = os.environ.get("OLLAMA_MODEL", saved.get("ollama_model", "qwen3:0.6b"))
        self.gemini_model = os.environ.get("GEMINI_MODEL", saved.get("gemini_model", "gemini-3.8-flash"))
        # Move the old default model forward; Google now limits access to some
        # legacy 2.5 model usage for accounts that were not already using them.
        if self.gemini_model.strip() == "gemini-2.5-flash":
            self.gemini_model = "gemini-3.8-flash"
        self.gemini_image_model = os.environ.get("GEMINI_IMAGE_MODEL", saved.get("gemini_image_model", "gemini-3.1-flash-image"))
        self.gemini_key = os.environ.get("GEMINI_API_KEY", self._unprotect_key(saved.get("gemini_api_key", ""))).strip()
        self.provider = saved.get("provider", os.environ.get("JARVIS_AI_PROVIDER", "auto")).strip().lower()
        if self.provider not in ("auto", "gemini", "ollama"):
            self.provider = "auto"

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
            encrypted = win32crypt.CryptProtectData(secret.encode("utf-8"), "Stagepulse JARVIS API Key", None, None, None, 0)[1]
            return {"dpapi": base64.b64encode(encrypted).decode("ascii")}
        except Exception:
            # Development environments without Windows DPAPI keep the key as plain text.
            return {"plain": secret}

    @staticmethod
    def _unprotect_key(value):
        if isinstance(value, str):
            return value  # Legacy settings file.
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
                  gemini_image_model=None, ollama_host=None, ollama_model=None):
        if provider is not None:
            provider = provider.strip().lower()
            if provider not in ("auto", "gemini", "ollama"):
                raise ValueError("Sağlayıcı auto, gemini veya ollama olmalı.")
            self.provider = provider
        if gemini_key is not None:
            self.gemini_key = gemini_key.strip()
        if gemini_model is not None and gemini_model.strip():
            self.gemini_model = gemini_model.strip()
        if self.gemini_model.strip() == "gemini-2.5-flash":
            self.gemini_model = "gemini-3.8-flash"
        if gemini_image_model is not None and gemini_image_model.strip():
            self.gemini_image_model = gemini_image_model.strip()
        if ollama_host is not None and ollama_host.strip():
            self.host = ollama_host.strip().rstrip("/")
        if ollama_model is not None and ollama_model.strip():
            self.model = ollama_model.strip()

        values = {
            "provider": self.provider,
            "gemini_api_key": self._protect_key(self.gemini_key),
            "gemini_model": self.gemini_model,
            "gemini_image_model": self.gemini_image_model,
            "ollama_host": self.host,
            "ollama_model": self.model,
        }
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.settings_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(temp_path), str(self.settings_path))

    def _instant(self, text):
        t = (text or "").strip().lower()
        if any(x in t for x in ("kimsin", "sen kimsin", "adın ne", "ismin ne")):
            return "Ben JARVIS. Gemini ve/veya Ollama ile çalışan Türkçe masaüstü asistanınım."
        if any(x in t for x in ("ne yapabilirsin", "neler yapabilirsin", "yeteneklerin")):
            return "Türkçe sohbet, web araştırması, Windows denetimi ve Gemini ile görsel analizi/üretimi yapabilirim. Özellikler ayarlara ve sağlayıcıya bağlıdır."
        if t in ("merhaba", "selam", "günaydın", "iyi akşamlar", "iyi geceler"):
            return "Hazırım Patron."
        return None

    def _needs_web(self, text):
        t = (text or "").lower()
        return any(x in t for x in ("internetten", "internette", "webde", "web'de", "araştır", "güncel", "şu an", "bugün", "son haber", "haberler", "fiyat", "site", "github", "youtube", "instagram", "stagepulse.com", "http://", "https://"))

    def _clean(self, raw):
        raw = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", raw)
        raw = re.sub(r"(?is)<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", html.unescape(raw)).strip()

    def _web(self, query):
        urls = re.findall(r"https?://[^\s]+", query or "")
        if urls:
            try:
                r = self.session.get(urls[0].rstrip(".,)"), timeout=self.web_timeout, headers={"User-Agent": "Mozilla/5.0 JARVIS/1.0"})
                if r.ok:
                    return self._clean(r.text)[:5000]
            except requests.RequestException:
                pass
        for engine in ("https://www.google.com/search?q=", "https://www.bing.com/search?q=", "https://html.duckduckgo.com/html/?q="):
            try:
                r = self.session.get(engine + quote(query), timeout=self.web_timeout, headers={"User-Agent": "Mozilla/5.0 JARVIS/1.0"})
                if r.ok:
                    text = self._clean(r.text)
                    if len(text) > 200:
                        return text[:5000]
            except requests.RequestException:
                pass
        return ""

    def _gemini_post(self, model, payload):
        # Last-resort migration for legacy settings, environment variables or stale UI state.
        if str(model).strip() == "gemini-2.5-flash":
            model = "gemini-3.8-flash"
        if not self.gemini_key:
            raise RuntimeError("Gemini API anahtarı ayarlanmamış. AI SETTINGS bölümünden ekleyin.")
        url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(
            quote(model.strip(), safe="-_.")
        )
        response = self.session.post(
            url, headers={"x-goog-api-key": self.gemini_key, "Content-Type": "application/json"},
            json=payload, timeout=self.timeout
        )
        if not response.ok:
            try:
                message = response.json().get("error", {}).get("message", response.text[:400])
            except ValueError:
                message = response.text[:400]
            raise RuntimeError("Gemini API HTTP {}: {}".format(response.status_code, message))
        data = response.json()
        if not data.get("candidates"):
            raise RuntimeError("Gemini boş yanıt döndürdü veya isteği engelledi.")
        return data

    @staticmethod
    def _response_text(data):
        chunks = []
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("text"):
                    chunks.append(part["text"])
        return "\n".join(chunks).strip()

    def _gemini(self, prompt, context=""):
        contents = prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")
        payload = {
            "systemInstruction": {"parts": [{"text": "Sen JARVIS'sin. Türkçe konuş. Kısa, doğrudan ve işe yarar cevap ver."}]},
            "contents": [{"role": "user", "parts": [{"text": contents}]}],
            "generationConfig": {"maxOutputTokens": 1024},
        }
        data = self._gemini_post(self.gemini_model, payload)
        return self._response_text(data) or "Gemini metin yanıtı döndürmedi."

    def _ollama(self, prompt, context=""):
        payload = {
            "model": self.model, "stream": False, "keep_alive": "30m", "think": False,
            "options": {"temperature": 0.1, "num_predict": 160, "num_ctx": 2048},
            "messages": [
                {"role": "system", "content": "Sen JARVIS'sin. Türkçe konuş. Kısa, doğrudan ve işe yarar cevap ver."},
                {"role": "user", "content": prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")},
            ],
        }
        r = self.session.post(self.host + "/api/chat", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return ((r.json().get("message") or {}).get("content") or "").strip()

    def analyze_image(self, prompt, image_path):
        image_file = Path(image_path)
        if not image_file.is_file():
            raise FileNotFoundError("Görsel dosyası bulunamadı.")
        raw = image_file.read_bytes()
        if not raw:
            raise ValueError("Görsel dosyası boş.")
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError("Görsel 12 MB sınırını aşıyor. Daha küçük bir kopya seçin.")
        mime_type = mimetypes.guess_type(str(image_file))[0] or "image/jpeg"
        payload = {
            "systemInstruction": {"parts": [{"text": "Sen JARVIS'sin. Görseli dikkatle analiz et ve Türkçe yanıt ver. Görselde olmayan ayrıntıları uydurma."}]},
            "contents": [{"role": "user", "parts": [
                {"text": prompt or "Bu görseli ayrıntılı şekilde analiz et."},
                {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(raw).decode("ascii")}},
            ]}],
            "generationConfig": {"maxOutputTokens": 1024},
        }
        data = self._gemini_post(self.gemini_model, payload)
        return self._response_text(data) or "Gemini görsel analizi için metin yanıtı döndürmedi."

    def generate_image(self, prompt):
        if not self.gemini_key:
            raise RuntimeError("Gemini API anahtarı ayarlanmamış. AI SETTINGS bölümünden ekleyin.")
        if not prompt or not prompt.strip():
            raise ValueError("Görsel için bir açıklama yazın.")
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        payload = {
            "model": self.gemini_image_model,
            "input": prompt.strip(),
            "response_format": {"type": "image", "mime_type": "image/png"},
        }
        response = self.session.post(
            url,
            headers={"x-goog-api-key": self.gemini_key, "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        if not response.ok:
            try:
                message = response.json().get("error", {}).get("message", response.text[:400])
            except ValueError:
                message = response.text[:400]
            raise RuntimeError("Gemini görsel API HTTP {}: {}".format(response.status_code, message))
        data = response.json()
        image_data = data.get("output_image") or {}
        encoded = image_data.get("data")
        mime_type = image_data.get("mime_type", image_data.get("mimeType", "image/png"))
        if not encoded:
            for step in data.get("steps", []):
                for block in step.get("content", []) or []:
                    if block.get("type") == "image":
                        encoded = block.get("data") or (block.get("image") or {}).get("data")
                        mime_type = block.get("mime_type", mime_type)
                        if encoded:
                            break
                if encoded:
                    break
        if not encoded:
            raise RuntimeError(
                "Gemini görsel üretmedi. Model erişimini ve API limitlerini kontrol edin. "
                + str(data.get("output_text", ""))[:300]
            )
        raw = base64.b64decode(encoded)
        ext = "jpg" if mime_type == "image/jpeg" else "png"
        base = Path.home() / "Pictures" / "StagepulseJARVIS"
        base.mkdir(parents=True, exist_ok=True)
        out = base / ("JARVIS_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "." + ext)
        out.write_bytes(raw)
        return str(out)

    def test_provider(self, provider=None):
        """Test a real request to Gemini or Ollama and return actionable diagnostics."""
        provider = (provider or self.provider).strip().lower()
        try:
            if provider == "ollama":
                response = self.session.get(self.host + "/api/tags", timeout=8)
                response.raise_for_status()
                models = [item.get("name", "") for item in response.json().get("models", [])]
                if not models:
                    return {"success": False, "message": "Ollama erişilebilir ancak model yüklü değil. CMD'de ollama pull " + self.model + " çalıştırın."}
                if not any(name == self.model or name.startswith(self.model + ":") for name in models):
                    return {"success": False, "message": "Ollama model bulunamadı: " + self.model + ". Yüklü modeller: " + ", ".join(models)}
                self._ollama("Sadece 'Bağlantı başarılı' yaz.")
                return {"success": True, "message": "Ollama bağlantısı başarılı: " + self.model}
            if provider == "gemini":
                if not self.gemini_key:
                    return {"success": False, "message": "Gemini API anahtarı boş. AI SETTINGS bölümünden ekleyin."}
                self._gemini("Sadece 'Bağlantı başarılı' yaz.")
                return {"success": True, "message": "Gemini API bağlantısı başarılı: " + self.gemini_model}
            return {"success": False, "message": "Sağlayıcı 'gemini' veya 'ollama' olmalı."}
        except Exception as exc:
            return {"success": False, "message": provider.upper() + " bağlantı hatası: " + str(exc)}

    def ask(self, prompt):
        instant = self._instant(prompt)
        if instant:
            return instant
        context = self._web(prompt) if self._needs_web(prompt) else ""
        order = (["gemini", "ollama"] if self.provider == "auto" else [self.provider])
        errors = []
        for provider in order:
            try:
                if provider == "gemini":
                    return self._gemini(prompt, context)
                if provider == "ollama":
                    return self._ollama(prompt, context)
                return "Bilinmeyen JARVIS_AI_PROVIDER: " + provider
            except Exception as exc:
                errors.append("{}: {}".format(provider, exc))
                if self.provider != "auto":
                    break
        return "Yapay zekâ yanıtı alınamadı. " + " | ".join(errors)

    respond = ask
    generate = ask
    process = ask