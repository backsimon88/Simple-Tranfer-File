@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher ^("py"^) was not found. Install Python for Windows first.
    exit /b 1
)

echo Installing Windows build dependency...
py -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

echo Cleaning previous Windows build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building Windows application bundle...
py -m PyInstaller --noconfirm "Simple Transfer File Server.spec"
if errorlevel 1 exit /b 1

if not exist release mkdir release

echo Creating release zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\Simple Transfer File Server\*' -DestinationPath 'release\Simple-Transfer-File-Server-Windows.zip' -Force"
if errorlevel 1 exit /b 1

echo.
echo Windows build complete:
echo   dist\Simple Transfer File Server\Simple Transfer File Server.exe
echo   release\Simple-Transfer-File-Server-Windows.zip