import pytest

from core.command_processor import _parse_image_download_command, _validate_public_http_url


def test_image_download_command_extracts_direct_url():
    matched, url = _parse_image_download_command(
        "Patron, görseli indir https://cdn.example.com/foto.jpg"
    )
    assert matched is True
    assert url == "https://cdn.example.com/foto.jpg"


def test_image_download_command_asks_for_url_when_missing():
    matched, url = _parse_image_download_command("resmi indir")
    assert matched is True
    assert url == ""


def test_unrelated_command_is_not_treated_as_image_download():
    matched, url = _parse_image_download_command("Stagepulse sitesini aç")
    assert matched is False
    assert url == ""


def test_local_private_ip_is_rejected_before_network_access():
    with pytest.raises(ValueError, match="indirilemez"):
        _validate_public_http_url("http://192.168.1.10/image.png")



def test_existing_image_is_reused_without_network_or_redownload(tmp_path, monkeypatch):
    import hashlib
    from pathlib import Path
    from core.command_processor import _download_image

    url = "https://cdn.example.com/flower.png"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    folder = tmp_path / "Downloads" / "StagepulseJARVIS"
    folder.mkdir(parents=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    existing = folder / ("flower-" + key + ".png")
    existing.write_bytes(b"existing image")

    def no_network(_url):
        raise AssertionError("Mevcut dosya varsa ağ isteği yapılmamalı")

    monkeypatch.setattr("core.command_processor._validate_public_http_url", no_network)
    assert _download_image(url) == existing
    assert existing.read_bytes() == b"existing image"
