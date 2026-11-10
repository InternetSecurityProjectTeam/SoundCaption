@echo off
rem SoundCaption - double-click to start (no install needed)
cd /d "%~dp0"
start "" "%~dp0runtime\pythonw.exe" "%~dp0launcher\boot.py" %*
