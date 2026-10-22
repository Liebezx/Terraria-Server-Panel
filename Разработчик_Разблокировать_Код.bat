@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Режим Разработчика - Разблокировка Кода

where python >nul 2>&1
if not errorlevel 1 (
    python "%~dp0Panel\scripts\developer_unlock.py"
    exit /b
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    pythonw "%~dp0Panel\scripts\developer_unlock.py"
    exit /b
)

echo [ОШИБКА] Python не обнаружен в системе.
pause
