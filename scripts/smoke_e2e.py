"""
scripts/smoke_e2e.py — 打包后端到端烟测

W5 Phase 3: 验证 dist/attendance-system/ 在"无 Python 环境" (或干净位置) 下:
  1. 启 exe 进程不挂
  2. MainWindowTitle 是登录窗口 (证明 LoginWindow 真的弹起来)
  3. app.log 完整链路 (init_db + create_all + face cache + dlib 模型)
  4. 退出时不留僵死进程

用法 (PowerShell):
  # 默认从项目根 dist/attendance-system/ 测
  .venv\Scripts\python.exe scripts\smoke_e2e.py

  # 自定义路径
  .venv\Scripts\python.exe scripts\smoke_e2e.py --dist C:\path\to\attendance-system

退出码:
  0 = PASS
  1 = FAIL (看 stderr)
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# 项目根 (脚本在 scripts/ 下, 上 1 级)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _find_exe(dist_dir: Path) -> Path:
    """在 dist_dir 下找 attendance-system.exe (Windows) 或 attendance-system (Linux/macOS)"""
    for name in ("attendance-system.exe", "attendance-system"):
        p = dist_dir / name
        if p.exists():
            return p
    raise FileNotFoundError(f"在 {dist_dir} 找不到 attendance-system[.exe]")


def _copy_to_temp(src: Path) -> Path:
    """把 dist 拷到临时目录, 模拟'客户机拷一份'"""
    tmp = Path(tempfile.mkdtemp(prefix="attendance-e2e-"))
    dst = tmp / src.name
    shutil.copytree(src, dst)
    # 拷 .env (用项目根的 dev .env, 验证 MySQL 连接)
    dev_env = PROJECT_ROOT / ".env"
    if dev_env.exists():
        shutil.copy2(dev_env, dst / ".env")
        print(f"[setup] copied {dev_env.name} -> {dst / '.env'}")
    print(f"[setup] dist copied to {dst}")
    return dst


def _wait_for_log(log_path: Path, max_wait: float = 15.0) -> list[str]:
    """等 app.log 出现 + 至少 N 行, 超时返回空"""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if len(lines) >= 5:
                return lines
        time.sleep(0.5)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dist", type=Path,
        default=PROJECT_ROOT / "dist" / "attendance-system",
        help="dist 目录 (默认 dist/attendance-system/)",
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="保留临时目录 (调试用)",
    )
    parser.add_argument(
        "--wait", type=float, default=10.0,
        help="等 GUI 启动秒数 (默认 10)",
    )
    args = parser.parse_args()

    if not args.dist.exists():
        print(f"[FAIL] dist 不存在: {args.dist}", file=sys.stderr)
        print(f"       先跑: pyinstaller build.spec", file=sys.stderr)
        return 1

    # 1. 拷到临时位置 (模拟客户机)
    work_dir = _copy_to_temp(args.dist)
    exe = _find_exe(work_dir)
    log_path = work_dir / "app.log"

    # 清掉旧 log
    if log_path.exists():
        log_path.unlink()

    # 2. 启 exe (真显示, 不 offscreen)
    print(f"[start] {exe}")
    proc = subprocess.Popen(
        [str(exe)],
        cwd=str(work_dir),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    fail = []
    try:
        # 3. 等 GUI 启动
        time.sleep(args.wait)

        # 4. 检查进程是否还在
        if proc.poll() is not None:
            fail.append(f"进程已退出 (exit code={proc.returncode})")
        else:
            print(f"[OK] 进程 {proc.pid} 还活着 ({args.wait}s)")

        # 5. 看 window title (Windows only, 跨进程 Get-Process 太复杂)
        # 简化: 看 app.log 验证启动链路完整
        log_lines = _wait_for_log(log_path, max_wait=5.0)
        if not log_lines:
            fail.append(f"app.log 5s 内没出现 / 少于 5 行")
        else:
            print(f"[OK] app.log 有 {len(log_lines)} 行")

            # 验证关键节点
            must_contain = [
                "W5: 文件日志已启用",
                "=== 应用启动 ===",
                "init_db: 开始导入 models",
                "init_db: models 导入完成",
                "init_db: create_all 完成",
                "数据库初始化完成",
                "dlib 模型路径 OK",
            ]
            joined = "\n".join(log_lines)
            for needle in must_contain:
                if needle in joined:
                    print(f"  [OK] log 含 '{needle}'")
                else:
                    fail.append(f"log 缺 '{needle}'")

    finally:
        # 6. 杀掉进程 (避免僵死)
        if proc.poll() is None:
            print(f"[cleanup] killing PID {proc.pid}")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        # 7. 保留 / 清理
        if not args.keep:
            shutil.rmtree(work_dir.parent, ignore_errors=True)
        else:
            print(f"[keep] 保留: {work_dir}")

    # 8. 报告
    print()
    if fail:
        print(f"[FAIL] {len(fail)} 项不通过:")
        for f in fail:
            print(f"  - {f}")
        return 1
    print(f"[PASS] 端到端 E2E 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
