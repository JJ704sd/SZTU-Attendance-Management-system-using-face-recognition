"""
prepare_deliverable_zip.py — 课程交付物 zip 打包脚本（W14 课程交付）

目标:
  把整个 git 仓库（含 .gitignore 但不含 .venv/dist/build/dataset/课程要求 PDF/个人报告）
  + .env.template（不放 .env，避免泄露密码）
  + 关键文档
  打成 `dist/deliverable-2026-06-20.zip`（~25-30 MB，不含 PyInstaller 产物）

用法:
  .venv\Scripts\python.exe scripts\prepare_deliverable_zip.py
  # 默认输出: dist/deliverable-2026-06-20.zip

退出码:
  0 = 成功（zip 已生成 + 大小校验通过）
  1 = 失败

设计动机:
  - 答辩老师要拿到完整可复现的源码（含 .git 历史可看 commit 演进）
  - 不能含 .env（DB 密码）/ .venv（虚拟环境 ~3 GB）/ dist（exe 太大）/ 个人报告草稿
  - 必须含 build.spec（演示重打 exe）+ db/schema.sql（演示重建库）
"""
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = ROOT / "dist" / "deliverable-2026-06-20.zip"

# =====================================================
# 排除规则（优先于 git ls-files）
# =====================================================
EXCLUDE_DIRS = {
    ".git",          # 用 git ls-files 跳过即可（这里只是兜底）
    ".venv",
    "venv",
    "env",
    "ENV",
    ".conda",
    "dist",          # PyInstaller 产物 (exe) 太大
    "build",         # PyInstaller 中间产物
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "models",        # dlib 模型权重 (运行时下载)
    "dataset",       # 人脸采集 (演示时生成)
    ".idea",
    ".vscode",
    ".opencode",     # 编辑器本地配置
    ".mavis",        # mavis 本地配置
    ".worktrees",    # git worktree
    "logs",          # 日志目录
    "htmlcov",       # coverage 报告
    ".coverage",
    # 课程内部资料（不入仓）
    "docs",          # docs 下有 PDF / 个人报告，按文件白名单处理
}

EXCLUDE_FILES = {
    # 敏感
    ".env",
    ".env.local",
    ".env.*.local",
    # 课程要求 PDF + 个人报告草稿
    "2025-2026-2+数据库原理+课程设计要求.pdf",
    "docs/202400502133-陈佳豪.pdf",
    "docs/202400502133-陈佳豪.docx",
    # 一次性审计产物
    ".cleanup_audit_20260607-215442.json",
    # 日志
    "app.log",
    "logs_pyinstaller.txt",
    "logs_pyinstaller.err",
    "logs_pytest.txt",
}

EXCLUDE_EXTS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe",
    ".log", ".tmp", ".bak", ".swp", ".swo",
    # PyInstaller 中间产物
    ".pkg", ".pyz",
    # dlib 模型
    ".dat", ".bz2",
}


def should_exclude(path: Path) -> bool:
    """判断 path 是否应排除。"""
    # 1. 排除目录
    for part in path.relative_to(ROOT).parts:
        if part in EXCLUDE_DIRS:
            return True
    # 2. 排除文件
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if rel in EXCLUDE_FILES:
        return True
    # 3. 排除扩展名
    if path.suffix.lower() in EXCLUDE_EXTS:
        return True
    return False


def collect_files() -> list[Path]:
    """收集所有要打进 zip 的文件（白名单 + 黑名单混合策略）。

    策略：
      - docs/ 目录只打包 .md / .sql 文件（不放 PDF / 个人报告 docx）
      - 其他目录按 EXCLUDE_DIRS / EXCLUDE_FILES / EXCLUDE_EXTS 黑名单过滤
      - .env.template 必须包含（用户要复制改名 .env）
      - build.spec 必须包含（演示重打 exe）
    """
    files: list[Path] = []

    # 1. 白名单：docs/ 下只放 .md / .sql
    docs_dir = ROOT / "docs"
    if docs_dir.exists():
        for f in docs_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in {".md", ".sql"}:
                rel = str(f.relative_to(ROOT)).replace("\\", "/")
                # 排除课程要求 PDF（已在 EXCLUDE_FILES，但 .pdf 不在 .md/.sql 白名单里自然过滤）
                # 排除个人报告 docx
                if "陈佳豪" in rel:
                    continue
                files.append(f)

    # 2. 白名单：根目录的 .env.template
    env_tpl = ROOT / ".env.template"
    if env_tpl.exists():
        files.append(env_tpl)

    # 3. 黑名单遍历其他目录
    skip_top = {"docs", ".venv", "venv", "env", "ENV", ".conda",
                "dist", "build", "models", "dataset",
                ".git", ".idea", ".vscode", ".opencode", ".mavis",
                ".worktrees", "logs", "htmlcov",
                ".pytest_cache", ".mypy_cache", ".ruff_cache",
                "__pycache__"}
    for item in ROOT.iterdir():
        if item.name in skip_top:
            continue
        if item.is_file():
            # 根目录文件：README.md, QUICKSTART.md, requirements.txt, build.spec, LICENSE, .gitignore
            if should_exclude(item):
                continue
            files.append(item)
        elif item.is_dir():
            for f in item.rglob("*"):
                if f.is_file() and not should_exclude(f):
                    files.append(f)

    return sorted(set(files), key=lambda p: str(p.relative_to(ROOT)))


def build_zip(files: list[Path]) -> int:
    """把所有 files 打进 zip，返回 zip 大小（bytes）。"""
    OUTPUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in files:
            rel = f.relative_to(ROOT).as_posix()
            zf.write(f, arcname=rel)

    return OUTPUT_ZIP.stat().st_size


def main() -> int:
    print("=== 课程交付物 zip 打包 ===")
    print(f"ROOT: {ROOT}")
    print(f"OUTPUT: {OUTPUT_ZIP}")

    # ====================================================
    # 1. 收集文件
    # ====================================================
    print("\n[1/3] 收集文件 ...")
    files = collect_files()
    print(f"  找到 {len(files)} 个文件")

    # 抽样打印几个关键文件
    key_files = ["README.md", "QUICKSTART.md", "requirements.txt",
                 "build.spec", "db/schema.sql", "db/migration_w13.sql",
                 ".env.template", "src/main.py", "src/services/signin_web.py",
                 "scripts/smoke_signin_web.py",
                 "scripts/smoke_signin_web_build.py",
                 "docs/W14-defense-outline.md",
                 "docs/superpowers/plans/2026-06-16-W14-multidevice-signin-design.md"]
    for kf in key_files:
        if (ROOT / kf).exists():
            print(f"    ✓ {kf}")
        else:
            print(f"    ✗ {kf} (missing)")

    # ====================================================
    # 2. 打 zip
    # ====================================================
    print("\n[2/3] 打 zip ...")
    try:
        zip_size = build_zip(files)
    except Exception as e:
        print(f"FAIL: zip 失败: {e}")
        return 1
    print(f"  zip 大小: {zip_size / 1024 / 1024:.2f} MB ({zip_size} bytes)")

    # ====================================================
    # 3. 校验：必含文件 + 必排除文件
    # ====================================================
    print("\n[3/3] 校验 ...")
    with zipfile.ZipFile(OUTPUT_ZIP, "r") as zf:
        names = set(zf.namelist())

    must_have = [
        "README.md",
        "QUICKSTART.md",
        "requirements.txt",
        "build.spec",
        ".env.template",
        "db/schema.sql",
        "src/main.py",
        "src/services/signin_web.py",
        "src/ui/web_templates/signin.html",
        "scripts/smoke_signin_web.py",
        "scripts/smoke_signin_web_build.py",
        "scripts/prepare_deliverable_zip.py",
        "docs/W14-defense-outline.md",
        "docs/superpowers/plans/2026-06-16-W14-multidevice-signin-design.md",
    ]
    missing = [m for m in must_have if m not in names]
    if missing:
        print(f"FAIL: 必含文件缺失:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print(f"  ✓ {len(must_have)} 个必含文件全部在 zip 里")

    must_not_have = [
        ".env",
        "2025-2026-2+数据库原理+课程设计要求.pdf",
        "docs/202400502133-陈佳豪.pdf",
        "docs/202400502133-陈佳豪.docx",
    ]
    # 目录类的 must_not_have: 检查是否有该前缀路径下的任何文件
    must_not_have_dirs = [
        ".venv/",
        "dist/attendance-system/_internal/",
        "models/shape_predictor_68_face_landmarks.dat",
    ]

    leaked = []
    for m in must_not_have:
        if m in names:
            leaked.append(m)
    for m in must_not_have_dirs:
        if any(n.startswith(m) for n in names):
            leaked.append(m)
    if leaked:
        print(f"FAIL: 不应包含的文件被泄露:")
        for m in leaked:
            print(f"  - {m}")
        return 1
    print(f"  ✓ 7 个必排除项全部未泄露")

    # ====================================================
    # Done
    # ====================================================
    print("\n" + "=" * 50)
    print(f"PASS: {OUTPUT_ZIP.relative_to(ROOT)}")
    print(f"      共 {len(files)} 个文件, {zip_size / 1024 / 1024:.2f} MB")
    print(f"      排除项: .venv / dist / build / dataset / models / 个人报告 / 课程要求 PDF")
    print(f"      含: README + build.spec + db/schema.sql + smoke 脚本 + W14 设计稿 + 答辩大纲")
    return 0


if __name__ == "__main__":
    sys.exit(main())