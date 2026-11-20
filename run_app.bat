@echo off
chcp 65001 >nul
title TikTok Manager Pro - Khoi dong ung dung
echo ========================================================
echo        TIKTOK MANAGER PRO - AUTO UPLOAD TOOL
echo ========================================================
echo Dang khoi dong ung dung...

cd /d "%~dp0"

set PYTHON_CMD=python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" (
        set PYTHON_CMD="%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    )
)

%PYTHON_CMD% app_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Co loi khi khoi chay ung dung!
    pause
)
