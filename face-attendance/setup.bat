@echo off
echo.
echo  FaceAttend — Windows Setup
echo.

setlocal EnableExtensions EnableDelayedExpansion

:: Check Python
set "PY=python"
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo  Python not found. Install Python 3.13 from https://python.org
    pause & exit /b 1
)
for /f "tokens=2 delims= " %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"
echo  Python %PYVER% found

:: Check Node
node --version >nul 2>&1
if errorlevel 1 (
    echo  Node.js not found. Download from https://nodejs.org
    pause & exit /b 1
)
echo  Node.js found

:: Backend
echo.
echo  Setting up backend...
cd backend
%PY% -m venv venv
call venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
call venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..
echo  Backend ready

:: Frontend
echo.
echo  Installing frontend packages...
cd frontend
call npm install
cd ..
echo  Frontend ready

echo.
echo  Setup complete! Run start.bat to launch.
pause
