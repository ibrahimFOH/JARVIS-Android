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



def test_expected_optional_providers_are_free_only(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    assert brain.FREE_PROVIDERS == frozenset({"auto", "ollama", "gemini", "groq"})
    assert brain.FREE_CLOUD_PROVIDERS == frozenset({"gemini", "groq"})
    assert brain.provider == "ollama"
    assert brain.free_cloud_enabled is False


def test_free_provider_settings_persist_and_reload(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.configure(
        provider="groq",
        groq_key="not-a-real-secret",
        groq_model="openai/gpt-oss-20b",
        free_cloud_enabled=True,
    )
    saved = (tmp_path / "ai_settings.json").read_text(encoding="utf-8")
    assert '"provider": "groq"' in saved
    assert '"free_cloud_enabled": true' in saved
    reloaded = fresh_brain(tmp_path, monkeypatch)
    assert reloaded.provider == "groq"
    assert reloaded.free_cloud_enabled is True
    assert reloaded.groq_key == "not-a-real-secret"


def test_paid_provider_is_rejected_without_network_access(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    calls = []

    class Session:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("Ücretli API'ye istek gönderilmemeli")

    brain.session = Session()
    with pytest.raises(ValueError, match="Ücretli"):
        brain.configure(provider="openai")
    with pytest.raises(RuntimeError, match="Ücretli"):
        brain._compatible_api("openai", "test prompt")
    result = brain.test_provider("grok")
    assert result["success"] is False
    assert "engellendi" in result["message"].lower()
    brain.provider = "grok"
    answer = brain.ask("API testi")
    assert "engellendi" in answer.lower()
    assert calls == []

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
    brain.free_cloud_enabled = True
    calls = []
    monkeypatch.setattr(brain.session, "post", lambda *args, **kwargs: calls.append(args))
    result = brain.test_provider("groq")
    assert result["success"] is False
    assert "anahtarı boş" in result["message"].lower()
    assert calls == []

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



def test_legacy_paid_api_settings_are_inactive_and_preserved(tmp_path, monkeypatch):
    import utils.config_manager as config_module

    legacy_ai = {
        "provider": "openai",
        "ollama_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:0.6b",
        "providers": {
            "gemini": {"api_key": "legacy-gemini-key", "model": "gemini-3.8-flash"},
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
    assert brain.provider == "ollama"
    assert brain.free_cloud_enabled is False
    assert brain.gemini_key == "legacy-gemini-key"
    assert brain.api_keys["openai"] == "legacy-openai-key"
    assert brain.api_models["openai"] == "legacy-model"


def test_auto_provider_uses_only_explicitly_enabled_free_groq_fallback(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.provider = "auto"
    brain.groq_key = "test-key"
    brain.free_cloud_enabled = True
    monkeypatch.setattr(
        brain,
        "_ollama",
        lambda _prompt, _context="": "Ollama bağlantısında sorun oluştu: sunucu kapalı",
    )
    monkeypatch.setattr(
        brain,
        "_compatible_groq",
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


def test_default_cloud_models_are_on_free_model_allowlists(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    assert brain.gemini_model == "gemini-3.8-flash"
    assert brain.gemini_model in brain.FREE_GEMINI_MODELS
    assert brain.groq_model == "openai/gpt-oss-20b"
    assert brain.groq_model in brain.FREE_GROQ_MODELS

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




def test_generic_paid_api_transport_is_hard_disabled(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    calls = []

    class Session:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("Ücretli endpoint çağrılmamalı")

    brain.session = Session()
    for provider in ("openai", "grok", "anthropic", "deepseek", "perplexity", "openrouter", "custom"):
        with pytest.raises(RuntimeError, match="devre dışı"):
            brain._compatible_api(provider, "test prompt")
    assert calls == []

def test_fast_turkish_responses_use_command_processors_real_process_method():
    from core.command_processor import CommandProcessor

    assert callable(CommandProcessor.process)
    assert not hasattr(CommandProcessor, "process_command")
    result = CommandProcessor.process(None, "merhaba")

    assert result["success"] is True
    assert result["intent"] == "greeting"
    assert result["fast_local"] is True
    assert "Hazırım" in result["response"]



def test_github_research_is_wired_for_stagepulse_commands():
    from core.agent_tools import RepositoryManager

    assert RepositoryManager.is_command("Stagepulse için Github araştır")
    assert RepositoryManager.is_command("github tara")
    assert RepositoryManager.is_command("github incele owner/repo")


def test_stagepulse_github_scan_recommends_only_explicit_open_source_licenses(tmp_path):
    from core.agent_tools import RepositoryManager

    manager = RepositoryManager(settings_path=tmp_path / "repo.json")
    manager._search_github_repositories = lambda _query, per_page=3: [
        {
            "full_name": "audio/open-tool",
            "description": "Open measurement tool",
            "html_url": "https://github.com/audio/open-tool",
            "license": {"spdx_id": "MIT"},
            "language": "Python",
            "stargazers_count": 120,
            "pushed_at": "2026-01-01T00:00:00Z",
            "archived": False,
            "fork": False,
        },
        {
            "full_name": "audio/unknown-license",
            "description": "License missing",
            "html_url": "https://github.com/audio/unknown-license",
            "license": None,
            "language": "Python",
            "stargazers_count": 900,
            "pushed_at": "2026-01-01T00:00:00Z",
            "archived": False,
            "fork": False,
        },
    ]

    result = manager.search_stagepulse_repositories()
    by_name = {item["name"]: item for item in result["repositories"]}
    assert by_name["audio/open-tool"]["install_recommended"] is True
    assert by_name["audio/unknown-license"]["install_recommended"] is False
    assert by_name["audio/unknown-license"]["license"] == "BELİRSİZ"


def test_github_inspection_flags_install_scripts_and_preserves_license(tmp_path):
    import base64
    from core.agent_tools import RepositoryManager

    manager = RepositoryManager(settings_path=tmp_path / "repo.json")
    readme = "# Open audio\n\nInstall with python."
    encoded = base64.b64encode(readme.encode("utf-8")).decode("ascii")

    def fake_github_json(path):
        if path == "/repos/audio/open-tool":
            return {
                "license": {"spdx_id": "MIT"},
                "html_url": "https://github.com/audio/open-tool",
                "description": "Audio utility",
                "stargazers_count": 12,
                "language": "Python",
                "default_branch": "main",
            }
        if path == "/repos/audio/open-tool/readme":
            return {"content": encoded, "encoding": "base64"}
        if path == "/repos/audio/open-tool/git/trees/main?recursive=1":
            return {"tree": [{"path": "install.ps1"}, {"path": "README.md"}]}
        raise AssertionError("Unexpected GitHub path: " + path)

    manager._github_json = fake_github_json
    result = manager.inspect_github_repository("audio/open-tool")
    assert result["license_allowed"] is True
    assert result["install_recommended"] is False
    assert any("install.ps1" in warning for warning in result["warnings"])
    assert result["readme_excerpt"] == readme


def test_github_inspection_rejects_invalid_repository_name(tmp_path):
    from core.agent_tools import RepositoryManager

    manager = RepositoryManager(settings_path=tmp_path / "repo.json")
    with pytest.raises(ValueError, match="owner/repo"):
        manager.inspect_github_repository("https://github.com/audio/open-tool")



def test_private_task_uses_ollama_even_when_free_cloud_provider_is_selected(tmp_path, monkeypatch):
    brain = fresh_brain(tmp_path, monkeypatch)
    brain.provider = "groq"
    brain.free_cloud_enabled = True
    brain.groq_key = "test-key"
    calls = []
    monkeypatch.setattr(brain, "_ollama", lambda _prompt, _context="": "Yalnızca yerel yanıt")
    monkeypatch.setattr(
        brain, "_compatible_groq",
        lambda *_args, **_kwargs: calls.append("groq") or "Bulut yanıtı",
    )
    monkeypatch.setattr(
        brain, "_web",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Gizli görev internete gitmemeli")),
    )

    result = brain.ask(
        "Müşteri salonu için rapor hazırla",
        memory_context="Özel müşteri ölçüleri",
        allow_cloud=False,
    )
    assert result == "Yalnızca yerel yanıt"
    assert calls == []
