@echo off
cd /d "%~dp0"
py -3 build_lobby.py
if errorlevel 1 python build_lobby.py
pause
