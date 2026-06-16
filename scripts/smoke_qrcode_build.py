"""
smoke_qrcode_build.py — 烟测脚本：验证 PyInstaller 打包的 exe 包含 qrcode 模块。

W14 修复背景:
  W5 PyInstaller 打包时还没有二维码签到功能 (W13+ 才加)，
  build.spec 的 hiddenimports 没列 qrcode，dist/_internal 缺 qrcode 目录，
  运行时报 No module named 'qrcode'。
  修复: 把 qrcode 加入 hiddenimports 并重打 exe。
  本脚本验证: 重打的 exe 能在 PYZ archive 里找到完整 qrcode 模块树。

用法:
  python scripts/smoke_qrcode_build.py
  # 默认检查 dist/attendance-system/attendance-system.exe

退出码:
  0 = qrcode 完整在 exe 里
  1 = 缺少必需模块
  2 = exe 不存在 (没打过包)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE_PATH = ROOT / "dist" / "attendance-system" / "attendance-system.exe"

# 必须出现在 PYZ 里的 qrcode 子模块 (qrcode.make() 路径会触达)
REQUIRED_QRCODE_MODULES = {
    "qrcode",
    "qrcode.main",
    "qrcode.base",
    "qrcode.constants",
    "qrcode.exceptions",
    "qrcode.util",
    "qrcode.image",
    "qrcode.image.pil",       # 默认 factory
    "qrcode.image.base",
    "qrcode.image.pure",
    "qrcode.compat",
    "qrcode.compat.etree",
}

# ArchiveViewer 输出格式形如: " qrcode" 或 " qrcode.image.pil" (前导空格)
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
        print("  提示: 先跑 `python -m PyInstaller build.spec --noconfirm`", file=sys.stderr)
        return 2

    print(f"[smoke] scanning {EXE_PATH.name} ...")
    try:
        modules = list_archive_modules(EXE_PATH)
    except Exception as e:
        print(f"FAIL: archive scan error: {e}", file=sys.stderr)
        return 1

    missing = REQUIRED_QRCODE_MODULES - modules
    if missing:
        print(f"FAIL: {len(missing)} required qrcode modules missing in exe:", file=sys.stderr)
        for m in sorted(missing):
            print(f"  - {m}", file=sys.stderr)
        print("\n修复: 在 build.spec 的 hiddenimports 里加上缺失模块，重打 exe。", file=sys.stderr)
        return 1

    print(f"OK: all {len(REQUIRED_QRCODE_MODULES)} required qrcode modules present in exe")
    print(f"OK: total {len(modules)} modules in exe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
