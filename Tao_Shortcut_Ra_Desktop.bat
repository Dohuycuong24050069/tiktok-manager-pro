@echo off
chcp 65001 >nul
echo Dang tao Shortcut tren Desktop cua ban...

set SCRIPT_DIR=%~dp0
set TARGET=%SCRIPT_DIR%run_app.bat
set SHORTCUT=%USERPROFILE%\Desktop\TikTok Manager Pro.lnk

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Description = 'Tool Quan Ly & Dang Video TikTok'; $s.Save()"

if exist "%SHORTCUT%" (
    echo [THANH CONG] Da tao shortcut "TikTok Manager Pro" tren Man hinh Desktop!
) else (
    echo [!] Khong the tao shortcut tu dong, ban co the nhap chuot phai vao run_app.bat chon Send to -> Desktop.
)
pause
