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
