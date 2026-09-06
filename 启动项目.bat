@echo off
set ROOT=%~dp0
set PYTHON=D:\anaconda\python.exe

echo.
echo [1] Killing old processes...
call :kill_port 5000
call :kill_port 5100
call :kill_port 3001
call :kill_port 3002
for /f "tokens=2" %%i in ('wmic process where "name='python.exe' and commandline like '%%app_v2.py%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do taskkill /PID %%i /F >nul 2>&1
for /f "tokens=2" %%i in ('wmic process where "name='python.exe' and commandline like '%%integration_demo%%app.py%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do taskkill /PID %%i /F >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2] Starting main backend  (port 5000)...
start "Backend-5000" cmd /k "cd /d "%ROOT%" && %PYTHON% server\app_v2.py"
timeout /t 1 /nobreak >nul

echo [2.5] Waiting for main backend to be ready (max 60s)...
set /a _tries=0
:wait_backend
set /a _tries+=1
if %_tries% GTR 60 (
    echo [WARN] Main backend /api/health not ready after 60s, continuing anyway...
    goto backend_ready
)
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5000/api/health' -TimeoutSec 2 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_backend
)
:backend_ready
echo Main backend is ready.

echo [3] Starting demo backend  (port 5100)...
start "Backend-5100" cmd /k "cd /d "%ROOT%" && %PYTHON% integration_demo\backend\app.py"
timeout /t 1 /nobreak >nul

echo [4] Starting main frontend (port 3001)...
start "Frontend-3001" cmd /k "cd /d "%ROOT%frontend" && npm run dev"
timeout /t 1 /nobreak >nul

echo [5] Starting demo frontend (port 3002)...
start "Frontend-3002" cmd /k "cd /d "%ROOT%integration_demo\frontend" && npm run dev"

echo.
echo Waiting for frontends to warm up...
timeout /t 6 /nobreak >nul

echo Opening demo at http://localhost:3002 ...
start "" "http://localhost:3002"

echo.
echo All services started. You can close this window.
echo.
pause

:kill_port
set PORT=%~1
for /f "tokens=5" %%i in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do taskkill /PID %%i /F >nul 2>&1
exit /b 0
