import base64
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "ai_brain.py"
_SPEC = importlib.util.spec_from_file_location("stagepulse_test_ai_brain", _MODULE_PATH)
_AI_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_AI_MODULE)
AIBrain = _AI_MODULE.AIBrain


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class AIBrainTests(unittest.TestCase):
    def make_brain(self):
        brain = AIBrain()
        brain.gemini_key = "test-api-key"
        brain.provider = "auto"
        brain._instant = lambda _text: None
        brain._web = lambda _query: ""
        return brain

    def test_auto_provider_falls_back_to_ollama(self):
        brain = self.make_brain()
        brain._gemini = Mock(side_effect=RuntimeError("Gemini unavailable"))
        brain._ollama = Mock(return_value="Ollama yanıtı")
        self.assertEqual(brain.ask("Kısa bir test sorusu"), "Ollama yanıtı")
        brain._gemini.assert_called_once()
        brain._ollama.assert_called_once()

    def test_generate_image_uses_interactions_api_and_saves_png(self):
        brain = self.make_brain()
        png_bytes = b"fake-png-payload"
        brain.session.post = Mock(return_value=FakeResponse({
            "output_image": {
                "data": base64.b64encode(png_bytes).decode("ascii"),
                "mime_type": "image/png",
            }
        }))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(Path, "home", return_value=Path(tmp)):
                result = Path(brain.generate_image("Minimal black and gold logo"))
                self.assertTrue(result.is_file())
                self.assertEqual(result.read_bytes(), png_bytes)
                self.assertEqual(result.suffix, ".png")
                self.assertEqual(result.parent.name, "StagepulseJARVIS")
        call = brain.session.post.call_args
        self.assertEqual(call.args[0], "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(call.kwargs["headers"]["x-goog-api-key"], "test-api-key")
        self.assertEqual(call.kwargs["json"]["model"], "gemini-3.1-flash-image")

    def test_generate_image_reports_missing_image(self):
        brain = self.make_brain()
        brain.session.post = Mock(return_value=FakeResponse({"output_text": "Text only"}))
        with self.assertRaisesRegex(RuntimeError, "Gemini görsel üretmedi"):
            brain.generate_image("A black and gold abstract logo")

    def test_invalid_provider_is_rejected(self):
        brain = self.make_brain()
        with self.assertRaises(ValueError):
            brain.configure(provider="unknown")


if __name__ == "__main__":
    unittest.main()
