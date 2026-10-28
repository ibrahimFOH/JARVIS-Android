import speech_recognition as sr

from voice.speech_recognition import SpeechRecognizer
from voice.text_to_speech import TextToSpeech


def test_tts_clean_text_does_not_read_markup_punctuation():
    source = "**Merhaba** / test (dünya) [Stagepulse](https://stagepulse.com.tr) \x60kod\x60"
    cleaned = TextToSpeech.clean_text(source)
    assert "Merhaba" in cleaned
    assert "test" in cleaned
    assert "dünya" in cleaned
    assert "Stagepulse" in cleaned
    assert "https://" not in cleaned
    assert "/" not in cleaned
    assert "(" not in cleaned and ")" not in cleaned
    assert "\x60" not in cleaned


def test_missing_microphone_is_reported_without_crashing(monkeypatch):
    def no_microphone(*args, **kwargs):
        raise OSError("no input device")

    monkeypatch.setattr(sr, "Microphone", no_microphone)
    recognizer = SpeechRecognizer()
    result = recognizer.listen()
    assert result["success"] is False
    assert result["error"] == "microphone_unavailable"
    assert "Mikrofon" in result["message"]


def test_microphone_test_does_not_false_pass_when_silent(monkeypatch):
    def no_microphone(*args, **kwargs):
        raise OSError("no input device")

    monkeypatch.setattr(sr, "Microphone", no_microphone)
    recognizer = SpeechRecognizer()
    result = recognizer.test_microphone()
    assert result["success"] is False
    assert "Mikrofon" in result["message"]


def test_recognition_service_error_is_visible(monkeypatch):
    recognizer = SpeechRecognizer.__new__(SpeechRecognizer)
    recognizer.recognizer = sr.Recognizer()
    recognizer.engine = "google"
    recognizer.language = "tr-TR"
    recognizer.last_recognition_error = ""
    monkeypatch.setattr(
        recognizer.recognizer,
        "recognize_google",
        lambda *args, **kwargs: (_ for _ in ()).throw(sr.RequestError("offline")),
    )
    assert recognizer._recognize_audio(object()) is None
    assert "offline" in recognizer.last_recognition_error.lower()


def test_voice_button_pauses_and_resumes_continuous_listening():
    from pathlib import Path

    source_path = Path(__file__).resolve().parents[1] / "gui" / "main_window.py"
    source = source_path.read_text(encoding="utf-8")
    assert '"VOICE INPUT: CONTINUOUS LISTENING PAUSED"' in source
    assert "self.jarvis.stop_listening()" in source
    assert "self.jarvis.process_voice_command()" in source
    assert "self.root.after(600, self._resume_continuous_listening_after_voice)" in source
    assert "CONTINUOUS LISTENING RESUMED" in source
    assert "SÜREKLİ DİNLEME ETKİN; ayrı kayıt başlatılmadı." not in source

def test_continuous_listening_uses_generations_after_rapid_restart():
    import threading
    from core.jarvis import Jarvis

    jarvis = Jarvis.__new__(Jarvis)
    jarvis.voice_enabled = True
    jarvis.speech_recognizer = object()
    jarvis.listening_continuously = False
    jarvis.stop_event = threading.Event()
    jarvis._continuous_lock = threading.Lock()
    jarvis._continuous_generation = 0
    jarvis._command_lock = threading.Lock()

    first_capture = threading.Event()
    release_first = threading.Event()
    second_capture = threading.Event()
    release_second = threading.Event()
    calls_lock = threading.Lock()
    calls = []

    def fake_process_voice_command():
        with jarvis._command_lock:
            with calls_lock:
                calls.append(threading.current_thread().name)
                number = len(calls)
            if number == 1:
                first_capture.set()
                assert release_first.wait(2)
            elif number == 2:
                second_capture.set()
                assert release_second.wait(2)
            return {"success": False, "error": "timeout"}

    jarvis.process_voice_command = fake_process_voice_command

    assert jarvis.start_listening()
    assert first_capture.wait(2)
    jarvis.stop_listening()
    assert jarvis.start_listening()
    release_first.set()
    assert second_capture.wait(2)
    jarvis.stop_listening()
    release_second.set()

    # Let both daemon loops observe their invalidated generation and exit.
    for _ in range(50):
        if len(calls) == 2 and not jarvis.listening_continuously:
            break
        threading.Event().wait(0.02)
    assert len(calls) == 2
    assert not jarvis.listening_continuously

