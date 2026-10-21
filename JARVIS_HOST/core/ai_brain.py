import html
import os
import re
import requests
from urllib.parse import quote


class AIBrain:
    """Multi-provider assistant: Gemini, Ollama, or Gemini-first fallback."""

    def __init__(self):
        self.host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.model = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
        self.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.provider = os.environ.get("JARVIS_AI_PROVIDER", "auto").strip().lower()
        self.timeout = 45
        self.web_timeout = 5
        self.session = requests.Session()

    def _instant(self, text):
        t = (text or "").strip().lower()
        if any(x in t for x in ("kimsin", "sen kimsin", "adın ne", "ismin ne")):
            return "Ben JARVIS. Gemini ve/veya Ollama ile çalışan Türkçe masaüstü asistanınım."
        if any(x in t for x in ("ne yapabilirsin", "neler yapabilirsin", "yeteneklerin")):
            return "Türkçe sohbet, web araştırması ve bağlı Windows araçlarını kullanabilirim. Gemini ve Ollama sağlayıcıları yapılandırmaya bağlıdır."
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

    def _gemini(self, prompt, context=""):
        if not self.gemini_key:
            raise RuntimeError("Gemini seçildi ancak GEMINI_API_KEY ayarlanmamış.")
        url = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent".format(self.gemini_model)
        contents = prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")
        payload = {"systemInstruction": {"parts": [{"text": "Sen JARVIS'sin. Türkçe konuş. Kısa, doğrudan ve işe yarar cevap ver."}]},
                   "contents": [{"role": "user", "parts": [{"text": contents}]}],
                   "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}}
        r = self.session.post(url, params={"key": self.gemini_key}, json=payload, timeout=self.timeout)
        if not r.ok:
            raise RuntimeError("Gemini API HTTP {}: {}".format(r.status_code, r.text[:500]))
        data = r.json()
        return "".join(part.get("text", "") for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])).strip()

    def _ollama(self, prompt, context=""):
        payload = {"model": self.model, "stream": False, "keep_alive": "30m", "think": False,
                   "options": {"temperature": 0.1, "num_predict": 160, "num_ctx": 2048},
                   "messages": [{"role": "system", "content": "Sen JARVIS'sin. Türkçe konuş. Kısa, doğrudan ve işe yarar cevap ver."},
                                {"role": "user", "content": prompt + (("\n\nWEB VERİSİ:\n" + context) if context else "")}]}
        r = self.session.post(self.host + "/api/chat", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return ((r.json().get("message") or {}).get("content") or "").strip()

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
