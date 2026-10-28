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
        self.recognizer.energy_threshold = min(float(config.get("voice.energy_threshold", 300)), 1000.0)
        self.recognizer.dynamic_energy_threshold = config.get("voice.dynamic_energy_threshold", True)
        self.recognizer.pause_threshold = float(config.get("voice.pause_threshold", 0.7))
        # SpeechRecognition uses this for remote recognition requests too.
        self.recognizer.operation_timeout = float(config.get("voice.recognition_operation_timeout", 12))
        self.microphone = None
        self.microphone_error = None
        self._select_microphone()

    def _select_microphone(self):
        """Probe devices by actually opening their input stream before selecting one."""
        def try_device(candidate, label):
            try:
                with candidate as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.35)
                self.microphone = candidate
                self.microphone_error = None
                logger.info("Microphone input stream opened successfully: " + str(label))
                return True
            except Exception as exc:
                logger.warning("Microphone probe failed for " + str(label) + ": " + str(exc))
                return False

        try:
            default_device = sr.Microphone()
        except Exception as exc:
            default_device = None
            logger.warning("Windows default microphone unavailable: " + str(exc))
        if default_device is not None and try_device(default_device, "Windows default"):
            return

        try:
            names = sr.Microphone.list_microphone_names()
        except Exception as exc:
            names = []
            logger.warning("Could not enumerate microphone devices: " + str(exc))

        for index, name in enumerate(names):
            if not name or not str(name).strip():
                continue
            try:
                candidate = sr.Microphone(device_index=index)
            except Exception as exc:
                logger.debug("Skipping input device " + str(name) + ": " + str(exc))
                continue
            if try_device(candidate, str(index) + ": " + str(name)):
                return

        self.microphone = None
        self.microphone_error = (
            "Kullanılabilir mikrofon açılamadı. Windows Ayarlar > Sistem > Ses > Giriş bölümünde "
            "doğru aygıtı seçin; Gizlilik ve güvenlik > Mikrofon altında masaüstü uygulamalarına "
            "erişimi açın. Mikrofonu başka bir uygulama kullanıyorsa o uygulamayı kapatın."
        )
        logger.error(self.microphone_error)

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
            # Keep network/API failures distinct from an unclear recording so the GUI
            # can tell the user why cloud recognition failed.
            logger.error("Speech recognition service/network error: %s", exc)
            raise RuntimeError(
                "Türkçe ses tanıma servisine bağlanılamadı. İnternet bağlantısını "
                "kontrol edin; güvenlik duvarı veya servis geçici olarak engelliyor olabilir. "
                "Ayrıntı: " + str(exc)
            ) from exc
        except Exception as exc:
            logger.exception("Speech recognition error: %s", exc)
            raise RuntimeError("Ses tanıma hatası: " + str(exc)) from exc

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
