"""Safe self-updater for the Stagepulse JARVIS Windows onedir build."""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

REPOSITORY = "ibrahimFOH/JARVIS-Android"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
TIMEOUT = (10, 90)


def _current_version():
    try:
        from version import __version__
        return str(__version__)
    except Exception:
        return "0.0.0"


def check_latest_release():
    """Return a newer published Windows release, or None when up to date."""
    response = requests.get(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Stagepulse-JARVIS-Updater"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    release = response.json()
    if release.get("draft") or release.get("prerelease"):
        return None
    tag = str(release.get("tag_name", "")).lstrip("vV")
    if not tag or tag == _current_version():
        return None
    assets = release.get("assets", [])
    asset = next((item for item in assets if item.get("name") == "StagepulseJARVIS-Windows.zip"), None)
    if not asset or not asset.get("browser_download_url"):
        return None
    return {
        "version": tag,
        "url": asset["browser_download_url"],
        "asset_size": int(asset.get("size", 0)),
        "html_url": release.get("html_url", ""),
    }


def download_and_prepare_update(release):
    """Download a release, validate the archive, and stage a replace-on-exit script."""
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Otomatik EXE güncellemesi yalnızca paketlenmiş Windows uygulamasında çalışır.")
    install_dir = Path(sys.executable).resolve().parent
    if not (install_dir / "StagepulseJARVIS.exe").exists():
        raise RuntimeError("JARVIS kurulum klasöründe ana EXE bulunamadı.")
    temp_root = Path(tempfile.mkdtemp(prefix="StagepulseJARVIS-update-"))
    archive_path = temp_root / "update.zip"
    extract_dir = temp_root / "extracted"
    extract_dir.mkdir()
    try:
        with requests.get(release["url"], stream=True, timeout=TIMEOUT,
                          headers={"User-Agent": "Stagepulse-JARVIS-Updater"}) as response:
            response.raise_for_status()
            total = 0
            with archive_path.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > 800 * 1024 * 1024:
                        raise RuntimeError("Güncelleme paketi beklenenden büyük; güvenlik nedeniyle durduruldu.")
                    stream.write(chunk)
        if total < 1024:
            raise RuntimeError("İndirilen güncelleme paketi boş veya eksik.")
        with zipfile.ZipFile(archive_path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise RuntimeError("Güncelleme ZIP doğrulaması başarısız: " + bad_member)
            archive.extractall(extract_dir)
        candidates = list(extract_dir.rglob("StagepulseJARVIS.exe"))
        if len(candidates) != 1:
            raise RuntimeError("Güncelleme paketinde tek bir StagepulseJARVIS.exe bulunamadı.")
        source_dir = candidates[0].parent
        script = temp_root / "apply_update.cmd"
        # The script waits for the current process to exit before replacing files.
        script.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            f'set "SOURCE={source_dir}"\r\n'
            f'set "TARGET={install_dir}"\r\n'
            'set "EXE=StagepulseJARVIS.exe"\r\n'
            ':waitloop\r\n'
            'tasklist /FI "IMAGENAME eq %EXE%" 2>NUL | find /I "%EXE%" >NUL\r\n'
            'if not errorlevel 1 (timeout /T 2 /NOBREAK >NUL & goto waitloop)\r\n'
            'robocopy "%SOURCE%" "%TARGET%" /E /R:2 /W:1 >NUL\r\n'
            'if errorlevel 8 (echo Update copy failed. Check write permissions. & pause & exit /b 1)\r\n'
            'start "" "%TARGET%\\%EXE%"\r\n'
            'timeout /T 2 /NOBREAK >NUL\r\n'
            f'rmdir /S /Q "{temp_root}"\r\n'
            'endlocal\r\n',
            encoding="utf-8",
        )
        subprocess.Popen(["cmd.exe", "/c", "start", "", str(script)],
                         cwd=str(install_dir), close_fds=True)
        return "Güncelleme indirildi. JARVIS şimdi kapatılacak, dosyalar yenilenecek ve yeniden açılacak."
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
