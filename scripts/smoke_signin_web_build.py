"""
smoke_signin_web_build.py — 烟测脚本：验证 PyInstaller 打包的 exe 包含 W14 FastAPI/H5 服务模块。

W14 修复背景:
  W13+ PyInstaller 打 exe 时还没有多端登录签到 (W14 才加),
  build.spec 的 hiddenimports 没列 fastapi/uvicorn/starlette/jinja2/httpx，
  dist/_internal 缺整个 FastAPI 目录 → 运行时报 No module named 'fastapi'。
  修复: 把 fastapi/uvicorn/starlette/jinja2/httpx 子模块加入 hiddenimports 并重打 exe。
  本脚本验证: 重打的 exe 能在 PYZ archive 里找到完整的 FastAPI 嵌入栈。

用法:
  python scripts/smoke_signin_web_build.py
  # 默认检查 dist/attendance-system/attendance-system.exe

退出码:
  0 = FastAPI 嵌入栈完整在 exe 里
  1 = 缺少必需模块
  2 = exe 不存在 (没打过包)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE_PATH = ROOT / "dist" / "attendance-system" / "attendance-system.exe"

# 必须出现在 PYZ 里的 W14 服务模块
# (signin_web.py 实际 import + uvicorn/fastapi 启动链路会触达的子模块)
REQUIRED_SIGNIN_WEB_MODULES = {
    # --- FastAPI 核心 (signin_web.py 直接 import) ---
    "fastapi",
    "fastapi.applications",
    "fastapi.dependencies",
    "fastapi.routing",
    "fastapi.templating",        # Jinja2Templates
    "fastapi.responses",         # HTMLResponse, JSONResponse
    # --- uvicorn (SigninWebServer 跑在 uvicorn.Server) ---
    "uvicorn",
    "uvicorn.config",            # uvicorn.Config
    "uvicorn.server",            # uvicorn.Server
    "uvicorn.loops",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    # --- starlette (FastAPI 的 ASGI 底层, PyInstaller 静态分析抓不到) ---
    "starlette",
    "starlette.applications",
    "starlette.routing",
    "starlette.responses",
    # --- jinja2 (Jinja2Templates 用, H5 签到页渲染) ---
    "jinja2",
    "jinja2.ext",
    # --- httpx (smoke 脚本用, 不强依赖但 build.spec 已列, 顺便校验) ---
    "httpx",
    "httpx._api",
    "httpx._client",
}

# ArchiveViewer 输出格式形如: " fastapi" 或 " fastapi.applications" (前导空格)
# 跳过头部 banner / 数字统计行
MODULE_LINE_RE = re.compile(r"^\s+([a-zA-Z_][\w.]*)\s*$")


def list_archive_modules(exe_path: Path) -> set[str]:
    """递归列出 exe 内所有 PYZ module 名。"""
    from PyInstaller.utils.cliutils.archive_viewer import ArchiveViewer
    import io
    from contextlib import redirect_stdout

    # ArchiveViewer(non-interactive) 会把内容 print 到 stdout
    buf = io.StringIO()
    av = ArchiveViewer(str(exe_path), False, True, True)
    with redirect_stdout(buf):
        av.main()

    modules: set[str] = set()
    for line in buf.getvalue().splitlines():
        m = MODULE_LINE_RE.match(line)
        if m:
            modules.add(m.group(1))
    return modules


def main() -> int:
    if not EXE_PATH.exists():
        print(f"FAIL: exe not found at {EXE_PATH}", file=sys.stderr)
        print("  提示: 先跑 `.venv\\Scripts\\python.exe -m PyInstaller build.spec --noconfirm`",
              file=sys.stderr)
        return 2

    print(f"[smoke] scanning {EXE_PATH.name} ...")
    try:
        modules = list_archive_modules(EXE_PATH)
    except Exception as e:
        print(f"FAIL: archive scan error: {e}", file=sys.stderr)
        return 1

    missing = REQUIRED_SIGNIN_WEB_MODULES - modules
    if missing:
        print(f"FAIL: {len(missing)} required W14 signin-web modules missing in exe:",
              file=sys.stderr)
        for m in sorted(missing):
            print(f"  - {m}", file=sys.stderr)
        print("\n修复: 在 build.spec 的 hiddenimports 里加上缺失模块，重打 exe。",
              file=sys.stderr)
        return 1

    print(f"OK: all {len(REQUIRED_SIGNIN_WEB_MODULES)} required W14 signin-web modules "
          f"present in exe")
    print(f"OK: total {len(modules)} modules in exe")
    return 0


if __name__ == "__main__":
    sys.exit(main())