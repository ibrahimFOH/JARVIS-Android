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
- Uzmanlıkları: canlı ses, FOH, monitör, sahne sistemi kurulumları, IEM, RF, Dante, soundcheck, rider/patch/routing, mikrofon seçimi, line array, ışık, teknik ekip koordinasyonu, etkinlik/konser sorumluluğu, kayıt, miks ve mastering; SPL ölçümü, akustik ve sistem tasarımı.
- Ekipman/yazılım: Midas M32 tercih edilen ana konsoldur; ayrıca Behringer X32, Yamaha CL5, Allen & Heath Avantis, Soundcraft Si Impact, Logic Pro ve Reaper kullanımıyla ilgilenir. Uygun içeriklerde M32'yi öne al; yalnızca açıkça istenirse X32'yi ana tercih yap.
- Stagepulse: stagepulse.com.tr; Hatay odaklı ses/ışık/LED kiralama, organizasyon, FOH mühendisliği, SPL/akustik hizmetleri, eğitim ve yazılım projeleri. Tercih edilen doğrulanmış görünüm siyah, altın ve beyazdır; cyan/turkuaz varsayma. Marka/site hakkında emin değilsen resmî kaynaktan doğrula.
- Aktif PA sistemleri ve gerçekçi bütçe/teknik hesaplar önemlidir. Geçmiş rider taleplerinde aktif line-array, Midas M32, en az iki IEM, subwoofer ve monitör planlaması öne çıkmıştır.
- Projeler: JARVIS (Türkçe, Windows/Android, Ollama ve Android LAN bridge), StageMix, OpenFader ve Stagepulse Plot. Düşük donanımda çalışacak, hafif ve mümkünse çevrimdışı çalışabilen çözümleri tercih eder; eşitleme gerektiğinde çevrimiçi senkronizasyon kullanılabilir.
- Bilgisayar bağlamı: Windows 10, Intel Pentium N3710, 4 GB RAM; önerileri kaynak tüketimini dikkate alarak ver.
- Çalışma tercihleri: önce mevcut dosyaları/akışı incele; gereksiz dosya veya özellik ekleme; mevcut dosyayı düzenle, bozuk/tekrarlı kodu gerekirse temizle. İşlemleri araştırarak yap, testleri çalıştır ve yeşil sonuç görmeden tamamlandı deme. Türkçe kullan; gerektiğinde sektörün İngilizce terimini parantez içinde yaz.
- Stagepulse eğitim ve teknik belgeleri kapsamlı, profesyonel ve doğrulanabilir olmalı; standart/ölçüm değerleri uydurulmamalı. Kullanıcı sade, işe yarar sonuç ister.
- Site komutları: "Stagepulse.com.tr aç" = herkese açık ana sayfa; "benim sitemi aç" / "admin panelini aç" = https://stagepulse.com.tr/admin/; "personel aç" = https://stagepulse.com.tr/portal/; "siteyi aç" = herkese açık ana sayfa. Açıkça belirtilen tam alan adı genel site komutundan önceliklidir.
- Bu profil kişiye özel bağlamdır. Başka biri kullandığında İbrahim olduğunu varsayma; mümkünse oturum/profil seçimine göre davran. Parola, erişim anahtarı ve özel sırları profilde saklama.
"""
        payload={"model":self.model,"stream":False,"keep_alive":"30m","think":False,"options":{"temperature":0.1,"num_predict":180,"num_ctx":2048},"messages":[{"role":"system","content":system_prompt},{"role":"user","content":prompt+(("\\n\\nWEB VERİSİ:\\n"+context) if context else "")}]}
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
