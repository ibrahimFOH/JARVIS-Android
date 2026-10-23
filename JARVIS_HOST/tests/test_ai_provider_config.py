from core.ai_brain import AIBrain


def fresh_brain(tmp_path, monkeypatch):
    monkeypatch.setattr(
        AIBrain, "_settings_file",
        staticmethod(lambda: tmp_path / "ai_settings.json")
    )
    return AIBrain()


def test_ollama_remains_the_default_provider(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    assert brain.provider == "ollama"
    assert brain.host == "http://127.0.0.1:11434"
    assert brain.model == "qwen3:0.6b"


def test_expected_optional_providers_are_available(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    expected = {
        "openai", "grok", "anthropic", "deepseek",
        "perplexity", "openrouter", "custom",
    }
    assert expected <= set(brain.api_defaults)
    assert {"auto", "gemini", "groq", "ollama"} <= {
        "auto", "gemini", "groq", "ollama", *brain.api_defaults
    }


def test_provider_settings_persist_and_reload(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.configure(
        provider="openai",
        api_keys={"openai": "not-a-real-secret"},
        api_models={"openai": "test-model"},
        api_base_urls={"openai": "https://example.invalid/v1"},
    )
    saved = (tmp_path / "ai_settings.json").read_text(encoding="utf-8")
    assert '"provider": "openai"' in saved
    reloaded = fresh_brain(tmp_path, monkeypatch)
    assert reloaded.provider == "openai"
    assert reloaded.api_keys["openai"] == "not-a-real-secret"
    assert reloaded.api_models["openai"] == "test-model"
    assert reloaded.api_base_urls["openai"] == "https://example.invalid/v1"


def test_openai_compatible_provider_uses_selected_url_model_and_key(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.api_keys["openai"] = "test-secret"
    brain.api_models["openai"] = "unit-test-model"
    brain.api_base_urls["openai"] = "https://example.invalid/v1"

    class Response:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "Yanıt tamam"}}]}

    class Session:
        call = None

        def post(self, url, **kwargs):
            self.call = (url, kwargs)
            return Response()

    session = Session()
    brain.session = session
    assert brain._compatible_api("openai", "test prompt") == "Yanıt tamam"
    assert session.call[0] == "https://example.invalid/v1/chat/completions"
    assert session.call[1]["json"]["model"] == "unit-test-model"
    assert session.call[1]["headers"]["Authorization"] == "Bearer test-secret"


def test_auto_provider_connection_check_rejects_ollama_failure(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    monkeypatch.setattr(
        brain, "ask",
        lambda _prompt: "Ollama bağlantısında sorun oluştu."
    )
    result = brain.test_provider("auto")
    assert result["success"] is False


def test_auto_provider_connection_check_accepts_a_real_response(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    monkeypatch.setattr(brain, "ask", lambda _prompt: "Bağlantı başarılı")
    result = brain.test_provider("auto")
    assert result["success"] is True


def test_groq_missing_key_reports_failure_without_network(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    result = brain.test_provider("groq")
    assert result["success"] is False
    assert "anahtarı boş" in result["message"].lower()


def test_turkish_profile_quick_response_is_preserved(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    answer = brain.ask("Ben kimim?")
    assert "İbrahim Kavasoğlu" in answer
    assert "Stagepulse" in answer
