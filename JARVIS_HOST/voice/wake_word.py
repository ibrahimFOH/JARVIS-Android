"""Yerel Vosk ile çevrimdışı JARVIS uyandırma kelimesi algılama."""
from __future__ import annotations

from threading import Thread, Event
from typing import Optional, Callable
import re
import unicodedata

from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()


def _normalize(value: str) -> str:
    value = str(value or "").casefold().replace("ı", "i")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


class WakeWordDetector:
    """Sürekli dinlemeyi bulut kullanmadan aynı yerel Vosk modelinde yürütür."""

    def __init__(self, wake_word: Optional[str] = None, speech_recognizer=None):
        self.wake_word = wake_word or config.get("voice.wake_word", "jarvis")
        self.speech_recognizer = speech_recognizer
        if self.speech_recognizer is None:
            try:
                from voice.speech_recognition import SpeechRecognizer
                self.speech_recognizer = SpeechRecognizer()
            except Exception as exc:
                logger.error("Yerel uyandırma algılayıcısı hazırlanamadı: " + str(exc))
        self.is_listening = False
        self.stop_event = Event()
        self.listen_thread = None
        self.is_available = bool(
            self.speech_recognizer
            and getattr(self.speech_recognizer, "microphone", None) is not None
            and getattr(self.speech_recognizer, "vosk_model", None) is not None
        )

    def start(self, callback: Callable):
        if self.is_listening:
            return True
        if not self.is_available:
            logger.warning("Çevrimdışı uyandırma kelimesi hazır değil; mikrofon veya Vosk modeli kullanılamıyor.")
            return False

        self.is_listening = True
        self.stop_event.clear()
        self.listen_thread = Thread(
            target=self._listen_loop,
            args=(callback,),
            daemon=True,
            name="JARVIS-Offline-WakeWord",
        )
        try:
            self.listen_thread.start()
            logger.info("Yerel uyandırma algılama başladı: " + str(self.wake_word))
            return True
        except Exception as exc:
            self.is_listening = False
            logger.error("Uyandırma algılama iş parçacığı başlatılamadı: " + str(exc))
            return False

    def _listen_loop(self, callback: Callable):
        target = _normalize(self.wake_word)
        try:
            while self.is_listening and not self.stop_event.is_set():
                result = self.speech_recognizer.listen(timeout=2, phrase_time_limit=3)
                if self.stop_event.is_set():
                    break
                error = result.get("error")
                if error == "timeout" or error == "no_recognition":
                    continue
                if error in {"microphone_unavailable", "offline_model_unavailable"}:
                    logger.error("Yerel uyandırma algılaması durdu: " + str(result.get("message", error)))
                    break
                if not result.get("success"):
                    logger.warning("Yerel uyandırma algılama hatası: " + str(result.get("message", error or "bilinmeyen hata")))
                    if self.stop_event.wait(0.5):
                        break
                    continue

                recognized = _normalize(result.get("text", ""))
                if target and target in recognized:
                    logger.info("JARVIS uyandırma kelimesi algılandı.")
                    if callback:
                        callback()
        except Exception as exc:
            logger.error("Yerel uyandırma döngüsü başarısız: " + str(exc))
        finally:
            self.is_listening = False
            logger.info("Yerel uyandırma algılama durdu.")

    def stop(self):
        self.is_listening = False
        self.stop_event.set()
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=3)

    def __del__(self):
        self.stop()


class SimpleWakeWordDetector(WakeWordDetector):
    """Geriye dönük uyumlu ad; aynı çevrimdışı Vosk motorunu kullanır."""
    pass
