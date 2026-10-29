from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_gui_exposes_android_host_control():
    source = (ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")
    assert 'text="ANDROID HOST"' in source
    assert "def _toggle_android_bridge(self):" in source
    assert "allow_lan_http=True" in source
    assert "Windows ve Android arasındaki köprü durdurulsun mu?" in source


def test_frozen_bridge_token_is_stored_outside_pyinstaller_temp_directory():
    source = (ROOT / "android_bridge.py").read_text(encoding="utf-8")
    assert 'if getattr(sys, "frozen", False):' in source
    assert 'app_data / "StagepulseJARVIS" / "config" / "bridge_token.txt"' in source
    assert "return ROOT / \"config\" / \"bridge_token.txt\"" in source


def test_bridge_wildcard_bind_requires_explicit_opt_in():
    source = (ROOT / "android_bridge.py").read_text(encoding="utf-8")
    assert 'if host in ("0.0.0.0", "::") and not allow_lan_http:' in source
    assert 'os.environ.get("JARVIS_BRIDGE_ALLOW_LAN_HTTP", "") == "1"' in source
