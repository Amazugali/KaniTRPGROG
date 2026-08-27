@echo off
chcp 65001 > nul
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%CD%"

echo HTML の title をファイル名に変更します。
echo 対象: %TARGET%
echo サブフォルダも含めて処理します。
echo.

py -3 rename_html_to_title.py "%TARGET%" --recursive
if errorlevel 1 (
  python rename_html_to_title.py "%TARGET%" --recursive
)

echo.
pause
