"""Windows TTS: prefer a Turkish SAPI voice and keep speech available with a clear fallback."""
import pyttsx3
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()


class TextToSpeech:
    def __init__(self):
        self.engine = None
        self.available = False
        self.rate = config.get("voice.tts_rate", 165)
        self.volume = config.get("voice.tts_volume", 0.9)
        self.turkish_voice_found = False
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)
            voice = config.get("voice.tts_voice", "auto-turkish")
            if voice == "auto-turkish":
                self.turkish_voice_found = self._find_turkish_voice()
                if not self.turkish_voice_found:
                    # Do not disable TTS entirely. Keep startup/status speech alive,
                    # and clearly log that Windows needs a Turkish speech voice installed.
                    logger.error("Turkish SAPI voice not found; Windows default voice is active until Turkish voice is installed.")
            elif voice != "default":
                self._set_voice(voice)
            self.available = True
            logger.info("Windows text-to-speech initialized; Turkish voice=%s", self.turkish_voice_found)
        except Exception as e:
            logger.error("Failed to initialize text-to-speech: " + str(e))
            self.engine = None
            self.available = False

    def _find_turkish_voice(self):
        try:
            voices = self.engine.getProperty("voices") or []
            needles = ("turkish", "tr-tr", "tr_tr", "turk", "türk", "041f", "0x41f")
            for voice in voices:
                languages = getattr(voice, "languages", []) or []
                if not isinstance(languages, (list, tuple)):
                    languages = [languages]
                language_text = " ".join(
                    item.decode("utf-8", "ignore") if isinstance(item, bytes) else str(item)
                    for item in languages
                )
                blob = " ".join((str(getattr(voice, "id", "")),
                                 str(getattr(voice, "name", "")), language_text)).lower()
                if any(term in blob for term in needles):
                    self.engine.setProperty("voice", voice.id)
                    logger.info("Turkish TTS voice selected: %s", voice.name)
                    return True
            logger.warning("Installed Windows TTS voices: %s",
                           [str(getattr(v, "name", getattr(v, "id", ""))) for v in voices])
        except Exception as e:
            logger.warning("Turkish voice scan failed: %s", e)
        return False

    def speak(self, text, wait=True):
        if not self.available or not self.engine or not text:
            logger.error("TTS unavailable; cannot speak.")
            return False
        try:
            self.engine.say(text)
            if wait:
                self.engine.runAndWait()
            return True
        except Exception as e:
            logger.error("Speech error: " + str(e))
            return False

    def stop(self):
        if self.available and self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass

    def set_rate(self, rate):
        self.rate = rate
        if self.engine:
            self.engine.setProperty("rate", rate)

    def set_volume(self, volume):
        self.volume = max(0, min(1, volume))
        if self.engine:
            self.engine.setProperty("volume", self.volume)

    def get_voices(self):
        try:
            return [{"id": v.id, "name": v.name} for v in self.engine.getProperty("voices")] if self.engine else []
        except Exception:
            return []

    def set_voice(self, voice_id):
        return self._set_voice(voice_id)

    def _set_voice(self, voice_id):
        try:
            if not self.engine:
                return False
            for voice in self.engine.getProperty("voices"):
                if voice_id.lower() in str(voice.id).lower() or voice_id.lower() in str(voice.name).lower():
                    self.engine.setProperty("voice", voice.id)
                    return True
        except Exception:
            pass
        return False

    def save_to_file(self, text, filename):
        try:
            if not self.available or not self.engine:
                return False
            self.engine.save_to_file(text, filename)
            self.engine.runAndWait()
            return True
        except Exception:
            return False
