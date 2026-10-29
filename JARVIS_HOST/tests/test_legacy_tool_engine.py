from core.agent_tools import ToolEngine


def test_legacy_run_safe_refuses_arbitrary_shell_commands(monkeypatch, tmp_path):
    import core.agent_tools as tools_module

    def forbidden_run(*args, **kwargs):
        raise AssertionError("arbitrary shell execution must not be invoked")

    monkeypatch.setattr(tools_module.subprocess, "run", forbidden_run)
    engine = ToolEngine(repo=tmp_path)

    result = engine.run_safe("echo safe-looking && whoami")

    assert result["ok"] is False
    assert "devre dışı" in result["error"].lower()
