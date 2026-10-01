"""
Intent recognition system for Jarvis V2
Turkish + English language support
"""

import re
from typing import Dict, List, Tuple


class IntentRecognizer:
    """Recognizes user intent from natural language commands"""

    def __init__(self):
        self.intent_patterns = {
            "launch_app": [
                r"\b(?:open|launch|start|run)\s+(.+)",
                r"\b(.+?)\s+(?:aç|başlat|çalıştır)\b",
                r"\b(.+?)(?:'u|'ü|'yı|'yi|'ı|'i)\s+(?:aç|başlat|çalıştır)\b",
                r"\b(?:aç|başlat|çalıştır)\s+(.+)",
            ],

            "close_app": [
                r"\b(?:close|quit|exit|terminate)\s+(.+)",
                r"\b(.+?)\s+(?:kapat|sonlandır)\b",
                r"\b(.+?)(?:'u|'ü|'yı|'yi|'ı|'i)\s+(?:kapat|sonlandır)\b",
                r"\b(?:kapat|sonlandır)\s+(.+)",
            ],

            "switch_app": [
                r"\b(?:switch to|go to|change to)\s+(.+)",
                r"\b(.+?)\s+(?:uygulamasına|uygulamasina)\s+geç\b",
                r"\b(.+?)\s+(?:uygulamasına|uygulamasina)\s+gec\b",
                r"\b(.+?)\s+geç\b",
                r"\b(.+?)\s+gec\b",
            ],

            "list_apps": [
                r"\b(?:list|show|display)\s+(?:open|running|active)\s+(?:apps|applications)\b",
                r"\b(?:açık|acik|çalışan|calisan|aktif)\s+(?:uygulamaları|uygulamalari)\s+(?:göster|goster|listele)\b",
                r"\bhangi\s+uygulamalar\s+(?:açık|acik)\b",
            ],

            "screenshot_window": [
                r"\b(?:screenshot|capture)\s+(?:this|the current)\s+(?:window)\b",
                r"\b(?:bu|aktif)\s+pencerenin\s+(?:ekran görüntüsünü|ekran goruntusunu)\s+al\b",
                r"\b(?:bu|aktif)\s+pencereyi\s+(?:yakala|çek|cek)\b",
            ],

            "screenshot_region": [
                r"\b(?:screenshot|capture)\s+(?:a|the)\s+(?:region|area)\b",
                r"\b(?:bölge|bolge|alan)\s+(?:ekran görüntüsü|ekran goruntusu)\s+al\b",
                r"\b(?:ekranın|ekranin)\s+(?:bir bölgesinin|bir bolgesinin|bir alanının|bir alaninin)\s+(?:görüntüsünü|goruntusunu)\s+al\b",
            ],

            "screenshot": [
                r"\b(?:take|capture|get)\s+(?:a\s+)?screenshot\b",
                r"\b(?:ekran görüntüsü|ekran goruntusu)\s+(?:al|çek|cek|yakala)\b",
                r"\b(?:ekranı|ekrani)\s+(?:yakala|çek|cek)\b",
            ],

            "volume": [
                r"\b(?:set|change|adjust)\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)",
                r"\b(?:volume|ses)\s+(?:to\s+)?(\d+)",
                r"\b(?:sesi|ses)\s+(?:yüzde|yuzde)?\s*(\d+)\s*(?:yap|ayarla)?\b",
                r"\b(?:ses)\s+(\d+)\s+(?:yap|ayarla)\b",
            ],

            "mute": [
                r"\b(?:mute|silence)\s+(?:the\s+)?(?:system|volume|sound)?\b",
                r"\b(?:sesi|sistemi)\s+(?:kapat|sessize al|sustur)\b",
                r"\b(?:sessize al|sesi kapat|sesi sustur)\b",
            ],

            "brightness": [
                r"\b(?:set|change|adjust)\s+(?:the\s+)?brightness\s+(?:to\s+)?(\d+)",
                r"\b(?:parlaklığı|parlakligi)\s+(\d+)\s*(?:yap|ayarla)?\b",
            ],

            "system_info": [
                r"\b(?:system|computer)\s+(?:info|information|status)\b",
                r"\b(?:sistem|bilgisayar)\s+(?:bilgisi|durumu|durum)\b",
                r"\b(?:bilgisayarım|bilgisayarim)\s+(?:nasıl|nasil)\b",
                r"\b(?:sistem)\s+(?:nasıl|nasil)\b",
            ],

            "lock_screen": [
                r"\b(?:lock)\s+(?:the\s+)?(?:screen|computer)\b",
                r"\b(?:ekranı|ekrani|bilgisayarı|bilgisayari)\s+kilitle\b",
                r"\b(?:bilgisayarı|bilgisayari)\s+kilitle\b",
            ],

            "shutdown": [
                r"\b(?:shutdown|shut down|power off)\s+(?:the\s+)?(?:computer|system)?\b",
                r"\b(?:bilgisayarı|bilgisayari|sistemi)\s+kapat\b",
                r"\b(?:bilgisayarı|bilgisayari)\s+kapatalım\b",
                r"\b(?:bilgisayarı|bilgisayari)\s+kapatalim\b",
            ],

            "restart": [
                r"\b(?:restart|reboot)\s+(?:the\s+)?(?:computer|system)?\b",
                r"\b(?:bilgisayarı|bilgisayari|sistemi)\s+(?:yeniden başlat|yeniden baslat)\b",
                r"\b(?:yeniden başlat|yeniden baslat)\b",
            ],

            "sleep": [
                r"\b(?:sleep|suspend)\s+(?:the\s+)?(?:computer|system)?\b",
                r"\b(?:bilgisayarı|bilgisayari)\s+(?:uykuya al|uyut)\b",
                r"\b(?:uykuya al|uyut)\b",
            ],

            "open_file": [
                r"\b(?:open)\s+(?:file|document)\s+(.+)",
                r"\b(.+?)\s+(?:dosyasını|dosyasini|belgesini)\s+aç\b",
                r"\b(?:dosyayı|dosyayi|belgeyi)\s+aç\s+(.+)",
            ],

            "find_files": [
                r"\b(?:find|search for|locate)\s+(?:files?|documents?)\s*(.*)",
                r"\b(?:dosya|dosyaları|dosyalari|belge|belgeleri)\s+(?:bul|ara)\s*(.*)",
                r"\b(.+?)\s+(?:dosyalarını|dosyalarini)\s+bul\b",
            ],

            "create_folder": [
                r"\b(?:create|make)\s+(?:a\s+)?folder\s+(.+)",
                r"\b(.+?)\s+(?:klasörü|klasoru)\s+oluştur\b",
                r"\b(.+?)\s+(?:klasörü|klasoru)\s+olustur\b",
                r"\b(?:klasör|klasor)\s+oluştur\s+(.+)",
                r"\b(?:klasör|klasor)\s+olustur\s+(.+)",
            ],

            "delete_file": [
                r"\b(?:delete|remove)\s+(?:file\s+)?(.+)",
                r"\b(.+?)\s+(?:dosyasını|dosyasini)\s+sil\b",
                r"\b(?:dosyayı|dosyayi)\s+sil\s+(.+)",
            ],

            "maximize": [
                r"\b(?:maximize|fullscreen)\s+(?:the\s+)?(?:window)?\b",
                r"\b(?:pencereyi)\s+(?:büyüt|buyut|maximize et|tam ekran yap)\b",
                r"\b(?:tam ekran)\s+(?:yap|ol)\b",
            ],

            "minimize": [
                r"\b(?:minimize)\s+(?:the\s+)?(?:window)?\b",
                r"\b(?:pencereyi)\s+(?:küçült|kucult|minimize et)\b",
            ],

            "split_screen": [
                r"\b(?:split|tile)\s+(?:the\s+)?screen\b",
                r"\b(?:ekranı|ekrani)\s+(?:böl|bol)\b",
                r"\b(?:ekranı|ekrani)\s+(?:ikiye|dörde|dorde)\s+(?:böl|bol)\b",
            ],

            "time": [
                r"\b(?:what\s+time\s+is\s+it|current\s+time|time)\b",
                r"\b(?:saat kaç|saat kac)\b",
                r"\b(?:şu an|su an)\s+saat\s+(?:kaç|kac)\b",
            ],

            "date": [
                r"\b(?:what\s+is\s+the\s+date|today's\s+date|current\s+date)\b",
                r"\b(?:bugünün|bugunun)\s+tarihi\s+(?:ne|nedir)\b",
                r"\b(?:bugün|bugun)\s+hangi\s+gün\b",
                r"\b(?:bugün|bugun)\s+hangi\s+gun\b",
            ],

            "weather": [
                r"\b(?:what's|what is)\s+(?:the\s+)?weather\b",
                r"\b(?:hava durumu)\s+(?:nasıl|nasil)\b",
                r"\b(?:hava)\s+(?:nasıl|nasil)\b",
            ],

            "greeting": [
                r"\b(?:hello|hi|hey|good morning|good afternoon|good evening)\b",
                r"\b(?:merhaba|selam|günaydın|gunaydin|iyi günler|iyi gunler|iyi akşamlar|iyi aksamlar)\b",
            ],

            "status": [
                r"\b(?:how are you|are you okay|status)\b",
                r"\b(?:nasılsın|nasilsin|iyi misin|durumun ne|sistem durumu)\b",
            ],

            "help": [
                r"\b(?:help|what can you do|what are you capable of|commands|capabilities)\b",
                r"\b(?:ne yapabilirsin|neler yapabilirsin|ne yapabiliyorsun|neler yapabiliyorsun)\b",
                r"\b(?:yardım|yardim|komutlar|yeteneklerin|hangi komutlar)\b",
            ],

            "thank": [
                r"\b(?:thanks|thank you|thx)\b",
                r"\b(?:teşekkürler|tesekkurler|teşekkür ederim|tesekkur ederim|sağ ol|sag ol)\b",
            ],
        }

    def recognize(self, text: str) -> Tuple[str, float, Dict]:
        """Recognize intent from text."""

        text = text.lower().strip()

        best_intent = "unknown"
        best_confidence = 0.0
        best_params = {}

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)

                if match:
                    confidence = self._calculate_confidence(
                        text,
                        match,
                        intent
                    )

                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence
                        best_params = self._extract_parameters(
                            text,
                            match,
                            intent
                        )

        return {"intent": best_intent, "confidence": best_confidence, "parameters": best_params}

    def _calculate_confidence(
        self,
        text: str,
        match,
        intent: str
    ) -> float:
        """Calculate confidence score."""

        confidence = 0.7
        matched_text = match.group(0).lower()

        if matched_text == text:
            confidence += 0.2

        if len(matched_text) > len(text) * 0.7:
            confidence += 0.05

        if intent in [
            "shutdown",
            "restart",
            "lock_screen",
            "delete_file"
        ]:
            confidence += 0.02

        return min(confidence, 1.0)

    def _extract_parameters(
        self,
        text: str,
        match,
        intent: str
    ) -> Dict:
        """Extract parameters from recognized command."""

        params = {}
        groups = match.groups()

        if intent in [
            "launch_app",
            "close_app",
            "switch_app",
            "open_file",
            "find_files",
            "create_folder",
            "delete_file"
        ]:
            if groups:
                value = groups[-1].strip()

                if value:
                    params["target"] = value

        elif intent in ["volume", "brightness"]:
            if groups:
                try:
                    params["level"] = int(groups[-1])
                except (ValueError, TypeError):
                    pass

        return params

    def get_supported_intents(self) -> List[str]:
        """Get list of supported intents."""
        return list(self.intent_patterns.keys())

    def get_intent_description(self, intent: str) -> str:
        """Get Turkish description of an intent."""

        descriptions = {
            "launch_app": "Uygulama açma",
            "close_app": "Uygulama kapatma",
            "switch_app": "Uygulamalar arasında geçiş",
            "list_apps": "Açık uygulamaları listeleme",
            "screenshot_window": "Pencere ekran görüntüsü",
            "screenshot_region": "Bölge ekran görüntüsü",
            "screenshot": "Ekran görüntüsü",
            "volume": "Ses seviyesi",
            "mute": "Sesi kapatma",
            "brightness": "Ekran parlaklığı",
            "system_info": "Sistem bilgisi",
            "lock_screen": "Ekranı kilitleme",
            "shutdown": "Bilgisayarı kapatma",
            "restart": "Bilgisayarı yeniden başlatma",
            "sleep": "Uyku modu",
            "open_file": "Dosya açma",
            "find_files": "Dosya arama",
            "create_folder": "Klasör oluşturma",
            "delete_file": "Dosya silme",
            "maximize": "Pencereyi büyütme",
            "minimize": "Pencereyi küçültme",
            "split_screen": "Ekranı bölme",
            "time": "Saat bilgisi",
            "date": "Tarih bilgisi",
            "weather": "Hava durumu",
            "greeting": "Selamlaşma",
            "status": "Sistem durumu",
            "help": "Yardım ve komutlar",
            "thank": "Teşekkür",
            "unknown": "Bilinmeyen komut",
        }

        return descriptions.get(
            intent,
            "Bilinmeyen komut"
        )