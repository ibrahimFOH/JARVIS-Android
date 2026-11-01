from types import SimpleNamespace

import pytest

from core.ai_brain import AIBrain


class _Response:
    ok = True
    status_code = 200
    text = ""

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": "Kroki metni ve ölçüleri analiz edildi."}]}}]}


def _brain(provider="gemini"):
    brain = AIBrain.__new__(AIBrain)
    brain.provider = provider
    brain.gemini_free_confirmed = True
    brain.gemini_model = AIBrain.FREE_MODELS["gemini"]
    brain.gemini_key = "test-key"
    brain.timeout = 10
    brain.session = SimpleNamespace(post=lambda *args, **kwargs: _Response())
    return brain


def test_image_upload_requires_separate_external_transfer_approval(tmp_path):
    image = tmp_path / "kroki.png"
    image.write_bytes(b"test-image")
    calls = []
    brain = _brain()
    brain.session.post = lambda *args, **kwargs: calls.append((args, kwargs))

    with pytest.raises(RuntimeError, match="ayrıca onaylanmalı"):
        brain.ask_with_images("Krokideki ölçüleri çıkar", [image])

    assert calls == []


def test_confirmed_free_gemini_can_analyze_supported_local_image(tmp_path):
    image = tmp_path / "kroki.png"
    image.write_bytes(b"test-image")
    calls = []
    brain = _brain()
    brain.session.post = lambda *args, **kwargs: (calls.append((args, kwargs)) or _Response())

    result = brain.ask_with_images(
        "Krokideki ölçüleri çıkar",
        [image],
        confirm_external_transfer=True,
    )

    assert "Kroki" in result
    assert len(calls) == 1
    parts = calls[0][1]["json"]["contents"][0]["parts"]
    assert parts[1]["inline_data"]["mime_type"] == "image/png"


def test_image_analysis_is_not_sent_by_non_gemini_provider(tmp_path):
    image = tmp_path / "kroki.png"
    image.write_bytes(b"test-image")
    brain = _brain(provider="ollama")

    with pytest.raises(RuntimeError, match="yalnızca ücretsiz katmanı onaylanmış Gemini"):
        brain.ask_with_images(
            "Krokideki ölçüleri çıkar",
            [image],
            confirm_external_transfer=True,
        )
