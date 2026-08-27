@echo off
chcp 65001 > nul
cd /d "%~dp0"
py -3 build_lobby.py
if errorlevel 1 (
  echo.
  echo py -3 で実行できなかったため python でも試します。
  python build_lobby.py
)
echo.
pause
