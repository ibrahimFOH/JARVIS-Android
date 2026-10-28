"""Verified Windows JARVIS updater for signed GitHub Release packages.

The updater never installs code from arbitrary URLs. It downloads only the Windows
package referenced by this repository's latest HTTPS GitHub Release and verifies SHA-256
before extraction. Windows still asks for elevation if the install directory requires it.
"""
import base64
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

REPOSITORY = "ibrahimFOH/JARVIS-Android"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_PACKAGE_BYTES = 500 * 1024 * 1024


@dataclass(frozen=True)
class WindowsUpdate:
    version_name: str
    package_url: str
    sha256: str
    notes: str
    tag_name: str


class WindowsUpdateManager:
    def __init__(self):
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home())
        self.state_dir = Path(local_app_data) / "Stagepulse" / "JARVIS" / "updates"
        self.state_file = self.state_dir / "update_state.json"
        self.timeout = (10, 40)

    @staticmethod
    def _version_tuple(value):
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", str(value or ""))
        return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)

    @staticmethod
    def _trusted_release_url(value):
        parsed = urlparse(str(value or ""))
        return (
            parsed.scheme == "https"
            and parsed.hostname == "github.com"
            and "/releases/download/" in parsed.path
            and parsed.username is None
            and parsed.password is None
        )

    def current_version(self):
        if getattr(sys, "frozen", False):
            candidates = [
                Path(sys.executable).resolve().parent / "VERSION",
                Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)) / "VERSION",
            ]
        else:
            candidates = [Path(__file__).resolve().parents[1] / "VERSION"]
        for version_file in candidates:
            try:
                version = version_file.read_text(encoding="utf-8").strip()
                if version:
                    return version
            except OSError:
                continue
        return "0.0.0"

    def _should_check(self, force):
        if force:
            return True
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            last = float(state.get("last_attempt", 0))
            return time.time() - last >= 12 * 60 * 60
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return True

    def _record_check(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps({"last_attempt": time.time()}, indent=2),
            encoding="utf-8",
        )

    def check_for_update(self, force=False):
        if not self._should_check(force):
            return None
        self._record_check()

        session = requests.Session()
        session.headers.update({
            "Accept": "application/vnd.github+json",
            "User-Agent": "Stagepulse-JARVIS-Windows-Updater/1.0",
        })
        response = session.get(RELEASE_API, timeout=self.timeout)
        if response.status_code == 404:
            raise RuntimeError(
                "Henüz yayımlanmış bir JARVIS GitHub Release bulunamadı. "
                "Güncelleme sistemi, ilk imzalı sürüm yayımlandıktan sonra etkinleşir."
            )
        response.raise_for_status()
        release = response.json()
        tag_name = str(release.get("tag_name", ""))
        assets = release.get("assets") or []
        metadata_url = next(
            (
                item.get("browser_download_url")
                for item in assets
                if item.get("name") == "update.json"
            ),
            None,
        )
        if not self._trusted_release_url(metadata_url):
            raise ValueError("En son sürüm güvenilir bir update.json dosyası içermiyor.")

        metadata_response = session.get(metadata_url, timeout=self.timeout)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        package_url = metadata.get("windowsUrl")
        package_hash = str(metadata.get("windowsSha256", "")).lower()
        version_name = str(metadata.get("versionName", ""))
        if not self._trusted_release_url(package_url):
            raise ValueError("Windows güncelleme paketi geçerli bir GitHub Release adresi değil.")
        if not re.fullmatch(r"[a-f0-9]{64}", package_hash):
            raise ValueError("Windows paketi SHA-256 bilgisi eksik veya hatalı.")
        if not version_name:
            raise ValueError("Windows güncellemesinde sürüm adı bulunamadı.")
        if self._version_tuple(version_name) <= self._version_tuple(self.current_version()):
            return None

        return WindowsUpdate(
            version_name=version_name,
            package_url=package_url,
            sha256=package_hash,
            notes=str(metadata.get("notes", "Stagepulse JARVIS güncellemesi.")),
            tag_name=tag_name,
        )

    def download_and_launch_installer(self, update):
        if not getattr(sys, "frozen", False):
            raise RuntimeError(
                "Otomatik değiştirme yalnızca yayımlanmış Windows EXE paketinde çalışır. "
                "Kaynak kodu ile çalıştırıldığında yeni paketi elle kurmak gerekir."
            )

        running_exe = Path(sys.executable).resolve()
        target_dir = running_exe.parent
        if running_exe.name.lower() not in {"jarvis.exe", "stagepulsejarvis.exe"} or not running_exe.is_file():
            raise RuntimeError("Güncelleme yalnızca resmi JARVIS.exe veya StagepulseJARVIS.exe uygulamasından başlatılabilir.")
        if (target_dir / "main.py").exists() or (target_dir / "venv").is_dir() or (target_dir / "JARVIS_HOST").is_dir():
            raise RuntimeError(
                "Bu klasör bir kaynak kodu/venv çalışma alanına benziyor. "
                "Güncelleme kaynak dosyalarını değiştirmemek için durduruldu; "
                "önce JARVIS-Windows.zip paketini ayrı bir uygulama klasörüne kur."
            )

        self.state_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.state_dir / f"JARVIS-Windows-{update.version_name}.zip"
        stage_dir = self.state_dir / f"stage-{update.version_name}"
        if stage_dir.exists():
            shutil.rmtree(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        total = 0
        with requests.get(
            update.package_url,
            stream=True,
            allow_redirects=True,
            timeout=self.timeout,
            headers={"User-Agent": "Stagepulse-JARVIS-Windows-Updater/1.0"},
        ) as response:
            response.raise_for_status()
            length = int(response.headers.get("Content-Length", "0") or 0)
            if length > MAX_PACKAGE_BYTES:
                raise ValueError("Windows paketi izin verilen boyutu aşıyor.")
            with zip_path.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_PACKAGE_BYTES:
                        raise ValueError("Windows paketi izin verilen boyutu aştı.")
                    digest.update(chunk)
                    output.write(chunk)

        if total == 0 or digest.hexdigest().lower() != update.sha256:
            zip_path.unlink(missing_ok=True)
            raise ValueError("Windows paketi SHA-256 doğrulamasından geçemedi.")

        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                root = stage_dir.resolve()
                for member in archive.infolist():
                    resolved = (stage_dir / member.filename).resolve()
                    if os.path.commonpath((str(root), str(resolved))) != str(root):
                        raise ValueError("Arşivde güvenli olmayan dosya yolu bulundu.")
                archive.extractall(stage_dir)
        except Exception:
            shutil.rmtree(stage_dir, ignore_errors=True)
            raise

        candidate_names = (running_exe.name, "StagepulseJARVIS.exe", "JARVIS.exe")
        new_exe = next((stage_dir / name for name in candidate_names if (stage_dir / name).is_file()), None)
        if new_exe is None or not (stage_dir / "VERSION").is_file():
            shutil.rmtree(stage_dir, ignore_errors=True)
            raise ValueError("İndirilen arşiv tanınan bir JARVIS EXE dosyası ve VERSION içermiyor.")
        new_exe_name = new_exe.name

        target_text = str(target_dir.resolve())
        stage_text = str(stage_dir.resolve())
        old_exe_name = running_exe.name
        pid_to_wait = os.getpid()

        def ps_quote(value):
            return "'" + str(value).replace("'", "''") + "'"

        script = r"""
$ErrorActionPreference = 'Stop'
$target = __TARGET__
$stage = __STAGE__
$parentPid = __PARENT_PID__
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "$target.rollback-$stamp"
while (Get-Process -Id $parentPid -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 1 }
try {
    foreach ($relative in @('config\config.json', 'config\bridge_token.txt')) {
        $oldFile = Join-Path $target $relative
        if (Test-Path -LiteralPath $oldFile -PathType Leaf) {
            $newFile = Join-Path $stage $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $newFile) | Out-Null
            Copy-Item -LiteralPath $oldFile -Destination $newFile -Force
        }
    }
    $oldLogs = Join-Path $target 'logs'
    if (Test-Path -LiteralPath $oldLogs -PathType Container) {
        $newLogs = Join-Path $stage 'logs'
        New-Item -ItemType Directory -Force -Path $newLogs | Out-Null
        Copy-Item -Path (Join-Path $oldLogs '*') -Destination $newLogs -Recurse -Force -ErrorAction SilentlyContinue
    }
    Move-Item -LiteralPath $target -Destination $backup
    try {
        Move-Item -LiteralPath $stage -Destination $target
        $newExe = Join-Path $target __NEW_EXE__
        $process = Start-Process -FilePath $newExe -WorkingDirectory $target -PassThru
        Start-Sleep -Seconds 8
        if ($process.HasExited) { throw 'Yeni JARVIS beklenmedik biçimde kapandı.' }
        # Retain one dated rollback folder rather than deleting the previous install/data.
    } catch {
        if (Test-Path -LiteralPath $target -PathType Container) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        if (Test-Path -LiteralPath $backup -PathType Container) {
            Move-Item -LiteralPath $backup -Destination $target
            Start-Process -FilePath (Join-Path $target __OLD_EXE__) -WorkingDirectory $target
        }
        throw
    }
} catch {
    $_ | Out-File -FilePath (Join-Path $env:TEMP 'stagepulse-jarvis-update-error.txt') -Encoding utf8
    exit 1
}
""".replace("__TARGET__", ps_quote(target_text)).replace(
            "__STAGE__", ps_quote(stage_text)
        ).replace("__NEW_EXE__", ps_quote(new_exe_name)).replace(
            "__OLD_EXE__", ps_quote(old_exe_name)
        ).replace("__PARENT_PID__", str(pid_to_wait))

        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        arguments = f"-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {encoded}"
        install_dir_writable = os.access(str(target_dir), os.W_OK)

        if os.name == "nt" and not install_dir_writable:
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "powershell.exe", arguments, None, 0
            )
            if result <= 32:
                raise OSError("Yükseltilmiş güncelleme işlemi başlatılamadı.")
        else:
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive",
                 "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                close_fds=True,
            )
        return "Güncelleme doğrulandı. JARVIS kapatılıp güncellenecek ve yeniden açılacak."
