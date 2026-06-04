@echo off
REM scripts\run_dev.bat — Windows 启动脚本
REM 用法：scripts\run_dev.bat
cd /d "%~dp0\.."
python -m src.main
