@echo off
chcp 65001 >nul
rem 문제가 생겼을 때 쓰는 실행: 검은 창에 진행 상황과 오류가 그대로 보임
cd /d "%~dp0"
set "PYTHONUNBUFFERED=1"
"%~dp0runtime\python.exe" "%~dp0launcher\boot.py" %*
echo.
echo 앱이 닫혔어요. 오류가 있었다면 위에 보여요. 기록은 logs 폴더에도 있어요.
pause
