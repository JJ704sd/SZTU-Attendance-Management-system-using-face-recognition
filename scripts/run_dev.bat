@echo off
REM scripts\run_dev.bat — Windows 启动脚本 (W14+ 修复: 用绝对路径 .venv)
REM 之前用 `python -m src.main` 会调到 PATH 里的系统 Python,
REM 系统 Python 缺包 (qrcode 等) 时会 ModuleNotFoundError.
REM 现在用绝对路径 .venv 永远能跑.
REM
REM 用法：scripts\run_dev.bat

cd /d "%~dp0\.."
".venv\Scripts\python.exe" -m src.main
if errorlevel 1 (
    echo.
    echo [错误] GUI 启动失败
    pause
)
