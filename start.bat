@echo off
REM start.bat - 一键启动 GUI (项目根目录)
REM 用绝对路径 .venv python, 避免 PATH 里的系统 Python 缺包
REM
REM 重要: 不用 echo (xxx) 的语法, cmd 5.1 会把括号当 block 解析报错
REM       (echo "xxx" 才安全). 也不要用 echo 中文括号, 改用 ASCII 括号.
REM
REM W15+ 改动: 加 .venv 存在性检查, 拷到新机器没建 venv 时给明确提示
REM           (不再"一闪而过", 组员能知道下一步该做什么)

chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  Attendance System GUI starting...
echo  Python: .venv\Scripts\python.exe
echo ============================================
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo [ERROR] .venv\Scripts\python.exe not found.
    echo         请先建 venv + 装依赖:
    echo           python -m venv .venv
    echo           .venv\Scripts\Activate.ps1
    echo           pip install -r requirements.txt
    echo         详细见 docs\TEAM_SETUP.md
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m src.main
if errorlevel 1 (
    echo.
    echo [ERROR] GUI failed to start. Check .venv or see logs above.
    pause
)
