"""Queued Turkish-first speech output with online female voice and offline fallback."""
from __future__ import annotations
import asyncio, os, queue, re, tempfile, threading
from pathlib import Path
from typing import Any
from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

class TextToSpeech:
    """Serialize speech access on one worker thread; prefer Turkish neural voice online."""

    EDGE_VOICES = (
        ("tr-TR-EmelNeural", "Emel (Türkçe kadın, çevrimiçi)"),
        ("tr-TR-AhmetNeural", "Ahmet (Türkçe erkek, çevrimiçi)"),
    )

    def __init__(self):
        self.rate = int(config.get("voice.tts_rate", 165) or 165)
        self.volume = max(0.0, min(1.0, float(config.get("voice.tts_volume", 0.9) or 0.9)))
        self.requested_voice = str(config.get("voice.tts_voice", "auto-turkish") or "auto-turkish")
        self.edge_voice = str(config.get("voice.tts_edge_voice", "tr-TR-EmelNeural") or "tr-TR-EmelNeural")
        preference = str(config.get("voice.tts_engine", "auto") or "auto").lower()
        self.prefer_native = preference in {"native", "sapi", "offline", "pyttsx3_offline"}
        self.available = True
        self._queue = queue.Queue()
        self._native_engine = None
        self._native_init_failed = False
        self._cancel_current = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="JARVIS-TTS-Queue", daemon=True)
        self._worker.start()
        logger.info("TTS kuyruğu başlatıldı; çevrimiçi Türkçe ses ve çevrimdışı yedek hazır.")

    @staticmethod
    def clean_text(text: Any) -> str:
        """Remove markup and punctuation that speech engines tend to read aloud."""
        value = str(text or "")
        value = re.sub(r"\x60{3}.*?\x60{3}", " kod bloğu ", value, flags=re.DOTALL)
        value = re.sub(r"https?://\S+", " bağlantı adresi ", value, flags=re.IGNORECASE)
        value = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", value)
        value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
        value = re.sub(r"\x60([^\x60]*)\x60", r"\1", value)
        value = re.sub(r"[*_#<>]+", " ", value)
        value = re.sub(r"[/\\|]+", " ", value)
        value = re.sub(r"[()[\]{}]", " ", value)
        value = re.sub(r"^\s*[-•]+\s*", "", value, flags=re.MULTILINE)
        return re.sub(r"\s+", " ", value).strip()

    def _worker_loop(self):
        while True:
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                break
            result = False
            try:
                op, payload = task["op"], task.get("payload")
                if op == "say":
                    result = self._speak_text(payload)
                elif op == "voices":
                    result = self._list_voices()
                elif op == "set_voice":
                    result = self._apply_voice(str(payload or ""))
                elif op == "set_rate":
                    result = self._apply_rate(int(payload))
                elif op == "set_volume":
                    result = self._apply_volume(float(payload))
                elif op == "save":
                    result = self._save_native(str(payload["text"]), str(payload["filename"]))
                elif op == "stop":
                    self._stop_engines()
                    result = True
            except Exception as exc:
                logger.error("TTS işlemi başarısız: " + str(exc))
            finally:
                task["result"] = result
                task["done"].set()
                self._queue.task_done()

    def _submit(self, op, payload=None, wait=True, timeout=240):
        if not self.available or not self._worker.is_alive():
            return False
        task = {"op": op, "payload": payload, "done": threading.Event(), "result": False}
        self._queue.put(task)
        if not wait:
            return True
        if not task["done"].wait(timeout):
            logger.error("TTS zaman aşımı: " + op)
            return False
        return task["result"]

    def _speak_text(self, raw_text):
        text = self.clean_text(raw_text)
        if not text:
            return True
        self._cancel_current.clear()
        if not self.prefer_native and self._speak_edge(text):
            return True
        if self._speak_native(text):
            return True
        if self.prefer_native and self._speak_edge(text):
            return True
        logger.error("Hiçbir TTS motoru ses üretemedi.")
        return False

    def _speak_edge(self, text):
        try:
            import edge_tts
            import pygame
            rate_delta = max(-40, min(60, round((self.rate - 165) / 165 * 100)))
            with tempfile.NamedTemporaryFile(prefix="stagepulse-tts-", suffix=".mp3", delete=False) as handle:
                audio_path = Path(handle.name)
            try:
                async def synthesize():
                    communicator = edge_tts.Communicate(
                        text, voice=self.edge_voice, rate=f"{rate_delta:+d}%", volume="+0%"
                    )
                    await communicator.save(str(audio_path))
                asyncio.run(synthesize())
                if not audio_path.is_file() or audio_path.stat().st_size < 512:
                    raise RuntimeError("TTS servisi boş veya eksik ses döndürdü.")
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.stop()
                pygame.mixer.music.load(str(audio_path))
                pygame.mixer.music.set_volume(self.volume)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self._cancel_current.wait(0.04):
                        pygame.mixer.music.stop()
                        return False
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
                logger.info("Türkçe çevrimiçi ses tamamlandı.")
                return True
            finally:
                try:
                    audio_path.unlink(missing_ok=True)
                except OSError:
                    pass
        except Exception as exc:
            logger.warning("Çevrimiçi TTS kullanılamadı; çevrimdışı yedeğe geçiliyor: " + str(exc))
            return False

    def _ensure_native_engine(self):
        if self._native_engine is not None:
            return self._native_engine
        if self._native_init_failed:
            return None
        try:
            import pyttsx3
            self._native_engine = pyttsx3.init(driverName="sapi5" if os.name == "nt" else None)
            self._native_engine.setProperty("rate", self.rate)
            self._native_engine.setProperty("volume", self.volume)
            if self.requested_voice not in ("", "auto-turkish", "default", "tr-TR-EmelNeural", "tr-TR-AhmetNeural"):
                self._apply_voice(self.requested_voice)
            else:
                self._select_turkish_native_voice()
            return self._native_engine
        except Exception as exc:
            self._native_init_failed = True
            self._native_engine = None
            logger.warning("Windows/yerel TTS başlatılamadı: " + str(exc))
            return None

    def _select_turkish_native_voice(self):
        if self._native_engine is None:
            return False
        try:
            for voice in self._native_engine.getProperty("voices") or []:
                info = " ".join((str(getattr(voice, "id", "")), str(getattr(voice, "name", "")),
                                 str(getattr(voice, "languages", "")))).lower()
                if any(token in info for token in ("turkish", "tr-tr", "tr_tr", "turk", "türk")):
                    self._native_engine.setProperty("voice", voice.id)
                    logger.info("Türkçe çevrimdışı ses seçildi: " + str(voice.name))
                    return True
        except Exception as exc:
            logger.warning("Türkçe çevrimdışı ses seçilemedi: " + str(exc))
        return False

    def _speak_native(self, text):
        engine = self._ensure_native_engine()
        if engine is None:
            return False
        try:
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            engine.say(text)
            engine.runAndWait()
            logger.info("Çevrimdışı TTS tamamlandı.")
            return True
        except Exception as exc:
            logger.error("Çevrimdışı konuşma hatası: " + str(exc))
            try:
                engine.stop()
            except Exception:
                pass
            return False

    def _list_voices(self):
        result = [{"id": voice_id, "name": label} for voice_id, label in self.EDGE_VOICES]
        engine = self._ensure_native_engine()
        if engine is not None:
            try:
                result.extend({"id": str(v.id), "name": str(v.name)} for v in (engine.getProperty("voices") or []))
            except Exception as exc:
                logger.warning("Yerel ses listesi alınamadı: " + str(exc))
        return result

    def _apply_voice(self, voice_id):
        for edge_id, _label in self.EDGE_VOICES:
            if voice_id.lower() == edge_id.lower():
                self.edge_voice = edge_id
                self.prefer_native = False
                return True
        engine = self._ensure_native_engine()
        if engine is None:
            return False
        try:
            for voice in engine.getProperty("voices") or []:
                if voice_id == str(voice.id) or voice_id.lower() in str(voice.name).lower():
                    engine.setProperty("voice", voice.id)
                    self.requested_voice = str(voice.id)
                    self.prefer_native = True
                    return True
        except Exception as exc:
            logger.warning("Ses seçimi başarısız: " + str(exc))
        return False

    def _apply_rate(self, rate):
        self.rate = max(80, min(300, int(rate)))
        if self._native_engine is not None:
            self._native_engine.setProperty("rate", self.rate)
        return True

    def _apply_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))
        if self._native_engine is not None:
            self._native_engine.setProperty("volume", self.volume)
        return True

    def _save_native(self, text, filename):
        engine = self._ensure_native_engine()
        if engine is None:
            return False
        try:
            engine.save_to_file(self.clean_text(text), filename)
            engine.runAndWait()
            return Path(filename).is_file() and Path(filename).stat().st_size > 0
        except Exception as exc:
            logger.error("Ses dosyası kaydedilemedi: " + str(exc))
            return False

    def _stop_engines(self):
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        if self._native_engine is not None:
            try:
                self._native_engine.stop()
            except Exception:
                pass

    def speak(self, text, wait=True):
        return self._submit("say", str(text or ""), wait=wait)

    def stop(self):
        self._cancel_current.set()
        return self._submit("stop", wait=True, timeout=5)

    def set_rate(self, rate):
        return self._submit("set_rate", rate, wait=True)

    def set_volume(self, volume):
        return self._submit("set_volume", volume, wait=True)

    def get_voices(self):
        result = self._submit("voices", wait=True, timeout=30)
        return result if isinstance(result, list) else []

    def set_voice(self, voice_id):
        return bool(self._submit("set_voice", voice_id, wait=True, timeout=30))

    def save_to_file(self, text, filename):
        return bool(self._submit("save", {"text": text, "filename": filename}, wait=True))
