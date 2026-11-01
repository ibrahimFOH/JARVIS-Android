from modules import application_manager as app_module


def make_manager():
    manager = app_module.ApplicationManager.__new__(app_module.ApplicationManager)
    manager.common_apps = {}
    return manager


def test_unknown_application_name_cannot_execute_shell_text(monkeypatch):
    monkeypatch.setattr(app_module, "find_executable", lambda _name: None)
    monkeypatch.setattr(app_module.time, "sleep", lambda _seconds: None)

    def forbid_popen(*args, **kwargs):
        raise AssertionError("an unrecognized user string must not reach process creation")

    monkeypatch.setattr(app_module.subprocess, "Popen", forbid_popen)
    result = make_manager().launch("notepad & whoami")

    assert result["success"] is False
    assert "not executed as shell commands" in result["message"]


def test_resolved_executable_uses_argument_list_without_shell(monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module.ApplicationManager, "_resolve_app_name",
        lambda _self, _name: r"C:\Program Files\Test App\test.exe",
    )
    monkeypatch.setattr(app_module, "find_executable", lambda _name: None)
    monkeypatch.setattr(app_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        app_module.subprocess, "Popen",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )

    result = make_manager().launch("Test App")

    assert result["success"] is True
    assert calls == [([r"C:\Program Files\Test App\test.exe"], {"shell": False})]


def test_known_windows_protocol_uses_shell_execute_not_cmd(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "find_executable", lambda _name: None)
    monkeypatch.setattr(app_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        app_module.os, "startfile",
        lambda target: calls.append(target),
        raising=False,
    )

    def forbid_popen(*args, **kwargs):
        raise AssertionError("protocol URI must not be executed by a shell")

    monkeypatch.setattr(app_module.subprocess, "Popen", forbid_popen)
    result = make_manager().launch("settings")

    assert result["success"] is True
    assert calls == ["ms-settings:"]



def test_command_scripts_are_rejected_even_when_resolved(monkeypatch):
    monkeypatch.setattr(app_module, "find_executable", lambda _name: None)
    monkeypatch.setattr(
        app_module.ApplicationManager, "_resolve_app_name",
        lambda _self, name: rf"C:\\Temp\\{name}",
    )
    monkeypatch.setattr(app_module.time, "sleep", lambda _seconds: None)

    def forbid_launch(*args, **kwargs):
        raise AssertionError("command scripts must never be launched")

    monkeypatch.setattr(app_module.subprocess, "Popen", forbid_launch)
    monkeypatch.setattr(app_module.os, "startfile", forbid_launch, raising=False)

    for name in ("payload.bat", "payload.cmd", "payload.ps1"):
        result = make_manager().launch(name)
        assert result["success"] is False
        assert "Desteklenmeyen uygulama türü" in result["message"]


def test_shortcut_launch_uses_windows_shell_execute(monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module.ApplicationManager, "_resolve_app_name",
        lambda _self, _name: r"C:\\ProgramData\\Stagepulse\\MixConsole.lnk",
    )
    monkeypatch.setattr(app_module, "find_executable", lambda _name: None)
    monkeypatch.setattr(app_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        app_module.os, "startfile",
        lambda target: calls.append(target),
        raising=False,
    )

    def forbid_popen(*args, **kwargs):
        raise AssertionError("shortcut must not be passed to process creation")

    monkeypatch.setattr(app_module.subprocess, "Popen", forbid_popen)
    result = make_manager().launch("MixConsole")

    assert result["success"] is True
    assert calls == [r"C:\\ProgramData\\Stagepulse\\MixConsole.lnk"]
