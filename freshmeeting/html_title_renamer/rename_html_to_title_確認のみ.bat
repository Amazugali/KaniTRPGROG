@echo off
chcp 65001 > nul
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%CD%"

echo 実際には変更せず、リネーム予定だけ確認します。
echo 対象: %TARGET%
echo.

py -3 rename_html_to_title.py "%TARGET%" --recursive --dry-run
if errorlevel 1 (
  python rename_html_to_title.py "%TARGET%" --recursive --dry-run
)

echo.
pause
