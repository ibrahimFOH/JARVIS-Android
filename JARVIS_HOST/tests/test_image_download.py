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
