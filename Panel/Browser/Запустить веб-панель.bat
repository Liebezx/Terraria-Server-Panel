@echo off
setlocal
cd /d "%~dp0"
for %%I in ("%~dp0..\..") do set "TERRARIA_ROOT=%%~fI"
set "PANEL_HOST=127.0.0.1"
set "PANEL_PORT=8765"
set "PYTHON=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
start "Terraria Web Panel" "%PYTHON%" "%~dp0server.py"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8765"
echo.
echo Web panel started. Keep the Terraria Web Panel console open.
echo Browser address: http://127.0.0.1:8765
echo Close the console window to stop only the web panel.
endlocal
