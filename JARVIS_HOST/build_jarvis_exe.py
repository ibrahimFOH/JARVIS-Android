"""Build the Stagepulse JARVIS Windows GUI as one standalone EXE."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
EXE_NAME = "StagepulseJARVIS"


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.check_call(list(args), cwd=ROOT)


def main() -> int:
    run(sys.executable, "-m", "pip", "install", "--upgrade", "pip")
    run(sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"), "pyinstaller")
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", EXE_NAME,
        "--add-data", "config/config.example.json;config",
        "--add-data", "VERSION;.",
        "--collect-all", "customtkinter",
        "--collect-all", "pystray",
        "--collect-all", "pyttsx3",
        "--collect-all", "speech_recognition",
        "--collect-all", "pvporcupine",
        "--collect-all", "pyaudio",
        "--collect-all", "PIL",
        "--hidden-import", "win32timezone",
        "--hidden-import", "pythoncom",
        "--hidden-import", "pywintypes",
        "main.py",
    ]
    run(*args)
    exe = ROOT / "dist" / f"{EXE_NAME}.exe"
    if not exe.is_file() or exe.stat().st_size < 1_000_000:
        raise RuntimeError(f"Tek dosya EXE doğrulanamadı: {exe}")
    print(f"BUILD OK: {exe} ({exe.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
