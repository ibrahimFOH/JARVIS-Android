# -*- coding: utf-8 -*-
from pathlib import Path
import json, shutil, subprocess, sys, re
from datetime import datetime

ROOT = Path(__file__).resolve().parent
if not (ROOT / "core").exists() or not (ROOT / "voice").exists():
    print("Bu dosyayi C:\\Jarvis\\J.A.R.V.I.S klasorunde calistirin.")
    sys.exit(2)

BACKUP = ROOT / "backup_ai_install" / datetime.now().strftime("%Y%m%d_%H%M%S")
FILES = [
    "core/command_processor.py",
    "voice/speech_recognition.py",
    "voice/text_to_speech.py",
    "config/config.json",
]

def backup():
    for rel in FILES:
        src = ROOT / rel
        if src.exists():
            dst = BACKUP / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    print("[OK] Yedek:", BACKUP)

def update_config():
    p = ROOT / "config/config.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.setdefault("voice", {}).update({
        "recognition_engine": "google",
        "recognition_language": "tr-TR",
        "recognition_timeout": 5,
        "phrase_time_limit": 10,
        "tts_voice": "auto-turkish",
        "tts_rate": 165,
        "tts_volume": 0.9,
        "dynamic_energy_threshold": True
    })
    data.setdefault("personality", {})["address_user_as"] = "Patron"
    data["ai"] = {
        "enabled": True,
        "provider": "openai",
        "model": "gpt-5.6-luna",
        "api_key_env": "OPENAI_API_KEY",
        "max_output_tokens": 500
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK] config/config.json")

AI_BRAIN = '''# -*- coding: utf-8 -*-
import os
import re
import requests
from typing import Dict, Any, Optional
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

class AIBrain:
    def __init__(self):
        self.enabled = bool(config.get("ai.enabled", True))
        self.model = config.get("ai.model", "gpt-5.6-luna")
        self.client = None
        key = os.getenv(config.get("ai.api_key_env", "OPENAI_API_KEY"))
        if self.enabled and key and OpenAI:
            try:
                self.client = OpenAI(api_key=key)
                logger.info("AI brain ready: " + self.model)
            except Exception as e:
                logger.warning("AI brain initialization failed: " + str(e))
        else:
            logger.warning("AI brain unavailable: missing SDK or OPENAI_API_KEY")

    def ask(self, command: str) -> Dict[str, Any]:
        command = (command or "").strip()
        local = self._local(command)
        if local:
            return {"success": True, "response": local, "intent": "ai_local"}

        weather = self._weather(command)
        if weather:
            return {"success": True, "response": weather, "intent": "weather"}

        if not self.client:
            return {
                "success": False,
                "response": "Bu komutu anlayamadım, PATRON. AI bağlantısı kullanılamıyor.",
                "intent": "ai_unavailable"
            }

        try:
            r = self.client.responses.create(
                model=self.model,
                instructions=(
                    "Sen JARVIS'sin. Daima Türkçe konuş. Kullanıcıya PATRON diye hitap et. "
                    "Kısa, doğal ve doğru cevap ver. Bilmediğini uydurma."
                ),
                input=command,
                max_output_tokens=int(config.get("ai.max_output_tokens", 500))
            )
            text = getattr(r, "output_text", None) or str(r)
            return {"success": True, "response": text.strip(), "intent": "ai"}
        except Exception as e:
            logger.error("OpenAI request failed: " + str(e))
            return {
                "success": False,
                "response": "AI bağlantısında sorun oluştu, PATRON: " + str(e),
                "intent": "ai_error"
            }

    def _local(self, c: str) -> Optional[str]:
        c = c.lower().strip()
        if any(x in c for x in [
            "neden ing", "neden ingilizce",
            "neden ingilizce konusuyorsun",
            "neden ingilizce konuşuyorsun"
        ]):
            return "Artık Türkçe konuşuyorum, PATRON. Ses tanıma ve cevap sistemini Türkçeye ayarladım."
        if any(x in c for x in ["merhaba", "selam jarvis"]):
            return "Merhaba PATRON. Hazırım."
        return None

    def _weather(self, c: str) -> Optional[str]:
        low = c.lower()
        if not any(x in low for x in [
            "hava kaç", "hava nasıl", "hava nasil",
            "kaç derece", "kac derece",
            "sıcaklık kaç", "sicaklik kac"
        ]):
            return None

        city = "Hatay"
        for name in [
            "istanbul", "ankara", "izmir", "hatay", "antalya",
            "adana", "gaziantep", "reyhanlı", "reyhanli", "antakya"
        ]:
            if name in low:
                city = name
                break

        try:
            r = requests.get(
                "https://wttr.in/" + city + "?format=j1",
                timeout=8,
                headers={"User-Agent": "JARVIS/2.0"}
            )
            r.raise_for_status()
            x = r.json()["current_condition"][0]
            return (
                f"{city.title()} için sıcaklık {x.get('temp_C', '?')} derece. "
                f"Hissedilen {x.get('FeelsLikeC', '?')} derece."
            )
        except Exception as e:
            logger.warning("Weather request failed: " + str(e))
            return "Hava durumu servisine şu anda ulaşamadım, PATRON."
'''

STT = '''# -*- coding: utf-8 -*-
import speech_recognition as sr
from typing import Optional, Dict
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

class SpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.engine = config.get("voice.recognition_engine", "google")
        self.language = config.get("voice.recognition_language", "tr-TR")
        self.timeout = config.get("voice.recognition_timeout", 5)
        self.phrase_limit = config.get("voice.phrase_time_limit", 10)
        self.recognizer.energy_threshold = config.get("voice.energy_threshold", 4000)
        self.recognizer.dynamic_energy_threshold = config.get("voice.dynamic_energy_threshold", True)
        self.recognizer.pause_threshold = 0.7
        self.recognizer.non_speaking_duration = 0.4
        self._calibrate()

    def _calibrate(self):
        try:
            logger.info("Calibrating microphone for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.info("Calibration complete. Energy threshold: " + str(self.recognizer.energy_threshold))
        except Exception as e:
            logger.warning("Could not calibrate microphone: " + str(e))

    def listen(self, timeout=None, phrase_time_limit=None) -> Dict[str, any]:
        try:
            timeout = self.timeout if timeout is None else timeout
            phrase_limit = self.phrase_limit if phrase_time_limit is None else phrase_time_limit
            with self.microphone as source:
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_limit
                )
            text = self._recognize_audio(audio)
            if text:
                logger.info("Recognized: " + text)
                return {"success": True, "text": text}
            return {
                "success": False,
                "error": "no_recognition",
                "message": "Could not understand audio"
            }
        except sr.WaitTimeoutError:
            return {"success": False, "error": "timeout", "message": "No speech detected"}
        except Exception as e:
            logger.error("Error during speech recognition: " + str(e))
            return {"success": False, "error": "exception", "message": str(e)}

    def _recognize_audio(self, audio: sr.AudioData) -> Optional[str]:
        try:
            if self.engine == "sphinx":
                return self.recognizer.recognize_sphinx(audio)
            return self.recognizer.recognize_google(
                audio, language=self.language, show_all=False
            )
        except sr.UnknownValueError:
            logger.warning("Speech not understood (" + self.language + ")")
            return None
        except sr.RequestError as e:
            logger.error("Speech recognition service error: " + str(e))
            return None
        except Exception as e:
            logger.error("Recognition error: " + str(e))
            return None

    def listen_continuous(self, callback, stop_event):
        logger.info("Starting continuous listening mode")
        with self.microphone as source:
            while not stop_event.is_set():
                try:
                    audio = self.recognizer.listen(
                        source, timeout=1, phrase_time_limit=self.phrase_limit
                    )
                    text = self._recognize_audio(audio)
                    if text and callback:
                        callback(text)
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logger.error("Error in continuous listening: " + str(e))
        logger.info("Stopped continuous listening")

    def test_microphone(self):
        try:
            with self.microphone as source:
                self.recognizer.listen(source, timeout=2, phrase_time_limit=2)
            return {"success": True, "message": "Microphone is working"}
        except sr.WaitTimeoutError:
            return {"success": True, "message": "Microphone is working (no speech detected in test)"}
        except Exception as e:
            return {"success": False, "message": "Microphone test failed: " + str(e)}

    def set_energy_threshold(self, threshold: int):
        self.recognizer.energy_threshold = threshold

    def recalibrate(self):
        self._calibrate()
'''

TTS = '''# -*- coding: utf-8 -*-
import pyttsx3
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

class TextToSpeech:
    def __init__(self):
        try:
            self.engine = pyttsx3.init()
            self.rate = config.get("voice.tts_rate", 165)
            self.volume = config.get("voice.tts_volume", 0.9)
            voice_name = config.get("voice.tts_voice", "auto-turkish")
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)

            if voice_name == "auto-turkish":
                self._select_turkish_voice()
            elif voice_name != "default":
                self._set_voice(voice_name)

            self.available = True
            logger.info("Text-to-speech initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize text-to-speech: " + str(e))
            self.engine = None
            self.available = False

    def _select_turkish_voice(self):
        try:
            voices = self.engine.getProperty("voices")
            for voice in voices:
                raw = (str(voice.id) + " " + str(voice.name) + " " +
                       str(getattr(voice, "languages", ""))).lower()
                if any(k in raw for k in ["turkish", "tr-tr", "tr_tr", "turk", "türk"]):
                    self.engine.setProperty("voice", voice.id)
                    logger.info("Turkish voice selected: " + str(voice.name))
                    return
            logger.warning("No Turkish Windows TTS voice found; using default voice")
        except Exception as e:
            logger.warning("Could not select Turkish voice: " + str(e))

    def speak(self, text: str, wait: bool = True) -> bool:
        if not self.available or not self.engine:
            return False
        try:
            self.engine.say(text)
            if wait:
                self.engine.runAndWait()
            return True
        except Exception as e:
            logger.error("Error during speech: " + str(e))
            return False

    def stop(self):
        if self.available and self.engine:
            try:
                self.engine.stop()
            except Exception:
                pass

    def set_rate(self, rate: int):
        if self.available and self.engine:
            self.engine.setProperty("rate", rate)
            self.rate = rate

    def set_volume(self, volume: float):
        if self.available and self.engine:
            self.engine.setProperty("volume", max(0.0, min(1.0, volume)))
            self.volume = volume

    def get_voices(self):
        if not self.available or not self.engine:
            return []
        return [{"id": v.id, "name": v.name} for v in self.engine.getProperty("voices")]

    def set_voice(self, voice_id: str):
        return self._set_voice(voice_id) if self.available and self.engine else False

    def _set_voice(self, voice_id: str) -> bool:
        try:
            for voice in self.engine.getProperty("voices"):
                if voice_id in voice.id or voice_id.lower() in voice.name.lower():
                    self.engine.setProperty("voice", voice.id)
                    logger.info("Voice set to: " + str(voice.name))
                    return True
            return False
        except Exception as e:
            logger.error("Error setting voice: " + str(e))
            return False

    def save_to_file(self, text: str, filename: str) -> bool:
        if not self.available or not self.engine:
            return False
        try:
            self.engine.save_to_file(text, filename)
            self.engine.runAndWait()
            return True
        except Exception as e:
            logger.error("Error saving speech to file: " + str(e))
            return False
'''

def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print("[OK]", rel)

def patch_command_processor():
    p = ROOT / "core/command_processor.py"
    s = p.read_text(encoding="utf-8")

    if "from core.ai_brain import AIBrain" not in s:
        if "from datetime import datetime" in s:
            s = s.replace(
                "from datetime import datetime",
                "from datetime import datetime\nfrom core.ai_brain import AIBrain",
                1
            )
        else:
            s = "from core.ai_brain import AIBrain\n" + s

    if "self.ai_brain = AIBrain()" not in s:
        marker = "self.response_generator = ResponseGenerator()"
        if marker not in s:
            raise RuntimeError("ResponseGenerator satiri bulunamadi")
        s = s.replace(marker, marker + "\n        self.ai_brain = AIBrain()", 1)

    start = s.find("        # Handle unknown intent")
    end = s.find("        # Validate command", start)

    if start != -1 and end != -1:
        fallback = '''        # Natural-language AI fallback
        if intent == 'unknown' or confidence < 0.3:
            ai_result = self.ai_brain.ask(command)
            if ai_result.get('success'):
                return {
                    'success': True,
                    'response': ai_result.get('response', ''),
                    'intent': ai_result.get('intent', 'ai')
                }

            response = ai_result.get(
                'response',
                self.response_generator.generate('unknown')
            )
            return {
                'success': False,
                'response': response,
                'intent': ai_result.get('intent', 'unknown')
            }

'''
        s = s[:start] + fallback + s[end:]
    else:
        proc_start = s.find("    def process(")
        exec_start = s.find("    def _execute_command(", proc_start)
        if proc_start == -1 or exec_start == -1:
            raise RuntimeError(
                "process() veya _execute_command() bulunamadi. "
                "Yerel command_processor.py beklenenden farkli."
            )

        replacement = '    def process(self, command: str) -> Dict[str, Any]:\n        """\n        Process a command and return response.\n        Unknown or low-confidence commands are sent to the AI brain.\n        """\n        logger.command(command)\n\n        intent_result = self.intent_recognizer.recognize(command)\n        intent = intent_result[\'intent\']\n        confidence = intent_result[\'confidence\']\n        parameters = intent_result[\'parameters\']\n\n        logger.debug(\n            f"Intent: {intent}, Confidence: {confidence:.2f}, Params: {parameters}"\n        )\n\n        # Natural-language AI fallback\n        if intent == \'unknown\' or confidence < 0.3:\n            ai_result = self.ai_brain.ask(command)\n\n            if ai_result.get(\'success\'):\n                return {\n                    \'success\': True,\n                    \'response\': ai_result.get(\'response\', \'\'),\n                    \'intent\': ai_result.get(\'intent\', \'ai\')\n                }\n\n            return {\n                \'success\': False,\n                \'response\': ai_result.get(\n                    \'response\',\n                    self.response_generator.generate(\'unknown\')\n                ),\n                \'intent\': ai_result.get(\'intent\', \'unknown\')\n            }\n\n        # Validate command\n        is_valid, error, warning = self.validator.validate(intent, parameters)\n\n        if not is_valid:\n            response = self.response_generator.generate(\n                \'error\',\n                intent=intent,\n                error=error\n            )\n            return {\n                \'success\': False,\n                \'response\': response,\n                \'intent\': intent\n            }\n\n        # Check if confirmation is required\n        if warning and self.validator.requires_confirmation(intent):\n            return {\n                \'success\': False,\n                \'requires_confirmation\': True,\n                \'intent\': intent,\n                \'parameters\': parameters,\n                \'warning\': warning,\n                \'response\': self.response_generator.generate(\n                    \'confirmation\',\n                    intent=intent,\n                    details=warning\n                )\n            }\n\n        return self._execute_command(intent, parameters)\n'
        s = s[:proc_start] + replacement + "\n" + s[exec_start:]

    p.write_text(s, encoding="utf-8")
    print("[OK] core/command_processor.py -> AI fallback")


def syntax_check():
    targets = [
        "core/ai_brain.py",
        "core/command_processor.py",
        "voice/speech_recognition.py",
        "voice/text_to_speech.py",
    ]
    good = True
    for rel in targets:
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", str(ROOT / rel)],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            print("[OK] syntax:", rel)
        else:
            good = False
            print("[HATA] syntax:", rel)
            print(r.stderr)
    return good

def main():
    print("=== JARVIS AI + TURKCE SES KURULUMU ===")
    backup()
    update_config()
    write("core/ai_brain.py", AI_BRAIN)
    write("voice/speech_recognition.py", STT)
    write("voice/text_to_speech.py", TTS)
    patch_command_processor()

    print("[INFO] OpenAI SDK ve requests guncelleniyor...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "openai", "requests"],
        check=False
    )

    if not syntax_check():
        print("[HATA] Syntax kontrolu basarisiz. Yedek:", BACKUP)
        sys.exit(1)

    print()
    print("=== TAMAMLANDI ===")
    print("AI modeli: gpt-5.6-luna")
    print("Ses tanima: Google / tr-TR")
    print("TTS: otomatik Turkce Windows sesi")
    print("Hava durumu: wttr.in")
    print("Yedek:", BACKUP)
    print()
    print("Baslatmak icin: python main.py")

if __name__ == "__main__":
    main()
