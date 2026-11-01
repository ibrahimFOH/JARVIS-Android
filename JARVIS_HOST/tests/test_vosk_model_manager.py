from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from voice.vosk_model_manager import (
    MODEL_NAME,
    MODEL_URL,
    VoskModelError,
    VoskModelManager,
)


def _model_zip():
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{MODEL_NAME}/am/final.mdl", b"model")
        archive.writestr(f"{MODEL_NAME}/conf/model.conf", b"config")
        archive.writestr(f"{MODEL_NAME}/graph/HCLG.fst", b"graph")
    return buffer.getvalue()


class _Response:
    def __init__(self, payload, url=MODEL_URL):
        self.payload = payload
        self.url = url
        self.headers = {"Content-Length": str(len(payload))}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1024):
        for offset in range(0, len(self.payload), chunk_size):
            yield self.payload[offset:offset + chunk_size]


def test_existing_local_model_is_reused_without_download(tmp_path, monkeypatch):
    model = tmp_path / MODEL_NAME
    (model / "am").mkdir(parents=True)
    (model / "conf").mkdir()
    (model / "graph").mkdir()
    (model / "am" / "final.mdl").write_bytes(b"model")
    (model / "conf" / "model.conf").write_bytes(b"config")

    manager = VoskModelManager()
    manager.default_parent = tmp_path
    calls = []
    monkeypatch.setattr(
        "voice.vosk_model_manager.requests.get",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    assert manager.ensure_model() == model
    assert calls == []


def test_missing_model_downloads_from_official_https_and_validates_structure(tmp_path, monkeypatch):
    manager = VoskModelManager()
    manager.default_parent = tmp_path / "models"
    calls = []
    monkeypatch.setattr(
        "voice.vosk_model_manager.requests.get",
        lambda url, **kwargs: (calls.append(url) or _Response(_model_zip())),
    )

    installed = manager.ensure_model()

    assert installed == tmp_path / "models" / MODEL_NAME
    assert manager._is_model(installed)
    assert calls == [MODEL_URL]
    assert (installed / ".stagepulse-source.sha256").is_file()


def test_model_download_rejects_redirect_to_untrusted_host(tmp_path, monkeypatch):
    manager = VoskModelManager()
    manager.default_parent = tmp_path / "models"
    monkeypatch.setattr(
        "voice.vosk_model_manager.requests.get",
        lambda *args, **kwargs: _Response(_model_zip(), url="https://mirror.invalid/model.zip"),
    )

    with pytest.raises(VoskModelError, match="resmi alan adından farklı"):
        manager.ensure_model()

    assert not (tmp_path / "models" / MODEL_NAME).exists()


def test_model_archive_rejects_path_traversal(tmp_path):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../outside.txt", "bad")
        archive.writestr(f"{MODEL_NAME}/am/final.mdl", b"model")
    buffer.seek(0)

    with zipfile.ZipFile(buffer, "r") as archive:
        with pytest.raises(VoskModelError, match="güvenli olmayan dosya yolu"):
            VoskModelManager._safe_extract(archive, tmp_path / "staging")


def test_incomplete_existing_model_is_not_overwritten_or_downloaded(tmp_path, monkeypatch):
    model = tmp_path / MODEL_NAME
    model.mkdir()
    manager = VoskModelManager()
    manager.default_parent = tmp_path
    calls = []
    monkeypatch.setattr(
        "voice.vosk_model_manager.requests.get",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(VoskModelError, match="eksik veya bozuk"):
        manager.ensure_model()

    assert calls == []
