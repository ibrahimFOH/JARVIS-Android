"""Build the Windows JARVIS package from this checkout, not a machine-specific path."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
if not PYTHON.is_file():
    PYTHON = Path(sys.executable)

def run(*args):
    subprocess.check_call([str(PYTHON), *args], cwd=ROOT)

if not (ROOT / "config" / "config.example.json").is_file():
    raise SystemExit("Missing config/config.example.json; run this script from the complete JARVIS_HOST project.")

run("-m", "pip", "install", "--upgrade", "pyinstaller")
run("-m", "PyInstaller", "--noconfirm", "--clean", "--name", "JARVIS",
    "--onedir", "--contents-directory", ".", "--windowed",
    "--add-data", "config/config.example.json;config",
    "--add-data", "VERSION;.",
    "--collect-all", "customtkinter",
    "--collect-all", "pystray",
    "--collect-all", "pyttsx3",
    "--collect-all", "speech_recognition",
    "--collect-all", "pvporcupine",
    "--hidden-import", "win32timezone",
    "--hidden-import", "android_bridge",
    "main.py")

exe = ROOT / "dist" / "JARVIS" / "JARVIS.exe"
if not exe.is_file():
    raise SystemExit("Build failed: JARVIS.exe was not created.")
print("Build completed:", exe)
print("Copy the entire dist/JARVIS folder; do not copy only the EXE.")
