@echo off
chcp 65001 >nul
rem SoundCaption 시연용: 더블클릭 한 번이면 (처음엔 자동으로 풀고) 실행
cd /d "%~dp0"
set "PS1=%~dp0source\_setup\setup.ps1"
if not exist "%PS1%" set "PS1=%~dp0setup.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Root "%~dp0."
if errorlevel 1 (
  echo.
  echo 문제가 생겼어요. 위 메시지를 확인해 주세요.
  pause
  exit /b 1
)
timeout /t 5 >nul
