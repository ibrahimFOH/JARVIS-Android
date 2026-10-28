"""Turkish speech recognition with explicit microphone and network diagnostics."""
from __future__ import annotations
from typing import Optional, Dict, Any
import speech_recognition as sr
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

class SpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.microphone_error = ""
        self.last_recognition_error = ""
        self.engine = str(config.get("voice.recognition_engine", "google") or "google").lower()
        self.language = str(config.get("voice.recognition_language", "tr-TR") or "tr-TR")
        self.timeout = float(config.get("voice.recognition_timeout", 5) or 5)
        self.phrase_limit = float(config.get("voice.phrase_time_limit", 10) or 10)
        self.recognizer.energy_threshold = int(config.get("voice.energy_threshold", 4000) or 4000)
        self.recognizer.dynamic_energy_threshold = bool(config.get("voice.dynamic_energy_threshold", True))
        try:
            self.microphone = sr.Microphone()
            logger.info("Mikrofon aygıtı bulundu.")
        except Exception as exc:
            self.microphone_error = str(exc)
            logger.error("Mikrofon başlatılamadı: " + self.microphone_error)
        self._calibrate()

    def _calibrate(self):
        if self.microphone is None:
            return False
        try:
            logger.info("Ortam gürültüsü ölçülüyor...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.7)
            logger.info("Mikrofon kalibrasyonu tamamlandı. Eşik: " + str(self.recognizer.energy_threshold))
            return True
        except Exception as exc:
            logger.warning("Mikrofon kalibrasyonu başarısız: " + str(exc))
            return False

    def listen(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> Dict[str, Any]:
        if self.microphone is None:
            return {"success": False, "error": "microphone_unavailable",
                    "message": "Mikrofon bulunamadı veya açılamadı. Windows giriş aygıtını ve mikrofon izinlerini kontrol edin."}
        self.last_recognition_error = ""
        try:
            with self.microphone as source:
                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=self.timeout if timeout is None else timeout,
                        phrase_time_limit=self.phrase_limit if phrase_time_limit is None else phrase_time_limit,
                    )
                except sr.WaitTimeoutError:
                    return {"success": False, "error": "timeout", "message": "Belirlenen sürede konuşma algılanmadı."}
            text = self._recognize_audio(audio)
            if text:
                logger.info("Ses tanındı: " + text)
                return {"success": True, "text": text}
            if self.last_recognition_error:
                return {"success": False, "error": "recognition_service_unavailable",
                        "message": self.last_recognition_error}
            return {"success": False, "error": "no_recognition",
                    "message": "Ses alındı ancak konuşma anlaşılamadı. Daha net konuşup tekrar deneyin."}
        except Exception as exc:
            logger.error("Ses tanıma hatası: " + str(exc))
            return {"success": False, "error": "exception", "message": "Mikrofon kullanılamadı: " + str(exc)}

    def _recognize_audio(self, audio):
        try:
            if self.engine == "sphinx":
                return self.recognizer.recognize_sphinx(audio)
            return self.recognizer.recognize_google(audio, language=self.language)
        except sr.UnknownValueError:
            return None
        except sr.RequestError as exc:
            self.last_recognition_error = (
                "Çevrimiçi Türkçe ses tanıma servisine ulaşılamadı. İnternet bağlantısını kontrol edin. " + str(exc)
            )
            logger.error("Ses tanıma servisi hatası: " + str(exc))
            return None
        except Exception as exc:
            self.last_recognition_error = "Ses tanıma başarısız: " + str(exc)
            logger.error(self.last_recognition_error)
            return None

    def test_microphone(self):
        if self.microphone is None:
            return {"success": False, "message": "Mikrofon başlatılamadı: " + (self.microphone_error or "kullanılabilir aygıt yok")}
        try:
            with self.microphone as source:
                self.recognizer.listen(source, timeout=3, phrase_time_limit=2)
            return {"success": True, "message": "Ses girişi algılandı."}
        except sr.WaitTimeoutError:
            return {"success": False, "message": "Mikrofon açık ancak test sırasında ses algılanmadı."}
        except Exception as exc:
            return {"success": False, "message": "Mikrofon testi başarısız: " + str(exc)}

    def set_energy_threshold(self, threshold: int):
        self.recognizer.energy_threshold = max(100, int(threshold))

    def recalibrate(self):
        return self._calibrate()
