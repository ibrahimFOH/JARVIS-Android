from pathlib import Path
import subprocess
ROOT=Path(r"C:\Jarvis\J.A.R.V.I.S")
PY=ROOT/"venv"/"Scripts"/"python.exe"
subprocess.check_call([str(PY),"-m","pip","install","pyinstaller"])
subprocess.check_call([str(PY),"-m","PyInstaller","--noconfirm","--clean","--name","JARVIS","--onedir","--windowed","main.py"],cwd=ROOT)
print("EXE:",ROOT/"dist"/"JARVIS")
