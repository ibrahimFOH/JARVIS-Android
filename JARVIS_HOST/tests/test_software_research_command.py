from core.command_processor import _stagepulse_software_research_command


def test_github_dmx_order_routes_to_stagepulse_lighting_research(monkeypatch):
    captured = {}

    class FakeScout:
        def scan(self, category, per_category):
            captured["category"] = category
            captured["per_category"] = per_category
            return {
                "results": [
                    {
                        "full_name": "example/lighting-tool",
                        "recommendation": "İncelemeye değer",
                        "license": "MIT",
                        "license_state": "Açık kaynak lisansı doğrulandı: MIT",
                        "description": "A free DMX tool",
                        "windows_support": "Windows desteğine dair depo işareti bulundu.",
                        "local_install_status": "Bu yazılım bilgisayarda kurulu; yeniden indirme/kurulum önerilmez.",
                        "installed_on_pc": [{"display_name": "QLC+", "version": "5.3.0"}],
                        "turkish_localization": {
                            "status": "Türkçe dil dosyası bulunamadı; çeviri çalışması gerekir."
                        },
                        "release": {"tag": "v1.0"},
                        "html_url": "https://github.com/example/lighting-tool",
                    }
                ]
            }

    monkeypatch.setattr(
        "core.software_scout.StagepulseSoftwareScout",
        FakeScout,
    )

    result = _stagepulse_software_research_command("GitHub'da DMX ışık yazılımı araştır")

    assert captured == {"category": "lighting", "per_category": 1}
    assert result["success"] is True
    assert result["intent"] == "stagepulse_software_research"
    assert "QLC+" in result["response"]
    assert "yeniden indirme/kurulum önerilmez" in result["response"]
    assert "çeviri çalışması gerekir" in result["response"]


def test_unrelated_commands_are_not_intercepted():
    result = _stagepulse_software_research_command("Bilgisayarın RAM durumunu göster")

    assert result is None
