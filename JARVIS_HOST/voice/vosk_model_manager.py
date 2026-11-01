"""Yerel Türkçe Vosk modeli: önce bilgisayarda ara, yoksa resmi kaynaktan indir."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import hashlib
import os
import shutil
import tempfile
import zipfile

import requests

MODEL_NAME = "vosk-model-small-tr-0.3"
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-tr-0.3.zip"
MAX_ARCHIVE_BYTES = 90 * 1024 * 1024
MAX_UNPACKED_BYTES = 250 * 1024 * 1024


class VoskModelError(RuntimeError):
    """Model bulunamadı, indirilemedi veya güvenli şekilde açılamadı."""


class VoskModelManager:
    def __init__(self, configured_path: str | None = None, timeout: int = 30):
        self.configured_path = str(configured_path or "").strip()
        self.timeout = max(5, min(int(timeout), 90))
        app_data = os.environ.get("APPDATA")
        self.default_parent = (
            Path(app_data) / "StagepulseJARVIS" / "models"
            if app_data else Path.home() / ".stagepulse-jarvis" / "models"
        )

    @staticmethod
    def _is_model(path: Path) -> bool:
        try:
            return (
                path.is_dir()
                and (path / "am" / "final.mdl").is_file()
                and (path / "conf" / "model.conf").is_file()
                and (path / "graph").is_dir()
            )
        except OSError:
            return False

    def _existing_candidates(self) -> list[Path]:
        candidates = []
        if self.configured_path:
            candidates.append(Path(self.configured_path).expanduser())
        candidates.extend([
            self.default_parent / MODEL_NAME,
            Path.cwd() / "models" / MODEL_NAME,
            Path.home() / "Downloads" / MODEL_NAME,
            Path.home() / "Documents" / "Stagepulse" / "models" / MODEL_NAME,
        ])
        seen = set()
        result = []
        for path in candidates:
            try:
                resolved = path.resolve()
            except (OSError, RuntimeError):
                continue
            key = os.path.normcase(str(resolved))
            if key not in seen:
                result.append(resolved)
                seen.add(key)
        return result

    def find_existing(self) -> Path | None:
        for path in self._existing_candidates():
            if self._is_model(path):
                return path
        return None

    @staticmethod
    def _safe_extract(archive: zipfile.ZipFile, staging: Path) -> Path:
        members = archive.infolist()
        if len(members) > 30000:
            raise VoskModelError("Model arşivi beklenenden fazla dosya içeriyor.")
        total_size = sum(info.file_size for info in members)
        if total_size > MAX_UNPACKED_BYTES:
            raise VoskModelError("Model arşivinin açılmış boyutu güvenlik sınırını aşıyor.")

        for info in members:
            name = info.filename.replace("\\", "/")
            parts = Path(name).parts
            if name.startswith("/") or ".." in parts or (parts and ":" in parts[0]):
                raise VoskModelError("Model arşivinde güvenli olmayan dosya yolu bulundu.")
            unix_mode = (info.external_attr >> 16) & 0xF000
            if unix_mode == 0xA000:
                raise VoskModelError("Model arşivindeki sembolik bağlantılar kabul edilmedi.")

        bad_member = archive.testzip()
        if bad_member:
            raise VoskModelError("Model arşivinin CRC kontrolü başarısız: " + bad_member)

        archive.extractall(staging)
        extracted = staging / MODEL_NAME
        if not VoskModelManager._is_model(extracted):
            # Some mirrors may wrap the same model in one extra directory.
            matches = [p for p in staging.rglob(MODEL_NAME) if VoskModelManager._is_model(p)]
            if len(matches) != 1:
                raise VoskModelError("İndirilen arşivde beklenen Türkçe Vosk model yapısı bulunamadı.")
            extracted = matches[0]
        return extracted

    def ensure_model(self) -> Path:
        existing = self.find_existing()
        if existing:
            return existing

        self.default_parent.mkdir(parents=True, exist_ok=True)
        final_path = self.default_parent / MODEL_NAME
        if final_path.exists():
            raise VoskModelError(
                "Model klasörü var ancak eksik veya bozuk. Otomatik üzerine yazılmadı: "
                + str(final_path)
            )

        temp_root = Path(tempfile.mkdtemp(prefix="vosk-tr-", dir=str(self.default_parent)))
        archive_path = temp_root / (MODEL_NAME + ".zip")
        staging = temp_root / "unpacked"
        staging.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        downloaded = 0

        try:
            response = requests.get(
                MODEL_URL,
                stream=True,
                timeout=self.timeout,
                allow_redirects=True,
                headers={"User-Agent": "Stagepulse-JARVIS/1.0"},
            )
            response.raise_for_status()
            final_host = (urlparse(response.url).hostname or "").lower()
            if final_host not in {"alphacephei.com", "www.alphacephei.com"}:
                raise VoskModelError("Vosk indirme adresi resmi alan adından farklı; indirme reddedildi.")

            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ARCHIVE_BYTES:
                raise VoskModelError("Vosk arşivi beklenen boyut sınırını aşıyor.")

            with archive_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > MAX_ARCHIVE_BYTES:
                        raise VoskModelError("İndirme boyutu güvenlik sınırını aştı.")
                    digest.update(chunk)
                    output.write(chunk)

            if downloaded == 0:
                raise VoskModelError("Vosk modeli boş indirildi.")
            with zipfile.ZipFile(archive_path, "r") as archive:
                model_path = self._safe_extract(archive, staging)

            if final_path.exists():
                raise VoskModelError("Model klasörü indirme sırasında oluşturuldu; üzerine yazılmadı.")
            shutil.move(str(model_path), str(final_path))
            if not self._is_model(final_path):
                raise VoskModelError("Kurulum sonrası Vosk model yapısı doğrulanamadı.")

            # Source site currently publishes no reference SHA-256 for this model.
            # Keep our measured digest for local integrity checks on later starts.
            (final_path / ".stagepulse-source.sha256").write_text(
                digest.hexdigest() + "  " + MODEL_NAME + ".zip\n",
                encoding="ascii",
            )
            return final_path
        except (requests.RequestException, OSError, zipfile.BadZipFile, ValueError) as exc:
            raise VoskModelError("Türkçe Vosk modeli indirilemedi veya açılamadı: " + str(exc)) from exc
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)
