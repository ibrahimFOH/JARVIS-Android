"""Turkish-first TTS for JARVIS.

Online default: Microsoft Edge's Turkish neural voice (Emel, female).
Offline options: Turkish Piper models via sherpa-onnx. Piper model files are
downloaded on first explicit use and cached under the current user's profile.
Windows SAPI/pyttsx3 remains the last-resort fallback.
"""
import asyncio
import ctypes
import importlib.util
import os
import shutil
import tempfile
import tarfile
import threading
import time
import wave
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np

from utils.logger import get_logger
from utils.config_manager import get_config

logger = get_logger()
config = get_config()

_EDGE_VOICES = {
    "tr-tr-emelneural": ("tr-TR-EmelNeural", "Emel (Türkçe, kadın, çevrimiçi)"),
    "tr-tr-ahmetneural": ("tr-TR-AhmetNeural", "Ahmet (Türkçe, erkek, çevrimiçi)"),
}
_PIPER_VOICES = {
    "dfki": ("vits-piper-tr_TR-dfki-medium", "DFKI (Türkçe, çevrimdışı)"),
    "fahrettin": ("vits-piper-tr_TR-fahrettin-medium", "Fahrettin (Türkçe, çevrimdışı)"),
    "fettah": ("vits-piper-tr_TR-fettah-medium", "Fettah (Türkçe, çevrimdışı)"),
}
_PIPER_RELEASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models"


class TextToSpeech:
    def __init__(self):
        self.engine = None
        self.available = False
        self.rate = int(config.get("voice.tts_rate", 165))
        self.volume = float(config.get("voice.tts_volume", 0.9))
        self.edge_rate = str(config.get("voice.edge_rate", "+0%"))
        self.edge_voice = "tr-TR-EmelNeural"
        self.piper_voice = str(config.get("voice.piper_voice", "dfki")).lower()
        self.tts_engine = str(config.get("voice.tts_engine", "edge")).lower()
        self._speak_lock = threading.Lock()
        self._piper_engine = None
        self._piper_engine_voice = None
        self.edge_available = importlib.util.find_spec("edge_tts") is not None
        self.sherpa_available = importlib.util.find_spec("sherpa_onnx") is not None

        configured_voice = str(config.get("voice.tts_voice", "auto-turkish"))
        normal_voice = configured_voice.lower().strip()
        if normal_voice in ("", "auto-turkish", "emel", "emelneural", "tr-tr-emelneural"):
            # Upgrade older config files automatically: auto-turkish now means
            # Emel's Turkish neural voice, not the Windows default Tolga voice.
            self.edge_voice = "tr-TR-EmelNeural"
            if self.tts_engine not in ("sherpa-onnx", "piper", "windows", "sapi"):
                self.tts_engine = "edge"
        elif normal_voice in ("ahmet", "ahmetneural", "tr-tr-ahmetneural"):
            self.edge_voice = "tr-TR-AhmetNeural"
            self.tts_engine = "edge"
        elif normal_voice.startswith("piper:"):
            self.piper_voice = normal_voice.split(":", 1)[1]
            self.tts_engine = "sherpa-onnx"
        elif normal_voice in ("default", "windows", "sapi"):
            self.tts_engine = "pyttsx3"
        elif normal_voice.startswith("tr-tr-") and normal_voice.endswith("neural"):
            self.edge_voice = configured_voice
            self.tts_engine = "edge"
        else:
            # Any other configured id/name is treated as a Windows SAPI voice.
            self.tts_engine = "pyttsx3"

        self._init_windows_fallback()
        self.available = bool(
            self.edge_available or self.sherpa_available or self.engine is not None
        )
        logger.info(
            "TTS ready: engine={} edge_available={} sherpa_available={} windows_fallback={} voice={}".format(
                self.tts_engine, self.edge_available, self.sherpa_available,
                self.engine is not None,
                self.edge_voice if self.tts_engine == "edge" else self.piper_voice,
            )
        )

    def _init_windows_fallback(self):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", max(0.0, min(1.0, self.volume)))
            voice_setting = str(config.get("voice.tts_voice", "auto-turkish"))
            if voice_setting.lower() not in (
                "auto-turkish", "emel", "emelneural", "tr-tr-emelneural",
                "ahmet", "ahmetneural", "tr-tr-ahmetneural",
                "default", "windows", "sapi"
            ) and not voice_setting.lower().startswith("piper:"):
                self._set_windows_voice(voice_setting)
            logger.info("Windows SAPI fallback is ready.")
        except Exception as exc:
            self.engine = None
            logger.warning("Windows SAPI fallback unavailable: " + str(exc))

    @staticmethod
    def _cache_root():
        base = os.environ.get("LOCALAPPDATA")
        if base:
            root = Path(base) / "Stagepulse" / "JARVIS" / "tts"
        else:
            root = Path.home() / ".cache" / "stagepulse" / "jarvis" / "tts"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _piper_directory(self, voice=None):
        key = (voice or self.piper_voice or "dfki").lower()
        if key not in _PIPER_VOICES:
            key = "dfki"
        return self._cache_root() / _PIPER_VOICES[key][0]

    def _piper_files_available(self, voice=None):
        name = (voice or self.piper_voice or "dfki").lower()
        directory = self._piper_directory(name)
        return (
            (directory / f"tr_TR-{name}-medium.onnx").is_file()
            and (directory / "tokens.txt").is_file()
            and (directory / "espeak-ng-data").is_dir()
        )

    def _ensure_piper_model(self, voice):
        voice = voice.lower()
        if voice not in _PIPER_VOICES:
            raise ValueError("Bilinmeyen Türkçe Piper sesi: " + voice)
        directory = self._piper_directory(voice)
        model_file = directory / f"tr_TR-{voice}-medium.onnx"
        if model_file.is_file() and (directory / "tokens.txt").is_file() and (directory / "espeak-ng-data").is_dir():
            return directory
        if not self.sherpa_available:
            raise RuntimeError(
                "Çevrimdışı Piper sesi için sherpa-onnx kurulmamış. "
                "JARVIS_HOST/requirements.txt içindeki bağımlılıkları yükleyin."
            )

        cache = self._cache_root()
        archive_name = f"vits-piper-tr_TR-{voice}-medium.tar.bz2"
        archive_path = cache / archive_name
        url = f"{_PIPER_RELEASE}/{archive_name}"
        temporary_archive = archive_path.with_suffix(archive_path.suffix + ".part")
        logger.info("Downloading Turkish offline TTS model " + voice + " from " + url)
        request = Request(url, headers={"User-Agent": "JARVIS-Stagepulse/1.0"})
        try:
            with urlopen(request, timeout=45) as response, open(temporary_archive, "wb") as target:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
            if temporary_archive.stat().st_size < 1_000_000:
                raise RuntimeError("İndirilen Türkçe ses modeli beklenenden küçük; indirme tamamlanmamış olabilir.")
            os.replace(temporary_archive, archive_path)

            root_resolved = cache.resolve()
            with tarfile.open(archive_path, "r:bz2") as bundle:
                members = bundle.getmembers()
                for member in members:
                    # Avoid extracting links or paths outside the TTS cache.
                    if member.issym() or member.islnk():
                        raise RuntimeError("Ses modelinin arşivinde güvenilmeyen bağlantı bulundu.")
                    destination = (cache / member.name).resolve()
                    if os.path.commonpath((str(root_resolved), str(destination))) != str(root_resolved):
                        raise RuntimeError("Ses modeli arşivinde geçersiz dosya yolu bulundu.")
                bundle.extractall(cache)
            try:
                archive_path.unlink()
            except OSError:
                pass
            if not (model_file.is_file() and (directory / "tokens.txt").is_file() and (directory / "espeak-ng-data").is_dir()):
                raise RuntimeError("Model indirildi ancak gerekli ONNX/tokens/espeak dosyaları bulunamadı.")
            logger.info("Turkish offline TTS model installed: " + str(directory))
            return directory
        except Exception:
            for candidate in (temporary_archive, archive_path):
                try:
                    candidate.unlink()
                except OSError:
                    pass
            raise

    def _speak_edge_sync(self, text):
        import edge_tts

        fd, output_path = tempfile.mkstemp(prefix="jarvis_tts_", suffix=".mp3")
        os.close(fd)
        try:
            level = max(0, min(100, int(round(self.volume * 100))))
            edge_volume = f"{level - 100:+d}%"

            async def synthesize():
                communicator = edge_tts.Communicate(
                    text,
                    voice=self.edge_voice,
                    rate=self.edge_rate,
                    volume=edge_volume,
                )
                await communicator.save(output_path)

            asyncio.run(synthesize())
            if not os.path.isfile(output_path) or os.path.getsize(output_path) < 512:
                raise RuntimeError("Türkçe çevrimiçi TTS boş ses dosyası döndürdü.")
            self._play_mp3_windows(output_path)
            return True
        finally:
            try:
                os.remove(output_path)
            except OSError:
                pass

    @staticmethod
    def _play_mp3_windows(path):
        if os.name != "nt":
            raise RuntimeError("Edge MP3 oynatımı şu anda Windows masaüstü için yapılandırıldı.")
        winmm = ctypes.WinDLL("winmm")
        winmm.mciSendStringW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p
        ]
        winmm.mciSendStringW.restype = ctypes.c_uint
        winmm.mciGetErrorStringW.argtypes = [
            ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint
        ]
        winmm.mciGetErrorStringW.restype = ctypes.c_int
        alias = "jarvis_tts_" + str(threading.get_ident())
        open_cmd = f'open "{str(Path(path).resolve())}" type mpegvideo alias {alias}'
        code = winmm.mciSendStringW(open_cmd, None, 0, None)
        if code:
            buffer = ctypes.create_unicode_buffer(256)
            winmm.mciGetErrorStringW(code, buffer, len(buffer))
            raise RuntimeError("Windows MP3 oynatımı açılamadı: " + buffer.value)
        try:
            code = winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
            if code:
                buffer = ctypes.create_unicode_buffer(256)
                winmm.mciGetErrorStringW(code, buffer, len(buffer))
                raise RuntimeError("Windows MP3 oynatımı başarısız: " + buffer.value)
        finally:
            winmm.mciSendStringW(f"close {alias}", None, 0, None)

    def _speak_piper_sync(self, text, voice=None):
        if os.name != "nt":
            raise RuntimeError("Piper WAV oynatımı şu anda Windows masaüstü için yapılandırıldı.")
        import sherpa_onnx
        import winsound

        voice = (voice or self.piper_voice or "dfki").lower()
        directory = self._ensure_piper_model(voice)
        if self._piper_engine is None or self._piper_engine_voice != voice:
            model = directory / f"tr_TR-{voice}-medium.onnx"
            tts_config = sherpa_onnx.OfflineTtsConfig(
                model=sherpa_onnx.OfflineTtsModelConfig(
                    vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                        model=str(model),
                        tokens=str(directory / "tokens.txt"),
                        data_dir=str(directory / "espeak-ng-data"),
                    ),
                    num_threads=1,
                ),
            )
            if not tts_config.validate():
                raise RuntimeError("Piper Türkçe TTS modeli doğrulanamadı.")
            self._piper_engine = sherpa_onnx.OfflineTts(tts_config)
            self._piper_engine_voice = voice

        speed = max(0.75, min(1.3, self.rate / 165.0))
        audio = self._piper_engine.generate(text=text, sid=0, speed=speed)
        if len(audio.samples) == 0:
            raise RuntimeError("Piper Türkçe TTS ses üretemedi.")
        samples = np.asarray(audio.samples, dtype=np.float32)
        pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2").tobytes()
        fd, wav_path = tempfile.mkstemp(prefix="jarvis_tts_", suffix=".wav")
        os.close(fd)
        try:
            with wave.open(wav_path, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(int(audio.sample_rate))
                wav.writeframes(pcm)
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_SYNC)
            return True
        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass

    def _speak_windows_sync(self, text):
        if not self.engine:
            raise RuntimeError("Windows konuşma motoru kullanılamıyor.")
        self.engine.say(text)
        self.engine.runAndWait()
        return True

    def _speak_sync(self, text):
        if not text:
            return False
        with self._speak_lock:
            # Preferred voice first.
            if self.tts_engine in ("sherpa-onnx", "piper"):
                try:
                    return self._speak_piper_sync(text)
                except Exception as exc:
                    logger.warning("Offline Piper TTS failed; trying online Turkish voice: " + str(exc))
                    if self.edge_available:
                        try:
                            return self._speak_edge_sync(text)
                        except Exception as edge_exc:
                            logger.warning("Online Turkish TTS fallback failed: " + str(edge_exc))
            elif self.tts_engine in ("edge", "edge-tts", "auto"):
                if self.edge_available:
                    try:
                        return self._speak_edge_sync(text)
                    except Exception as exc:
                        logger.warning("Online Turkish TTS failed; trying available local voice: " + str(exc))
                # Avoid an unexpected 60+ MB download just because the internet TTS
                # service is temporarily unavailable. Use a cached Piper model only.
                if self.sherpa_available:
                    for candidate in (self.piper_voice, "dfki", "fahrettin", "fettah"):
                        if candidate in _PIPER_VOICES and self._piper_files_available(candidate):
                            try:
                                return self._speak_piper_sync(text, candidate)
                            except Exception as exc:
                                logger.warning("Cached Piper fallback failed: " + str(exc))
                                break
            # SAPI/Tolga fallback. If the Turkish neural service is unavailable,
            # this preserves speech instead of making JARVIS silent.
            try:
                return self._speak_windows_sync(text)
            except Exception as exc:
                logger.error("All TTS backends failed: " + str(exc))
                return False

    def speak(self, text, wait=True):
        if not self.available or not text:
            logger.error("TTS unavailable; cannot speak.")
            return False
        if wait:
            return self._speak_sync(str(text))
        threading.Thread(
            target=self._speak_sync,
            args=(str(text),),
            daemon=True,
            name="JARVIS-TTS-Playback",
        ).start()
        return True

    def stop(self):
        try:
            if self.engine:
                self.engine.stop()
        except Exception:
            pass

    def set_rate(self, rate):
        self.rate = int(rate)
        if self.engine:
            try:
                self.engine.setProperty("rate", self.rate)
            except Exception:
                pass

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))
        if self.engine:
            try:
                self.engine.setProperty("volume", self.volume)
            except Exception:
                pass

    def get_voices(self):
        voices = [
            {"id": "tr-TR-EmelNeural", "name": "Emel (Türkçe, kadın, çevrimiçi)"},
            {"id": "tr-TR-AhmetNeural", "name": "Ahmet (Türkçe, erkek, çevrimiçi)"},
            {"id": "piper:dfki", "name": "DFKI (Türkçe / Offline; ilk kullanımda indirilir)"},
            {"id": "piper:fahrettin", "name": "Fahrettin (Türkçe / Offline; ilk kullanımda indirilir)"},
            {"id": "piper:fettah", "name": "Fettah (Türkçe / Offline; ilk kullanımda indirilir)"},
        ]
        try:
            if self.engine:
                voices.extend(
                    {"id": "windows:" + str(v.id), "name": "Windows: " + str(v.name)}
                    for v in self.engine.getProperty("voices") or []
                )
        except Exception:
            pass
        return voices

    def set_voice(self, voice_id):
        value = str(voice_id or "").strip()
        lowered = value.lower()
        if lowered in _EDGE_VOICES:
            self.edge_voice = _EDGE_VOICES[lowered][0]
            self.tts_engine = "edge"
            config.set("voice.tts_voice", self.edge_voice)
            config.set("voice.tts_engine", "edge")
            return True
        if lowered.startswith("piper:"):
            key = lowered.split(":", 1)[1]
            if key not in _PIPER_VOICES:
                return False
            self.piper_voice = key
            self.tts_engine = "sherpa-onnx"
            config.set("voice.tts_voice", "piper:" + key)
            config.set("voice.piper_voice", key)
            config.set("voice.tts_engine", "sherpa-onnx")
            return True
        if lowered.startswith("windows:"):
            value = value.split(":", 1)[1]
        if self._set_windows_voice(value):
            self.tts_engine = "pyttsx3"
            config.set("voice.tts_voice", value)
            config.set("voice.tts_engine", "pyttsx3")
            return True
        return False

    def _set_windows_voice(self, voice_id):
        try:
            if not self.engine:
                return False
            wanted = str(voice_id).lower()
            for voice in self.engine.getProperty("voices") or []:
                if wanted in str(voice.id).lower() or wanted in str(voice.name).lower():
                    self.engine.setProperty("voice", voice.id)
                    return True
        except Exception as exc:
            logger.warning("Could not set Windows voice: " + str(exc))
        return False

    def save_to_file(self, text, filename):
        if not text:
            return False
        # Generate with Piper without playback when explicitly configured. Online
        # Edge TTS keeps the generated MP3 so it can be used as a normal audio file.
        if self.tts_engine in ("sherpa-onnx", "piper"):
            try:
                import sherpa_onnx
                directory = self._ensure_piper_model(self.piper_voice)
                model = directory / f"tr_TR-{self.piper_voice}-medium.onnx"
                cfg = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                            model=str(model), tokens=str(directory / "tokens.txt"),
                            data_dir=str(directory / "espeak-ng-data"),
                        ),
                        num_threads=1,
                    ),
                )
                audio = sherpa_onnx.OfflineTts(cfg).generate(text=str(text), sid=0, speed=1.0)
                with wave.open(str(filename), "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(int(audio.sample_rate))
                    wav.writeframes(np.clip(np.asarray(audio.samples) * 32767, -32768, 32767).astype("<i2").tobytes())
                return True
            except Exception as exc:
                logger.error("Could not save Piper speech to file: " + str(exc))
                return False
        if self.engine and self.tts_engine == "pyttsx3":
            try:
                self.engine.save_to_file(str(text), filename)
                self.engine.runAndWait()
                return True
            except Exception as exc:
                logger.error("Could not save Windows TTS to file: " + str(exc))
        return False
