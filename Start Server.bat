@echo off
cd /d "%~dp0"
tasklist /FI "IMAGENAME eq TShock.Server.exe" /NH | findstr /I /C:"TShock.Server.exe" >nul
if not errorlevel 1 goto already_running
set "DOTNET_ROOT=%~dp0dotnet"
TShock.Server.exe -world "%~dp0Worlds\FriendsWorld.wld" -port 7777 -maxplayers 8
pause
exit /b
:already_running
echo The Terraria server is already running. Do not start a second copy.
echo Close this window; the running server is still active.
pause