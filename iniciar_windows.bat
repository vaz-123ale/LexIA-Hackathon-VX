@echo off
cd /d "%~dp0"
echo LexIA - abrindo em http://localhost:8765
where py >NUL 2>NUL
if %ERRORLEVEL% EQU 0 (
  py -3 -m app.server
) else (
  python -m app.server
)
pause
