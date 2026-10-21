"""Windows text-to-speech with Turkish voice enforced for JARVIS."""
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
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)
            voice = config.get("voice.tts_voice", "auto-turkish")
            if voice == "auto-turkish":
                if not self._find_turkish_voice():
                    # Never silently fall back to an English/default voice.
                    logger.error(
                        "Turkish Windows TTS voice is not installed/enabled. "
                        "Install a Turkish speech voice in Windows Settings."
                    )
                    self.engine = None
                    return
            elif voice == "default":
                logger.error("Default TTS voice is disabled; configure auto-turkish instead.")
                self.engine = None
                return
            elif not self._set_voice(voice):
                logger.error("Configured TTS voice was not found: " + str(voice))
                self.engine = None
                return
            self.available = True
            logger.info("Turkish text-to-speech initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Turkish text-to-speech: " + str(e))
            self.engine = None
            self.available = False

    def _find_turkish_voice(self):
        try:
            voices = self.engine.getProperty("voices") or []
            needles = ("turkish", "tr-tr", "tr_tr", "turk", "türk", "tr-tr")
            for voice in voices:
                languages = getattr(voice, "languages", []) or []
                if not isinstance(languages, (list, tuple)):
                    languages = [languages]
                language_text = " ".join(
                    item.decode("utf-8", "ignore") if isinstance(item, bytes) else str(item)
                    for item in languages
                )
                blob = " ".join((
                    str(getattr(voice, "id", "")),
                    str(getattr(voice, "name", "")),
                    language_text,
                )).lower()
                if any(term in blob for term in needles):
                    self.engine.setProperty("voice", voice.id)
                    logger.info("Fixed Turkish TTS voice selected: " + str(voice.name))
                    return True
            logger.error("No Turkish Windows TTS voice found; English fallback is prohibited.")
            return False
        except Exception as e:
            logger.error("Turkish voice scan failed: " + str(e))
            return False

    def speak(self, text, wait=True):
        if not self.available or not self.engine or not text:
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
