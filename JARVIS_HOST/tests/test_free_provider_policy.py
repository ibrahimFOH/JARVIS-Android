"""Ücretli API uç noktalarının kapalı kaldığını doğrulayan regresyon testleri."""

from types import SimpleNamespace

import pytest

from core.ai_brain import AIBrain


def make_brain():
    brain = AIBrain.__new__(AIBrain)
    brain.provider = "ollama"
    brain.gemini_key = ""
    brain.gemini_model = "gemini-3.8-flash"
    brain.groq_key = ""
    brain.groq_model = "openai/gpt-oss-20b"
    brain.gemini_free_confirmed = False
    brain.groq_free_confirmed = False
    brain.host = "http://127.0.0.1:11434"
    brain.model = "qwen3:0.6b"
    brain.api_defaults = {}
    brain.api_keys = {}
    brain.api_models = {}
    brain.api_base_urls = {}
    brain.session = SimpleNamespace(post=lambda *args, **kwargs: None)
    brain._persist_settings = lambda: None
    return brain


@pytest.mark.parametrize(
    "provider",
    ["openai", "grok", "anthropic", "deepseek", "perplexity", "openrouter", "custom"],
)
def test_paid_or_unverified_provider_cannot_be_selected(provider):
    brain = make_brain()

    with pytest.raises(ValueError, match="yalnızca ücretsiz sağlayıcılar"):
        brain.configure(provider=provider)


def test_only_local_and_free_tier_providers_are_allowlisted():
    assert AIBrain.FREE_PROVIDERS == frozenset({"auto", "ollama", "gemini", "groq"})


@pytest.mark.parametrize(
    "provider",
    ["openai", "grok", "anthropic", "deepseek", "perplexity", "openrouter", "custom"],
)
def test_paid_provider_connection_test_is_blocked_without_network(provider):
    brain = make_brain()

    result = brain.test_provider(provider)

    assert result["success"] is False
    assert "engellendi" in result["message"]


def test_generic_api_adapter_cannot_call_paid_or_custom_endpoints():
    brain = make_brain()

    with pytest.raises(RuntimeError, match="Genel/ücretli API uç noktaları devre dışı"):
        brain._compatible_api("openai", "test")


def test_auto_mode_never_falls_back_to_paid_providers(monkeypatch):
    brain = make_brain()
    brain.provider = "auto"
    brain._ollama = lambda _prompt, _context="": "Ollama bağlantısında sorun oluştu: kapalı"
    paid_calls = []

    def forbidden_paid_call(*args, **kwargs):
        paid_calls.append((args, kwargs))
        raise AssertionError("AUTO ücretli sağlayıcıya yönelmemeli")

    monkeypatch.setattr(AIBrain, "_compatible_api", forbidden_paid_call)

    result = brain.ask("Basit bir test yap")

    assert result.startswith("Yapay zekâ yanıtı alınamadı.")
    assert paid_calls == []


def test_configure_accepts_free_provider_and_rejects_paid_key_injection():
    brain = make_brain()

    brain.configure(provider="groq", api_keys={"openai": "must-not-be-used"})

    assert brain.provider == "groq"
    assert brain.api_keys == {}


def test_paid_gemini_or_groq_model_cannot_be_configured():
    brain = make_brain()

    with pytest.raises(ValueError, match="ücretsiz Gemini Flash"):
        brain.configure(gemini_model="gemini-3.8-pro")

    with pytest.raises(ValueError, match="Groq Free Plan"):
        brain.configure(groq_model="llama-3.3-70b-versatile")


@pytest.mark.parametrize("provider", ["gemini", "groq"])
def test_cloud_provider_requires_explicit_free_billing_confirmation(provider):
    brain = make_brain()

    result = brain.test_provider(provider)

    assert result["success"] is False
    assert "isteği gönderilmedi" in result["message"]


def test_gemini_api_is_blocked_before_network_without_free_tier_confirmation(monkeypatch):
    brain = make_brain()
    brain.gemini_key = "test-key"
    calls = []
    monkeypatch.setattr(brain.session, "post", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(RuntimeError, match="faturalandırmanın kapalı olduğu onaylanmalı"):
        brain._gemini_api("test")

    assert calls == []


def test_groq_api_is_blocked_before_network_without_free_plan_confirmation(monkeypatch):
    brain = make_brain()
    brain.groq_key = "test-key"
    calls = []
    monkeypatch.setattr(brain.session, "post", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(RuntimeError, match="Free Plan üzerinde olduğu onaylanmalı"):
        brain._compatible_groq("test")

    assert calls == []


def test_auto_mode_does_not_call_cloud_without_provider_specific_confirmation(monkeypatch):
    brain = make_brain()
    brain.provider = "auto"
    brain.gemini_key = "gemini-test-key"
    brain.groq_key = "groq-test-key"
    brain._ollama = lambda _prompt, _context="": "Ollama bağlantısında sorun oluştu: kapalı"
    cloud_calls = []

    monkeypatch.setattr(
        brain, "_gemini_api",
        lambda *args, **kwargs: cloud_calls.append("gemini"),
    )
    monkeypatch.setattr(
        brain, "_compatible_groq",
        lambda *args, **kwargs: cloud_calls.append("groq"),
    )

    result = brain.ask("Çevrimdışı test")

    assert result.startswith("Yapay zekâ yanıtı alınamadı.")
    assert cloud_calls == []
