@echo off
echo.
echo  Starting FaceAttend...
echo.

:: Start Backend
echo  Starting backend on http://localhost:8000
start "FaceAttend Backend" cmd /k "cd backend && venv\Scripts\activate && python main.py"

:: Wait a moment
timeout /t 4 /nobreak >nul

:: Start Frontend
echo  Starting frontend on http://localhost:5173
start "FaceAttend Frontend" cmd /k "cd frontend && npm run dev"

timeout /t 4 /nobreak >nul

echo.
echo  ============================================
echo   FaceAttend is starting!
echo.
echo   Open: http://localhost:5173
echo   Admin:   admin / admin123
echo   Faculty: faculty / faculty123
echo  ============================================
echo.
start http://localhost:5173
pause
