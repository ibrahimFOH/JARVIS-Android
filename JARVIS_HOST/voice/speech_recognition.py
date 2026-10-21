"""Turkish-first Windows speech recognition with explicit microphone diagnostics and bounded waits."""
import speech_recognition as sr
from typing import Optional, Dict, Any
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()


class SpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.engine = config.get("voice.recognition_engine", "google")
        self.language = config.get("voice.recognition_language", "tr-TR")
        self.timeout = float(config.get("voice.recognition_timeout", 5))
        self.phrase_limit = float(config.get("voice.phrase_time_limit", 8))
        self.recognizer.energy_threshold = config.get("voice.energy_threshold", 4000)
        self.recognizer.dynamic_energy_threshold = config.get("voice.dynamic_energy_threshold", True)
        # SpeechRecognition uses this for remote recognition requests too.
        self.recognizer.operation_timeout = float(config.get("voice.recognition_operation_timeout", 12))
        self.microphone = None
        self.microphone_error = None
        self._select_microphone()

    def _select_microphone(self):
        """Prefer the Windows default input; if unavailable, select the first listed device."""
        try:
            self.microphone = sr.Microphone()
            logger.info("Using Windows default microphone.")
        except Exception as default_error:
            logger.warning("Default microphone unavailable: %s", default_error)
            try:
                names = sr.Microphone.list_microphone_names()
                logger.info("Available microphone devices: %s", names)
                for index, name in enumerate(names):
                    if not name or not str(name).strip():
                        continue
                    try:
                        self.microphone = sr.Microphone(device_index=index)
                        logger.info("Using microphone device %s: %s", index, name)
                        break
                    except Exception as device_error:
                        logger.warning("Microphone device %s failed: %s", name, device_error)
            except Exception as listing_error:
                logger.error("Could not enumerate microphones: %s", listing_error)
            if self.microphone is None:
                self.microphone_error = (
                    "Windows mikrofonuna erişilemiyor. Ayarlar > Gizlilik ve güvenlik > "
                    "Mikrofon bölümünde erişimi ve masaüstü uygulamalarının erişimini açın; "
                    "Ayarlar > Sistem > Ses > Giriş bölümünde çalışan bir mikrofon seçin. "
                    "Teknik ayrıntı: " + str(default_error)
                )
                logger.error(self.microphone_error)
                return
        self._calibrate()

    def _calibrate(self):
        if self.microphone is None:
            return
        try:
            logger.info("Calibrating microphone for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
            logger.info("Microphone calibration complete; threshold=%s", self.recognizer.energy_threshold)
        except Exception as exc:
            self.microphone_error = "Mikrofon açıldı ancak kalibrasyon başarısız: " + str(exc)
            logger.warning(self.microphone_error)

    def listen(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> Dict[str, Any]:
        if self.microphone is None:
            return {"success": False, "error": "microphone_unavailable",
                    "message": self.microphone_error or "Mikrofon aygıtı bulunamadı."}
        try:
            with self.microphone as source:
                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=self.timeout if timeout is None else timeout,
                        phrase_time_limit=self.phrase_limit if phrase_time_limit is None else phrase_time_limit
                    )
                except sr.WaitTimeoutError:
                    return {"success": False, "error": "timeout",
                            "message": "Ses algılanmadı. Mikrofon girişini ve ses seviyesini kontrol edin."}
            text = self._recognize_audio(audio)
            if text:
                logger.info("Recognized Turkish speech: %s", text)
                return {"success": True, "text": text}
            return {"success": False, "error": "no_recognition",
                    "message": "Konuşma anlaşılamadı. İnternet bağlantısını ve Türkçe konuşmayı kontrol edin."}
        except Exception as exc:
            logger.exception("Speech recognition failed")
            message = str(exc)
            if "device" in message.lower() or "microphone" in message.lower() or "input" in message.lower():
                message = "Mikrofon açılamadı. Windows Ses > Giriş bölümünde doğru aygıtı seçin. Ayrıntı: " + message
            return {"success": False, "error": "microphone_or_audio_error", "message": message}

    def _recognize_audio(self, audio):
        try:
            if self.engine == "sphinx":
                return self.recognizer.recognize_sphinx(audio)
            # Explicitly lock cloud recognition to Turkish.
            return self.recognizer.recognize_google(audio, language=self.language)
        except sr.UnknownValueError:
            return None
        except sr.RequestError as exc:
            logger.error("Speech recognition service error: %s", exc)
            return None
        except Exception as exc:
            logger.exception("Speech recognition error: %s", exc)
            return None

    def test_microphone(self):
        if self.microphone is None:
            return {"success": False, "message": self.microphone_error or "Mikrofon aygıtı bulunamadı."}
        try:
            with self.microphone as source:
                self.recognizer.listen(source, timeout=2, phrase_time_limit=2)
            return {"success": True, "message": "Mikrofon çalışıyor"}
        except sr.WaitTimeoutError:
            return {"success": True, "message": "Mikrofon açıldı; test sırasında ses algılanmadı"}
        except Exception as exc:
            return {"success": False, "message": "Mikrofon testi başarısız: " + str(exc)}

    def set_energy_threshold(self, threshold: int):
        self.recognizer.energy_threshold = threshold

    def recalibrate(self):
        self._calibrate()
