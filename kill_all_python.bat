@echo off
REM kill_all_python.bat
REM W15+ : clean up all python.exe (GUI residual)
REM          run before start.bat to avoid port conflict
REM
REM W15+ fix: ALL ASCII, no Chinese comments. cmd 5.1 with GBK
REM          default codepage parses UTF-8 bytes wrong, treating
REM          Chinese text in REM as commands. Use ASCII only.

chcp 65001 >nul
echo ============================================
echo  KILL all python.exe (GUI residual)
echo  Safe: does not touch cmd / powershell / mavis
echo ============================================
taskkill /F /IM python.exe 2>nul
if errorlevel 1 (
    echo.
    echo [INFO] no python.exe running (already clean)
) else (
    echo.
    echo [OK] all python.exe killed
)
echo.
echo Next: double-click start.bat to restart GUI
pause
