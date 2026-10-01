import re
import html
import requests
from urllib.parse import quote

class AIBrain:
    def __init__(self):
        self.host="http://127.0.0.1:11434"
        self.model="qwen3:0.6b"
        self.timeout=18
        self.web_timeout=5

    def _instant(self,text):
        t=(text or "").strip().lower()
        if any(x in t for x in ("kimsin","sen kimsin","adın ne","ismin ne")):
            return "Ben JARVIS. Ollama ile çalışan Türkçe masaüstü asistanınım."
        if any(x in t for x in ("ne yapabilirsin","neler yapabilirsin","yeteneklerin")):
            return "Komut anlayabilir, Ollama ile cevap üretebilir, webden bilgi getirebilir ve bağlı güvenli araçları kullanabilirim."
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
        payload={"model":self.model,"stream":False,"keep_alive":"30m","think":False,"options":{"temperature":0.1,"num_predict":120,"num_ctx":2048},"messages":[{"role":"system","content":"Sen JARVIS'sin. Türkçe konuş. Kısa, doğrudan ve işe yarar cevap ver."},{"role":"user","content":prompt+(("\n\nWEB VERİSİ:\n"+context) if context else "")}]}
        try:
            r=requests.post(self.host+"/api/chat",json=payload,timeout=self.timeout)
            r.raise_for_status()
            return ((r.json().get("message") or {}).get("content") or "").strip()
        except Exception as e:
            return "Ollama bağlantısında sorun oluştu: "+str(e)

    def ask(self,prompt):
        instant=self._instant(prompt)
        if instant: return instant
        return self._ollama(prompt,self._web(prompt) if self._needs_web(prompt) else "")

    respond=ask
    generate=ask
    process=ask
