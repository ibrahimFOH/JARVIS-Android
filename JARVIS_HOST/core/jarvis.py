"""Main JARVIS controller with serialized commands and speech playback."""
from __future__ import annotations
import threading
from typing import Optional, Callable
from utils.logger import get_logger, log_startup
from utils.config_manager import get_config
from core.command_processor import CommandProcessor
from voice import SpeechRecognizer, TextToSpeech, WakeWordDetector, SimpleWakeWordDetector
from personality.response_generator import ResponseGenerator

logger = get_logger()
config = get_config()

class Jarvis:
    """JARVIS desktop assistant controller."""
    def __init__(self):
        log_startup()
        logger.info("JARVIS başlatılıyor...")
        self.command_processor = CommandProcessor()
        self.response_generator = ResponseGenerator()
        self.voice_enabled = bool(config.get("voice.enabled", True))
        self.speech_recognizer = None
        self.text_to_speech = None
        self.wake_word_detector = None
        if self.voice_enabled:
            try:
                self.speech_recognizer = SpeechRecognizer()
            except Exception as exc:
                logger.error("Ses tanıma başlatılamadı; metin arayüzü açık kalacak: " + str(exc))
            try:
                self.text_to_speech = TextToSpeech()
            except Exception as exc:
                logger.error("Ses motoru başlatılamadı; metin arayüzü açık kalacak: " + str(exc))
            if config.get("voice.wake_word_enabled", False):
                try:
                    self.wake_word_detector = WakeWordDetector()
                except Exception as exc:
                    logger.warning("Uyandırma algılayıcısı kullanılamadı: " + str(exc))
                    try:
                        self.wake_word_detector = SimpleWakeWordDetector()
                    except Exception as fallback_exc:
                        logger.warning("Uyandırma algılayıcısı kapalı: " + str(fallback_exc))
        self.is_running = False
        self.listening_continuously = False
        self.stop_event = threading.Event()
        self._command_lock = threading.Lock()
        self.on_command_callback: Optional[Callable] = None
        self.on_response_callback: Optional[Callable] = None
        logger.info("JARVIS çekirdeği hazır.")

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.stop_event.clear()
        if config.get("personality.greeting_enabled", True):
            self.speak(self.response_generator.generate("greeting"), wait=True)
        logger.info("JARVIS çalışıyor.")

    def stop(self):
        if not self.is_running:
            return
        logger.info("JARVIS kapatılıyor...")
        self.stop_event.set()
        self.listening_continuously = False
        if self.wake_word_detector:
            try:
                self.wake_word_detector.stop()
            except Exception:
                pass
        if self.text_to_speech:
            try:
                self.text_to_speech.stop()
            except Exception:
                pass
        self.is_running = False
        logger.info("JARVIS kapatıldı.")

    def _notify_command(self, command):
        if self.on_command_callback:
            try:
                self.on_command_callback(command)
            except Exception as exc:
                logger.warning("Komut arayüz bildirimi başarısız: " + str(exc))

    def _notify_response(self, result):
        if self.on_response_callback:
            try:
                self.on_response_callback(result)
            except Exception as exc:
                logger.warning("Yanıt arayüz bildirimi başarısız: " + str(exc))

    def process_command(self, command: str, speak_response: bool = True) -> dict:
        """Run typed commands in a worker thread and wait for speech before releasing it."""
        command = str(command or "").strip()
        if not command:
            return {"success": False, "response": "Boş komut gönderildi."}
        if not self.is_running:
            return {"success": False, "response": "JARVIS çalışmıyor."}
        self._notify_command(command)

        def worker():
            with self._command_lock:
                try:
                    result = self.command_processor.process(command)
                    if not isinstance(result, dict):
                        result = {"success": False, "response": "Komut motoru geçerli yanıt döndürmedi."}
                    if speak_response and not result.get("requires_confirmation"):
                        response_text = str(result.get("response", "") or "")
                        if response_text and not self.speak(response_text, wait=True):
                            result["speech_warning"] = "Yanıt metni üretildi ancak seslendirme başarısız oldu."
                    self._notify_response(result)
                    logger.response(str(result.get("response", "")))
                except Exception as exc:
                    logger.error("Komut işleme hatası: " + str(exc))
                    self._notify_response({"success": False,
                        "response": "Patron, komut işlenirken hata oluştu: " + str(exc), "intent": "error"})

        threading.Thread(target=worker, daemon=True, name="JARVIS-Command").start()
        return {"success": True, "response": "Komut işleniyor.", "async": True}

    def process_voice_command(self) -> dict:
        """Own the command lock during capture, processing, and speech to avoid self-triggering."""
        if not self.voice_enabled or self.speech_recognizer is None:
            return {
                "success": False,
                "error": "voice_disabled",
                "message": "Sesli komutlar etkin değil veya mikrofon başlatılamadı.",
            }

        # Do not record assistant speech or let multiple listeners capture the same phrase.
        with self._command_lock:
            listened = self.speech_recognizer.listen()
            if not listened.get("success"):
                return listened
            command = str(listened.get("text", "")).strip()
            if not command:
                return {"success": False, "error": "no_recognition", "message": "Konuşma anlaşılamadı."}

            self._notify_command(command)
            try:
                result = self.command_processor.process(command)
                if not isinstance(result, dict):
                    result = {"success": False, "response": "Komut motoru geçerli yanıt döndürmedi."}
                result["text"] = command
                if not result.get("requires_confirmation"):
                    response_text = str(result.get("response", "") or "")
                    if response_text and not self.speak(response_text, wait=True):
                        result["speech_warning"] = "Yanıt metni üretildi ancak seslendirilemedi."
                self._notify_response(result)
                logger.response(str(result.get("response", "")))
                return result
            except Exception as exc:
                logger.error("Sesli komut işleme hatası: " + str(exc))
                result = {
                    "success": False,
                    "error": "command_failed",
                    "text": command,
                    "response": "Patron, sesli komut işlenirken hata oluştu: " + str(exc),
                }
                self._notify_response(result)
                return result

    def start_listening(self):
        """Start a continuous loop without recording over the previous response."""
        if not self.voice_enabled or self.speech_recognizer is None:
            logger.warning("Sürekli dinleme başlatılamadı; mikrofon kullanılamıyor.")
            return False
        if self.listening_continuously:
            return True
        self.listening_continuously = True
        self.stop_event.clear()
        def listening_loop():
            logger.info("Sürekli dinleme başladı.")
            while self.listening_continuously and not self.stop_event.is_set():
                try:
                    result = self.process_voice_command()
                    if not result.get("success") and result.get("error") not in ("timeout", "no_recognition"):
                        logger.warning("Dinleme durumu: " + str(result.get("message", result.get("error", ""))))
                        self.stop_event.wait(0.5)
                except Exception as exc:
                    logger.error("Sürekli dinleme hatası: " + str(exc))
                    self.stop_event.wait(1.0)
            logger.info("Sürekli dinleme durdu.")
        threading.Thread(target=listening_loop, daemon=True, name="JARVIS-Continuous-Listen").start()
        return True

    def stop_listening(self):
        self.listening_continuously = False
        logger.info("Sürekli dinleme durduruluyor.")

    def start_wake_word_detection(self):
        if not self.wake_word_detector:
            logger.warning("Uyandırma sözcüğü algılayıcısı kullanılabilir değil.")
            return False
        def on_wake_word():
            if not self.stop_event.is_set():
                self.speak("Evet, Patron?", wait=True)
                self.process_voice_command()
        self.wake_word_detector.start(on_wake_word)
        return True

    def speak(self, text: str, wait: bool = True) -> bool:
        if not text or self.text_to_speech is None:
            return False
        try:
            return bool(self.text_to_speech.speak(text, wait=wait))
        except Exception as exc:
            logger.error("Seslendirme çağrısı başarısız: " + str(exc))
            return False

    def set_voice_enabled(self, enabled: bool):
        """Enable or disable voice components without restarting the GUI."""
        enabled = bool(enabled)
        if not enabled:
            self.voice_enabled = False
            self.stop_listening()
            if self.text_to_speech:
                try:
                    self.text_to_speech.stop()
                except Exception:
                    pass
            return True
        try:
            if self.speech_recognizer is None:
                self.speech_recognizer = SpeechRecognizer()
            if self.text_to_speech is None:
                self.text_to_speech = TextToSpeech()
            self.voice_enabled = True
            return True
        except Exception as exc:
            logger.error("Ses bileşenleri etkinleştirilemedi: " + str(exc))
            self.voice_enabled = False
            return False

    def set_voice_rate(self, rate: int):
        return self.text_to_speech.set_rate(rate) if self.text_to_speech else False

    def set_voice_volume(self, volume: float):
        return self.text_to_speech.set_volume(volume) if self.text_to_speech else False

    def test_microphone(self) -> dict:
        if self.speech_recognizer:
            return self.speech_recognizer.test_microphone()
        return {"success": False, "message": "Ses tanıma motoru başlatılamadı."}

    def get_available_voices(self) -> list:
        return self.text_to_speech.get_voices() if self.text_to_speech else []

    def set_voice(self, voice_id: str) -> bool:
        return bool(self.text_to_speech.set_voice(voice_id)) if self.text_to_speech else False

    def on_command(self, callback: Callable):
        self.on_command_callback = callback

    def on_response(self, callback: Callable):
        self.on_response_callback = callback


_jarvis_instance = None

def get_jarvis() -> Jarvis:
    global _jarvis_instance
    if _jarvis_instance is None:
        _jarvis_instance = Jarvis()
    return _jarvis_instance
