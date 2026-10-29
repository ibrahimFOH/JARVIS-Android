import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

import core.update_manager as update_module
from core.update_manager import WindowsUpdate, WindowsUpdateManager


class JsonResponse:
    status_code = 200
    headers = {}

    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        return None

    def json(self):
        return self.value


class BytesResponse:
    status_code = 200

    def __init__(self, data):
        self.data = data
        self.headers = {"Content-Length": str(len(data))}
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024):
        for offset in range(0, len(self.data), chunk_size):
            yield self.data[offset:offset + chunk_size]

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def test_only_github_release_assets_are_trusted():
    assert WindowsUpdateManager._trusted_release_url(
        "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/update.json"
    )
    assert WindowsUpdateManager._trusted_release_url(
        "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/JARVIS-Windows.zip",
        expected_tag="v2.2.3",
    )
    assert not WindowsUpdateManager._trusted_release_url(
        "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.2/JARVIS-Windows.zip",
        expected_tag="v2.2.3",
    )
    assert not WindowsUpdateManager._trusted_release_url("https://example.com/release.zip")
    assert not WindowsUpdateManager._trusted_release_url("https://github.com/another-owner/another-repo/releases/download/v2/file.zip")
    assert not WindowsUpdateManager._trusted_release_url("http://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2/file.zip")
    assert not WindowsUpdateManager._trusted_release_url(
        "https://github.com:8443/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/JARVIS-Windows.zip",
        expected_tag="v2.2.3",
    )
    assert not WindowsUpdateManager._trusted_release_url(
        "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/../JARVIS-Windows.zip",
        expected_tag="v2.2.3",
    )
    assert WindowsUpdateManager._trusted_final_download_url(
        "https://release-assets.githubusercontent.com/signed-asset"
    )
    assert not WindowsUpdateManager._trusted_final_download_url(
        "https://evil.example/signed-asset"
    )


def test_check_for_update_reads_windows_fields_from_shared_manifest(tmp_path, monkeypatch):
    manager = WindowsUpdateManager()
    manager.state_dir = tmp_path / "updates"
    manager.state_file = manager.state_dir / "update_state.json"
    monkeypatch.setattr(manager, "_should_check", lambda force: True)
    monkeypatch.setattr(manager, "_record_check", lambda: None)
    monkeypatch.setattr(manager, "current_version", lambda: "2.2.2")

    metadata_url = "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/update.json"
    package_url = "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/JARVIS-Windows.zip"
    metadata = {
        "tagName": "v2.2.3",
        "versionName": "2.2.3",
        "windowsUrl": package_url,
        "windowsSha256": "a" * 64,
        "notes": "Test release",
    }

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout=None):
            if url == update_module.RELEASE_API:
                return JsonResponse({
                    "tag_name": "v2.2.3",
                    "assets": [{"name": "update.json", "browser_download_url": metadata_url}],
                })
            if url == metadata_url:
                return JsonResponse(metadata)
            raise AssertionError("Unexpected URL: " + url)

    monkeypatch.setattr(update_module.requests, "Session", Session)
    update = manager.check_for_update(force=True)
    assert update is not None
    assert update.version_name == "2.2.3"
    assert update.package_url == package_url
    assert update.sha256 == "a" * 64


def test_update_script_cannot_replace_the_entire_application_folder(tmp_path, monkeypatch):
    install_dir = tmp_path / "app"
    install_dir.mkdir()
    running_exe = install_dir / "StagepulseJARVIS.exe"
    running_exe.write_bytes(b"old executable")
    (install_dir / "config").mkdir()
    (install_dir / "config" / "config.json").write_text('{"test":true}', encoding="utf-8")
    (install_dir / "config" / "bridge_token.txt").write_text("local-token", encoding="utf-8")

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("StagepulseJARVIS.exe", b"new executable")
        archive.writestr("VERSION", "2.2.3")
    archive_bytes = archive_buffer.getvalue()

    manager = WindowsUpdateManager()
    manager.state_dir = tmp_path / "local-app-data" / "updates"
    monkeypatch.setattr(update_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(update_module.sys, "executable", str(running_exe))
    monkeypatch.setattr(
        update_module.requests, "get",
        lambda *args, **kwargs: BytesResponse(archive_bytes),
    )
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(update_module.subprocess, "Popen", fake_popen)
    update = WindowsUpdate(
        version_name="2.2.3",
        package_url="https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/JARVIS-Windows.zip",
        sha256=hashlib.sha256(archive_bytes).hexdigest(),
        notes="",
        tag_name="v2.2.3",
    )

    result = manager.download_and_launch_installer(update)
    assert "Güncelleme doğrulandı" in result
    powershell = captured["args"][-1]
    decoded = base64.b64decode(powershell).decode("utf-16le")
    assert "Copy-Item -Path (Join-Path $stage '*') -Destination $target" in decoded
    assert "$backup = Join-Path (Split-Path -Parent $target)" in decoded
    assert "Move-Item -LiteralPath $target -Destination $backup" not in decoded
    assert "Remove-Item -LiteralPath $target -Recurse -Force" not in decoded
    assert "config\\config.json" in decoded



def test_check_for_update_rejects_manifest_from_a_different_release_tag(tmp_path, monkeypatch):
    manager = WindowsUpdateManager()
    manager.state_dir = tmp_path / "updates"
    manager.state_file = manager.state_dir / "update_state.json"
    monkeypatch.setattr(manager, "_should_check", lambda force: True)
    monkeypatch.setattr(manager, "_record_check", lambda: None)
    monkeypatch.setattr(manager, "current_version", lambda: "2.2.2")

    latest_metadata_url = "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.3/update.json"
    stale_package_url = "https://github.com/ibrahimFOH/JARVIS-Android/releases/download/v2.2.2/JARVIS-Windows.zip"

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout=None):
            if url == update_module.RELEASE_API:
                return JsonResponse({
                    "tag_name": "v2.2.3",
                    "assets": [{"name": "update.json", "browser_download_url": latest_metadata_url}],
                })
            if url == latest_metadata_url:
                return JsonResponse({
                    "tagName": "v2.2.3",
                    "versionName": "2.2.3",
                    "windowsUrl": stale_package_url,
                    "windowsSha256": "a" * 64,
                })
            raise AssertionError("Unexpected URL: " + url)

    monkeypatch.setattr(update_module.requests, "Session", Session)
    import pytest
    with pytest.raises(ValueError, match="aynı sürüm etiketine"):
        manager.check_for_update(force=True)
