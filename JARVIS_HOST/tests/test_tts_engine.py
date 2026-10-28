import threading
from unittest.mock import Mock

from voice.text_to_speech import TextToSpeech
from core.update_manager import WindowsUpdateManager


def test_spoken_text_removes_urls_and_markdown_punctuation():
    cleaned = TextToSpeech._clean_spoken_text(
        "# Merhaba Patron\nJARVIS (hazır) https://stagepulse.com.tr/admin/ `kod`"
    )
    assert "stagepulse.com.tr" not in cleaned
    assert "https" not in cleaned
    assert "(" not in cleaned and ")" not in cleaned
    assert "Merhaba" in cleaned and "Patron" in cleaned


def test_speak_rejects_empty_text_without_touching_audio_backend():
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.available = True
    assert tts.speak("   ") is False


def test_synchronous_tts_falls_back_to_windows_sapi_backend():
    tts = TextToSpeech.__new__(TextToSpeech)
    tts.available = True
    tts.engine = object()
    tts.tts_engine = "pyttsx3"
    tts.edge_available = False
    tts.sherpa_available = False
    tts._speak_lock = threading.Lock()
    tts._speak_windows_sync = Mock(return_value=True)

    assert tts._speak_sync("Merhaba Patron") is True
    tts._speak_windows_sync.assert_called_once_with("Merhaba Patron")


def test_windows_versions_compare_all_numeric_components():
    assert WindowsUpdateManager._version_tuple("2026.10.28.400123") > (
        WindowsUpdateManager._version_tuple("2026.10.27.400999")
    )
    assert WindowsUpdateManager._version_tuple("2026.10.28.400123") > (
        WindowsUpdateManager._version_tuple("2026.10.6")
    )
