@echo off
chcp 65001 > nul
cd /d "%~dp0"

set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%CD%"

echo HTML の title をファイル名に変更します。
echo 対象: %TARGET%
echo.
echo ※ 同名ファイルがある場合は (2), (3)... を付けます。
echo ※ title がないHTMLは変更しません。
echo.

py -3 rename_html_to_title.py "%TARGET%"
if errorlevel 1 (
  python rename_html_to_title.py "%TARGET%"
)

echo.
pause
