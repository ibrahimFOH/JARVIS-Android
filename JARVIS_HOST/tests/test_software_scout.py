from core.software_scout import StagepulseSoftwareScout, SoftwareScoutError


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.headers = {}
        self.ok = 200 <= status < 300

    def json(self):
        return self._payload


class _Session:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        payload = self.mapping.get(url)
        if payload is None:
            return _Response({}, status=404)
        return _Response(payload)


def test_license_policy_accepts_open_source_only():
    assert StagepulseSoftwareScout._license_state("MIT").startswith("Açık kaynak")
    assert StagepulseSoftwareScout._license_state("Apache-2.0").startswith("Açık kaynak")
    assert "doğrulanamadı" in StagepulseSoftwareScout._license_state("").lower()
    assert "izin listesinde değil" in StagepulseSoftwareScout._license_state("NOASSERTION").lower()


def test_turkish_locale_is_detected_from_translation_tree():
    tree = {
        "tree": [
            {"path": "translations/app_tr_TR.ts", "type": "blob"},
            {"path": "translations/app_de_DE.ts", "type": "blob"},
        ],
        "truncated": False,
    }
    result = StagepulseSoftwareScout._turkish_locale(tree)
    assert result["available"] is True
    assert result["files"] == ["translations/app_tr_TR.ts"]


def test_missing_turkish_locale_is_reported_without_claiming_translation():
    result = StagepulseSoftwareScout._turkish_locale({"tree": [], "truncated": False})
    assert result["available"] is False
    assert "çeviri çalışması gerekir" in result["status"]


def test_repository_report_includes_license_localization_and_windows_metadata():
    base = "https://api.github.com/repos/example/free-tool"
    mapping = {
        base: {
            "full_name": "example/free-tool",
            "description": "A free Windows DMX tool",
            "html_url": "https://github.com/example/free-tool",
            "homepage": "https://example.org",
            "license": {"spdx_id": "MIT"},
            "archived": False,
            "pushed_at": "2026-10-30T12:00:00Z",
            "stargazers_count": 50,
            "default_branch": "main",
            "topics": ["windows", "dmx"],
        },
        base + "/git/trees/main": {
            "tree": [
                {"path": "src/app_windows.cpp", "type": "blob"},
                {"path": "translations/app_tr_TR.ts", "type": "blob"},
            ],
            "truncated": False,
        },
        base + "/releases/latest": {
            "tag_name": "v1.0.0",
            "published_at": "2026-10-20T10:00:00Z",
            "assets": [
                {
                    "name": "setup.exe",
                    "browser_download_url": "https://github.com/example/free-tool/releases/download/v1/setup.exe",
                    "size": 1024,
                    "digest": "sha256:abc123",
                }
            ],
        },
    }
    scout = StagepulseSoftwareScout(session=_Session(mapping))
    result = scout.inspect_repository("example/free-tool")

    assert result["license_approved"] is True
    assert result["turkish_localization"]["available"] is True
    assert "Windows desteğine dair depo işareti" in result["windows_support"]
    assert result["release"]["has_verified_installer_candidate"] is True
    assert result["install_policy"].startswith("Kurulum adayı")


def test_invalid_repository_name_is_rejected_before_network():
    session = _Session({})
    scout = StagepulseSoftwareScout(session=session)

    try:
        scout.inspect_repository("https://example.com/owner/repo")
    except SoftwareScoutError as exc:
        assert "owner/repository" in str(exc)
    else:
        raise AssertionError("Geçersiz repo adresi kabul edildi")

    assert session.calls == []
