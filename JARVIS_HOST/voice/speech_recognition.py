"""Turkish offline speech recognition using a locally stored Vosk model."""
from __future__ import annotations

from typing import Optional, Dict, Any
from pathlib import Path
import json

import speech_recognition as sr

from utils.logger import get_logger
from utils.config_manager import get_config
from voice.vosk_model_manager import VoskModelManager, VoskModelError

logger = get_logger()
config = get_config()


class SpeechRecognizer:
    """Microphone capture and Turkish speech-to-text without paid cloud APIs."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.microphone_error = ""
        self.last_recognition_error = ""
        self.engine = str(config.get("voice.recognition_engine", "vosk") or "vosk").lower()
        self.language = "tr-TR"
        self.timeout = float(config.get("voice.recognition_timeout", 5) or 5)
        self.phrase_limit = float(config.get("voice.phrase_time_limit", 10) or 10)
        self.recognizer.energy_threshold = int(config.get("voice.energy_threshold", 4000) or 4000)
        self.recognizer.dynamic_energy_threshold = bool(config.get("voice.dynamic_energy_threshold", True))
        self.vosk_model = None
        self.vosk_model_path = None
        self.model_error = ""

        if self.engine != "vosk":
            logger.warning(
                "Ücretli veya çevrimiçi konuşma servisi seçimi kapatıldı; yerel Türkçe Vosk kullanılacak."
            )
            self.engine = "vosk"

        try:
            self.microphone = sr.Microphone()
            logger.info("Mikrofon aygıtı bulundu.")
        except Exception as exc:
            self.microphone_error = str(exc)
            logger.error("Mikrofon başlatılamadı: " + self.microphone_error)

        self._load_vosk_model()
        self._calibrate()

    def _load_vosk_model(self):
        configured = config.get("voice.vosk_model_path", "") or ""
        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)
            self.vosk_model_path = VoskModelManager(configured_path=configured).ensure_model()
            self.vosk_model = Model(str(self.vosk_model_path))
            logger.info("Yerel Türkçe Vosk modeli hazır: " + str(self.vosk_model_path))
            return True
        except (ImportError, VoskModelError, Exception) as exc:
            self.model_error = str(exc)
            self.vosk_model = None
            logger.error("Yerel Türkçe konuşma modeli yüklenemedi: " + self.model_error)
            return False

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
            return {
                "success": False, "error": "microphone_unavailable",
                "message": "Mikrofon bulunamadı veya açılamadı. Windows giriş aygıtını ve mikrofon izinlerini kontrol edin."
            }
        if self.vosk_model is None:
            return {
                "success": False, "error": "offline_model_unavailable",
                "message": (
                    "Yerel Türkçe konuşma modeli hazır değil. İnternet bağlantısını ve model klasörünü kontrol edin. "
                    + self.model_error
                )
            }

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
                    return {
                        "success": False, "error": "timeout",
                        "message": "Belirlenen sürede konuşma algılanmadı."
                    }
            text = self._recognize_audio(audio)
            if text:
                logger.info("Çevrimdışı Türkçe ses tanındı: " + text)
                return {"success": True, "text": text}
            return {
                "success": False, "error": "no_recognition",
                "message": "Ses alındı ancak konuşma anlaşılamadı. Daha net konuşup tekrar deneyin."
            }
        except Exception as exc:
            logger.error("Çevrimdışı ses tanıma hatası: " + str(exc))
            return {
                "success": False, "error": "exception",
                "message": "Mikrofon veya yerel ses tanıma kullanılamadı: " + str(exc)
            }

    def _recognize_audio(self, audio):
        if self.vosk_model is None:
            self.last_recognition_error = self.model_error or "Yerel Vosk modeli yüklenmedi."
            return None
        try:
            from vosk import KaldiRecognizer
            raw_audio = audio.get_raw_data(convert_rate=16000, convert_width=2)
            if not raw_audio:
                return None
            recognizer = KaldiRecognizer(self.vosk_model, 16000)
            recognizer.SetWords(False)
            recognizer.AcceptWaveform(raw_audio)
            result = json.loads(recognizer.FinalResult() or "{}")
            text = str(result.get("text", "")).strip()
            return text or None
        except Exception as exc:
            self.last_recognition_error = "Yerel Türkçe ses çözümlemesi başarısız: " + str(exc)
            logger.error(self.last_recognition_error)
            return None

    def test_microphone(self):
        if self.microphone is None:
            return {
                "success": False,
                "message": "Mikrofon başlatılamadı: " + (self.microphone_error or "kullanılabilir aygıt yok")
            }
        if self.vosk_model is None:
            return {
                "success": False,
                "message": "Mikrofon görüldü ancak yerel Türkçe model hazır değil: " + self.model_error
            }
        try:
            with self.microphone as source:
                self.recognizer.listen(source, timeout=3, phrase_time_limit=2)
            return {"success": True, "message": "Ses girişi algılandı. Tanıma yerel Vosk ile yapılır."}
        except sr.WaitTimeoutError:
            return {"success": False, "message": "Mikrofon açık ancak test sırasında ses algılanmadı."}
        except Exception as exc:
            return {"success": False, "message": "Mikrofon testi başarısız: " + str(exc)}

    def set_energy_threshold(self, threshold: int):
        self.recognizer.energy_threshold = max(100, int(threshold))

    def recalibrate(self):
        return self._calibrate()
