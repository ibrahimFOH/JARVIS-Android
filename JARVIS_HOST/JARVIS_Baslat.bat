@echo off
cd /d "C:\Jarvis\J.A.R.V.I.S"
if not exist "venv\Scripts\pythonw.exe" (echo venv bulunamadi&pause&exit /b 1)
start "" /b "venv\Scripts\pythonw.exe" main.py
