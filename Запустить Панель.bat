@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Панель Сервера Terraria

if exist "%~dp0Запустить Панель.exe" (
    start "" "%~dp0Запустить Панель.exe"
    exit
)

if exist "%~dp0Panel\TerrariaPanel.exe" (
    start "" "%~dp0Panel\TerrariaPanel.exe"
    exit
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" pythonw "%~dp0Panel\TerrariaPanel.pyw"
    exit
)

where python >nul 2>&1
if not errorlevel 1 (
    start "" python "%~dp0Panel\TerrariaPanel.pyw"
    exit
)

echo [ОШИБКА] Не удалось найти "Запустить Панель.exe" или установленный Python.
pause
