import builtins
import pytest

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


def test_personal_profile_is_not_hardcoded_in_source(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    answer = brain.ask("Ben kimim?")
    assert "kişisel profil bilgileri kaynak koda sabitlenmiyor" in answer.lower()
    assert "İbrahim Kavasoğlu" not in answer


def test_onefile_first_launch_finds_bundled_turkish_default_config(tmp_path, monkeypatch):
    import json
    import utils.config_manager as config_module

    bundle = tmp_path / "_MEIPASS"
    bundled_config = bundle / "config" / "config.example.json"
    bundled_config.parent.mkdir(parents=True)
    bundled_config.write_text(
        json.dumps({
            "voice": {"enabled": True, "recognition_language": "tr-TR"},
            "personality": {"language": "tr-TR"},
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "_MEIPASS", str(bundle), raising=False)
    writable_path = tmp_path / "release" / "config" / "config.json"
    config = config_module.ConfigManager(str(writable_path))
    assert writable_path.is_file()
    assert config.get("voice.recognition_language") == "tr-TR"
    assert config.get("personality.language") == "tr-TR"


def test_legacy_api_provider_settings_are_preserved(tmp_path, monkeypatch):
    import utils.config_manager as config_module

    legacy_ai = {
        "provider": "openai",
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:0.6b",
        "providers": {
            "gemini": {"api_key": "legacy-gemini-key", "model": "gemini-legacy"},
            "openai": {
                "api_key": "legacy-openai-key",
                "base_url": "https://example.invalid/v1/chat/completions",
                "model": "legacy-model",
            },
        },
    }

    class LegacyConfig:
        def get(self, key, default=None):
            return legacy_ai if key == "ai" else default

    monkeypatch.setattr(config_module, "get_config", lambda: LegacyConfig())
    monkeypatch.setattr(
        AIBrain, "_settings_file",
        staticmethod(lambda: tmp_path / "no-settings-yet.json")
    )
    brain = AIBrain()
    assert brain.provider == "openai"
    assert brain.gemini_key == "legacy-gemini-key"
    assert brain.api_keys["openai"] == "legacy-openai-key"
    assert brain.api_models["openai"] == "legacy-model"
    assert brain.api_base_urls["openai"] == "https://example.invalid/v1"


def test_auto_provider_uses_configured_groq_fallback(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.provider = "auto"
    brain.groq_key = "test-key"
    monkeypatch.setattr(
        brain, "_ollama",
        lambda _prompt, _context="": "Ollama bağlantısında sorun oluştu: sunucu kapalı",
    )
    monkeypatch.setattr(
        brain, "_compatible_groq",
        lambda _prompt, _context="": "Türkçe yedek yanıt",
    )
    assert brain.ask("Bir test sorusu") == "Türkçe yedek yanıt"


def test_repository_manager_add_commit_and_status(tmp_path):
    import subprocess
    from core.agent_tools import RepositoryManager

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "jarvis-test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "JARVIS Test"], check=True)
    manager = RepositoryManager(settings_path=tmp_path / "repository.json")
    bound = manager.bind(str(repo))
    assert bound["success"] is True
    (repo / "sample.txt").write_text("Stagepulse test", encoding="utf-8")
    add_pending = manager.handle_command("git add .")
    assert add_pending["success"] is False
    assert add_pending["requires_confirmation"] is True
    added = manager.handle_command("git add .", confirmed=True)
    assert added["success"] is True
    commit_pending = manager.handle_command("git commit Initial test commit")
    assert commit_pending["success"] is False
    assert commit_pending["requires_confirmation"] is True
    committed = manager.handle_command("git commit Initial test commit", confirmed=True)
    assert committed["success"] is True
    status = manager.handle_command("git status")
    assert status["success"] is True
    assert "sample.txt" not in status["response"]


def test_repository_manager_refuses_pull_with_uncommitted_files(tmp_path):
    import subprocess
    from core.agent_tools import RepositoryManager

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    manager = RepositoryManager(settings_path=tmp_path / "repository.json")
    assert manager.bind(str(repo))["success"] is True
    (repo / "untracked.txt").write_text("keep me", encoding="utf-8")
    pending = manager.handle_command("git pull")
    assert pending["requires_confirmation"] is True
    result = manager.handle_command("git pull", confirmed=True)
    assert result["success"] is False
    assert "Yerel değişiklikler var" in result["response"]


def test_phone_manager_parses_a_number_without_calling_automatically():
    from core.agent_tools import PhoneManager

    phone = PhoneManager()
    phone._dial = lambda number: {"success": True, "response": number}
    result = phone.handle_command("ara +90 532 123 4567")
    assert result["success"] is True
    assert result["response"] == "+905321234567"

def test_explicit_provider_does_not_silently_fallback_to_another_service(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.provider = "ollama"
    brain.groq_key = "test-key"
    calls = []
    monkeypatch.setattr(
        brain, "_ollama",
        lambda *_args, **_kwargs: "Ollama bağlantısında sorun oluştu: offline"
    )
    monkeypatch.setattr(
        brain, "_compatible_groq",
        lambda *_args, **_kwargs: calls.append("groq") or "cloud answer"
    )

    answer = brain.ask("Bu teknik metnin ana fikrini açıkla.")

    assert answer.startswith("Yapay zekâ yanıtı alınamadı.")
    assert calls == []

def test_default_config_path_does_not_depend_on_current_working_directory(tmp_path, monkeypatch):
    import utils.config_manager as config_module

    monkeypatch.setattr(config_module.sys, "frozen", False, raising=False)
    expected_source_path = config_module.ConfigManager._default_config_path()
    monkeypatch.chdir(tmp_path)
    assert config_module.ConfigManager._default_config_path() == expected_source_path

    exe = tmp_path / "installed" / "StagepulseJARVIS.exe"
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "executable", str(exe), raising=False)
    assert config_module.ConfigManager._default_config_path() == (
        tmp_path / "installed" / "config" / "config.json"
    )

def test_default_cloud_models_use_current_model_aliases(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    assert brain.gemini_model == "gemini-3.8-flash"
    assert brain.api_defaults["openai"][1] == "gpt-6-luna"
    assert brain.api_defaults["grok"][1] == "grok-4.7"
    assert brain.api_defaults["anthropic"][1] == "claude-sonnet-4-6"
    assert brain.api_defaults["deepseek"][1] == "deepseek-flash"
    assert brain.api_defaults["openrouter"][1] == "openai/gpt-6-luna"


def test_legacy_cloud_model_aliases_migrate_to_current_defaults(tmp_path, monkeypatch):
    import json

    settings_path = tmp_path / "ai_settings.json"
    settings_path.write_text(json.dumps({
        "provider": "openai",
        "api_models": {
            "openai": "gpt-4.1-mini",
            "grok": "grok-4.1",
            "openrouter": "openai/gpt-4.1-mini",
        },
        "api_keys": {},
    }), encoding="utf-8")
    monkeypatch.setattr(AIBrain, "_settings_file", staticmethod(lambda: settings_path))

    brain = AIBrain()

    assert brain.api_models["openai"] == "gpt-6-luna"
    assert brain.api_models["grok"] == "grok-4.7"
    assert brain.api_models["openrouter"] == "openai/gpt-6-luna"

def test_dpapi_failure_does_not_fall_back_to_plaintext(monkeypatch):
    original_import = builtins.__import__

    def block_win32crypt(name, *args, **kwargs):
        if name == "win32crypt":
            raise ImportError("DPAPI unavailable in test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_win32crypt)
    with pytest.raises(RuntimeError, match="şifrelenemedi"):
        AIBrain._protect_key("test-secret")




def test_legacy_plaintext_api_keys_are_migrated_to_dpapi(tmp_path, monkeypatch):
    import json
    import utils.config_manager as config_module

    settings_path = tmp_path / "ai_settings.json"
    settings_path.write_text(json.dumps({
        "provider": "openai",
        "gemini_api_key": "legacy-gemini-secret",
        "api_keys": {},
    }), encoding="utf-8")

    legacy_ai = {
        "provider": "openai",
        "providers": {
            "openai": {"api_key": "legacy-openai-secret", "model": "legacy-model"}
        },
    }

    class LegacyConfig:
        def get(self, key, default=None):
            return legacy_ai if key == "ai" else default

        def set(self, key_path, value, save=True):
            assert key_path == "ai.providers"
            legacy_ai["providers"] = value
            return True

    monkeypatch.setattr(config_module, "get_config", lambda: LegacyConfig())
    monkeypatch.setattr(AIBrain, "_settings_file", staticmethod(lambda: settings_path))
    import hashlib

    def fake_protect(secret):
        if not secret:
            return {"plain": ""}
        return {"dpapi": hashlib.sha256(("test-encrypted:" + secret).encode("utf-8")).hexdigest()}

    monkeypatch.setattr(AIBrain, "_protect_key", staticmethod(fake_protect))

    brain = AIBrain()

    persisted = settings_path.read_text(encoding="utf-8")
    assert brain.gemini_key == "legacy-gemini-secret"
    assert brain.api_keys["openai"] == "legacy-openai-secret"
    assert "legacy-gemini-secret" not in persisted
    assert "legacy-openai-secret" not in persisted
    saved = json.loads(persisted)
    assert saved["gemini_api_key"] == {"dpapi": hashlib.sha256(b"test-encrypted:legacy-gemini-secret").hexdigest()}
    assert saved["api_keys"]["openai"] == {"dpapi": hashlib.sha256(b"test-encrypted:legacy-openai-secret").hexdigest()}
    assert legacy_ai["providers"]["openai"]["api_key"] == {"dpapi": hashlib.sha256(b"test-encrypted:legacy-openai-secret").hexdigest()}


def test_failed_plaintext_migration_preserves_original_credentials(tmp_path, monkeypatch):
    import json
    import utils.config_manager as config_module

    settings_path = tmp_path / "ai_settings.json"
    original = json.dumps({
        "provider": "openai",
        "gemini_api_key": "legacy-gemini-secret",
        "api_keys": {},
    })
    settings_path.write_text(original, encoding="utf-8")
    legacy_ai = {
        "provider": "openai",
        "providers": {"openai": {"api_key": "legacy-openai-secret"}},
    }

    class LegacyConfig:
        def get(self, key, default=None):
            return legacy_ai if key == "ai" else default

        def set(self, key_path, value, save=True):
            raise AssertionError("legacy config must not be changed if encryption failed")

    def encryption_failure(_secret):
        raise RuntimeError("DPAPI unavailable in test")

    monkeypatch.setattr(config_module, "get_config", lambda: LegacyConfig())
    monkeypatch.setattr(AIBrain, "_settings_file", staticmethod(lambda: settings_path))
    monkeypatch.setattr(AIBrain, "_protect_key", staticmethod(encryption_failure))

    AIBrain()

    assert settings_path.read_text(encoding="utf-8") == original
    assert legacy_ai["providers"]["openai"]["api_key"] == "legacy-openai-secret"



def test_gpt6_chat_completions_use_supported_sampling_parameters(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.api_keys["openai"] = "test-secret"

    class Response:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "Yanıt tamam"}}]}

    class Session:
        def __init__(self):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    session = Session()
    brain.session = session

    brain.api_models["openai"] = "gpt-6-luna"
    assert brain._compatible_api("openai", "test prompt") == "Yanıt tamam"
    luna_payload = session.calls[-1][1]["json"]
    assert luna_payload["reasoning_effort"] == "none"
    assert luna_payload["temperature"] == 0.2

    brain.api_models["openai"] = "gpt-6-astra"
    assert brain._compatible_api("openai", "test prompt") == "Yanıt tamam"
    astra_payload = session.calls[-1][1]["json"]
    assert "temperature" not in astra_payload
    assert "reasoning_effort" not in astra_payload

    brain.api_models["openrouter"] = "openai/gpt-6-luna"
    brain.api_keys["openrouter"] = "test-secret"
    assert brain._compatible_api("openrouter", "test prompt") == "Yanıt tamam"
    router_payload = session.calls[-1][1]["json"]
    assert router_payload["reasoning_effort"] == "none"


def test_fast_turkish_responses_use_command_processors_real_process_method():
    from core.command_processor import CommandProcessor

    assert callable(CommandProcessor.process)
    assert not hasattr(CommandProcessor, "process_command")
    result = CommandProcessor.process(None, "merhaba")

    assert result["success"] is True
    assert result["intent"] == "greeting"
    assert result["fast_local"] is True
    assert "Hazırım" in result["response"]



def test_ollama_task_router_classifies_coding_audio_and_general(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    assert brain._ollama_task("Python kodunu debug et") == "coding"
    assert brain._ollama_task("Midas M32 FOH ve SPL hesabı") == "audio"
    assert brain._ollama_task("Bana kısa bir selam ver") == "general"


def test_ollama_router_prefers_specialist_model_that_fits_4gb_budget(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    gib = 1024 ** 3
    monkeypatch.setattr(brain, "_ollama_memory_budget", lambda: int(1.1 * gib))
    models = [
        {"name": "qwen3:0.6b", "size": int(0.55 * gib)},
        {"name": "deepseek-coder:1.3b", "size": int(1.0 * gib)},
        {"name": "qwen2.5-coder:0.5b", "size": int(0.45 * gib)},
        {"name": "deepseek-r1:7b", "size": int(4.5 * gib)},
    ]
    selected, task, size, budget = brain._select_ollama_model(
        "Python kodundaki hatayı bul", models=models
    )
    assert selected == "qwen2.5-coder:0.5b"
    assert task == "coding"
    assert size <= budget


def test_ollama_router_refuses_model_larger_than_safe_memory_budget(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    monkeypatch.setattr(brain, "_ollama_memory_budget", lambda: 700 * 1024 ** 2)
    models = [
        {"name": "deepseek-coder:6.7b", "size": 5 * 1024 ** 3},
        {"name": "qwen2.5:1.5b", "size": 1 * 1024 ** 3},
    ]
    with pytest.raises(RuntimeError, match="4 GB RAM güvenli çalışma sınırı"):
        brain._select_ollama_model("kod yaz", models=models)


def test_ollama_request_uses_selected_model_small_context_and_unloads(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        brain, "_select_ollama_model",
        lambda _prompt: ("qwen3:0.6b", "general", 500 * 1024 ** 2, 900 * 1024 ** 2)
    )
    monkeypatch.setattr(brain, "_release_other_ollama_models", lambda _selected: None)

    class Response:
        ok = True
        def raise_for_status(self):
            return None
        def json(self):
            return {"message": {"content": "Hazırım."}}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(brain.session, "post", fake_post)
    assert brain._ollama("Merhaba") == "Hazırım."
    payload = calls[0][1]["json"]
    assert payload["model"] == "qwen3:0.6b"
    assert payload["keep_alive"] == 0
    assert payload["options"]["num_ctx"] == 2048
    assert brain.last_ollama_model == "qwen3:0.6b"



def test_ollama_router_honors_model_typed_in_settings(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    gib = 1024 ** 3
    brain.model = "huihui_ai/qwen2.5-abliterate"
    monkeypatch.setattr(brain, "_ollama_memory_budget", lambda: int(2.0 * gib))
    models = [
        {"name": "dolphin-philatelist:latest", "size": int(1.49 * gib)},
        {"name": "huihui_ai/qwen2.5-abliterate:latest", "size": int(1.2 * gib)},
    ]
    selected, task, size, budget = brain._select_ollama_model(
        "Genel bağlantı testi", models=models
    )
    assert selected == "huihui_ai/qwen2.5-abliterate:latest"
    assert size == int(1.2 * gib)
    assert size <= budget


def test_ollama_router_reports_pull_command_for_uninstalled_manual_model(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.model = "huihui_ai/qwen2.5-abliterate:latest"
    monkeypatch.setattr(brain, "_ollama_memory_budget", lambda: 2 * 1024 ** 3)
    models = [{"name": "dolphin-philatelist:latest", "size": int(1.49 * 1024 ** 3)}]
    with pytest.raises(RuntimeError, match="ollama pull huihui_ai/qwen2.5-abliterate:latest"):
        brain._select_ollama_model("Merhaba", models=models)


def test_ollama_router_explains_when_selected_model_exceeds_available_ram(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.model = "dolphin-philatelist:latest"
    monkeypatch.setattr(brain, "_ollama_memory_budget", lambda: int(0.09 * 1024 ** 3))
    models = [{"name": brain.model, "size": int(1.49 * 1024 ** 3)}]
    with pytest.raises(RuntimeError, match="boş RAM'e sığmıyor"):
        brain._select_ollama_model("Merhaba", models=models)
