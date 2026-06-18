"""
build_2_zips.py — 重新打 2 个课程交付 zip (W15+ 修复版)

跟旧 tmp_build_2_zips_v4.py 等价 (该脚本被 commit 5239032 清理), 但带 W15+ 修复.

产物:
  - 完整源代码.zip  (~350 KB / ~140 文件) - 老师/接手人/组员用
  - 智能考勤与实验室准入系统_设计方案.zip  (~400 MB / ~600 文件) - 课程提交用
    (改名为 <组长学号>_智能考勤与实验室准入系统_设计方案.zip 再交)

用法: .venv/Scripts/python.exe scripts/build_2_zips.py

W15+ 修复: 改用 os.walk 收 worktree 真实文件, 不依赖 git ls-files.
原因: commit 3550078 把 快速验证.md / submission/课程提交物清单.md add
      成 octal-escape 字符串 (而不是真 UTF-8 文件名), git index 跟工作区
      UTF-8 文件不匹配, 导致 git ls-files 漏掉这 2 个文件. 用 os.walk 收集
      才能保证中文文件名也打进去.
"""
import io
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(r'D:\Attendance-Management-system-using-face-recognition').resolve()
os.chdir(ROOT)

OUT_FULL = ROOT / "完整源代码.zip"
OUT_COURSE = ROOT / "智能考勤与实验室准入系统_设计方案.zip"
ARCHIVE = ROOT / "完整源代码-archive-2026-06-18.zip"
COURSE_ARCHIVE = ROOT / "智能考勤与实验室准入系统_设计方案-archive-2026-06-18.zip"

# 备份
print("[0/6] 备份旧 zip ...")
if OUT_FULL.exists():
    shutil.copy2(OUT_FULL, ARCHIVE)
    print(f"  备份 → {ARCHIVE.name} ({ARCHIVE.stat().st_size} bytes)")
if OUT_COURSE.exists():
    shutil.copy2(OUT_COURSE, COURSE_ARCHIVE)
    print(f"  备份 → {COURSE_ARCHIVE.name} ({COURSE_ARCHIVE.stat().st_size} bytes)")

# 1. 排除规则
EXCLUDE_TOP_DIRS = {
    ".venv", "venv", "env", "ENV", ".conda",
    "dist", "build",
    "models", "dataset",
    ".git", ".idea", ".vscode", ".opencode", ".mavis",
    ".worktrees", "logs", "htmlcov",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "__pycache__",
    "backups",  # 旧版脏目录
}
EXCLUDE_EXTS = {".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".dat", ".bz2", ".log"}
EXCLUDE_FILES = {
    "完整源代码.zip",
    "完整源代码-archive-2026-06-18.zip",
    "智能考勤与实验室准入系统_设计方案.zip",
    "智能考勤与实验室准入系统_设计方案-archive-2026-06-18.zip",
    "group-member-package(1).zip",
    "group-member-package-archive-2026-06-18.zip",
}

# 2. 用 os.walk 收 worktree 真实文件 (W15+ 修复: 不依赖 git ls-files, 解决中文文件名 bug)
print("\n[1/6] 收集 worktree 真实文件 (os.walk) ...")
src_files = []
for root, dirs, files in os.walk(ROOT):
    # 排除目录
    rel_root = Path(root).relative_to(ROOT)
    parts = rel_root.parts
    if parts and parts[0] in EXCLUDE_TOP_DIRS:
        # 跳过整个子树
        dirs[:] = []
        continue
    for f in files:
        rel = (rel_root / f).as_posix()
        if rel in EXCLUDE_FILES:
            continue
        if any(f.endswith(ext) for ext in EXCLUDE_EXTS):
            continue
        # 排除 dist/ 里的 zip 文件 (防止递归打 zip)
        if rel.endswith('.zip'):
            continue
        src_files.append(rel)
src_files.sort()
print(f"  os.walk 收集: {len(src_files)} 文件")


# ============================================================
# 3. 打 完整源代码.zip
# ============================================================
print(f"\n[2/6] 打 {OUT_FULL.name} ...")
if OUT_FULL.exists():
    OUT_FULL.unlink()
with zipfile.ZipFile(OUT_FULL, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    n_written = 0
    n_missing = 0
    for rel in src_files:
        abs_path = ROOT / rel
        if not abs_path.exists():
            n_missing += 1
            continue
        with open(abs_path, "rb") as f:
            data = f.read()
        arcname = f"完整源代码/{rel}".replace("\\", "/")
        zf.writestr(arcname, data)
        n_written += 1
print(f"  ✓ {OUT_FULL.stat().st_size/1024:.1f} KB ({n_written} 文件)")


# ============================================================
# 4. 打 智能考勤与实验室准入系统_设计方案.zip
# ============================================================
print(f"\n[3/6] 打 {OUT_COURSE.name} ...")
if OUT_COURSE.exists():
    OUT_COURSE.unlink()

USAGE_DIR = "使用说明"
EXE_DIR = "可执行文件"
PPT_DIR = "汇报PPT或演示视频"
CODE_DIR = "源代码"

# 使用说明: docs/ + 根目录上手相关
USAGE_ROOTS = {
    "README.md", "CLAUDE.md", "快速验证.md",
    "start.bat", "kill_all_python.bat", "LICENSE",
    ".env.example", "requirements.txt", "build.spec",
}
usage_files = []
for rel in src_files:
    if rel.startswith("docs/"):
        usage_files.append(rel)
    elif rel in USAGE_ROOTS:
        usage_files.append(rel)
usage_files = sorted(set(usage_files))
print(f"  使用说明/ : {len(usage_files)} 文件")

# 可执行文件: dist/attendance-system/ 全部 (新打的, 含 W15+ 修复)
exe_files = []
exe_src = ROOT / "dist" / "attendance-system"
if exe_src.exists():
    for p in exe_src.rglob("*"):
        if p.is_file():
            rel = p.relative_to(exe_src).as_posix()
            exe_files.append(rel)
print(f"  可执行文件/ : {len(exe_files)} 文件")

# 汇报PPT或演示视频: 03 + 04 submission
ppt_files = sorted(f for f in src_files if f in (
    "submission/03_REPORT_PPT_OUTLINE.md",
    "submission/04_DEMO_VIDEO_SCRIPT.md",
))
print(f"  汇报PPT或演示视频/ : {len(ppt_files)} 文件")

# 源代码: 全部 worktree 文件 (跟 完整源代码.zip 一致)
code_files = src_files
print(f"  源代码/ : {len(code_files)} 文件")

with zipfile.ZipFile(OUT_COURSE, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for rel in usage_files:
        abs_path = ROOT / rel
        if not abs_path.exists():
            continue
        with open(abs_path, "rb") as f:
            data = f.read()
        zf.writestr(f"{USAGE_DIR}/{rel}".replace("\\", "/"), data)

    for rel in exe_files:
        abs_path = exe_src / rel
        with open(abs_path, "rb") as f:
            data = f.read()
        zf.writestr(f"{EXE_DIR}/{rel}".replace("\\", "/"), data)

    for rel in ppt_files:
        abs_path = ROOT / rel
        if not abs_path.exists():
            continue
        with open(abs_path, "rb") as f:
            data = f.read()
        zf.writestr(f"{PPT_DIR}/{rel}".replace("\\", "/"), data)

    for rel in code_files:
        abs_path = ROOT / rel
        if not abs_path.exists():
            continue
        with open(abs_path, "rb") as f:
            data = f.read()
        zf.writestr(f"{CODE_DIR}/{rel}".replace("\\", "/"), data)

print(f"  ✓ {OUT_COURSE.stat().st_size/1024/1024:.1f} MB ({len(usage_files)+len(exe_files)+len(ppt_files)+len(code_files)} 文件)")


# ============================================================
# 5. 验证
# ============================================================
print("\n[4/6] 验证 2 个 zip ...")
for zp_path, label in [(OUT_FULL, "完整源代码"), (OUT_COURSE, "智能考勤与实验室准入系统_设计方案")]:
    with zipfile.ZipFile(zp_path) as z:
        names = z.namelist()
        bad = z.testzip()
        crc_ok = bad is None
        from collections import Counter
        c = Counter(names)
        dups = {k: v for k, v in c.items() if v > 1}
        cd_paths = [n for n in names if n.endswith("src/dao/course_dao.py")]
        has_fix = False
        if cd_paths:
            content = z.read(cd_paths[0]).decode("utf-8")
            has_fix = "outerjoin" in content and "CourseTeacher" in content
        has_test = any("test_course_dao.py" in n for n in names)
        must_have = ["src/main.py", "db/schema.sql", "db/migration_w14.sql", "requirements.txt",
                     "README.md", "快速验证.md", "submission/课程提交物清单.md",
                     "submission/01_DESIGN_PROPOSAL.md", "submission/05_GROUP_MEMBERS.md"]
        missing = [m for m in must_have if not any(m in n for n in names)]
        top = sorted(set(n.split("/")[0] for n in names if "/" in n))
        print(f"\n  {label} ({zp_path.stat().st_size/1024/1024:.1f} MB, {len(names)} 文件):")
        print(f"    CRC 校验: {'✓' if crc_ok else '✗ ' + str(bad)}")
        print(f"    重复条目: {'✓ 无' if not dups else '✗ ' + str(dups)}")
        print(f"    W15+ course_dao.py 修复: {'✓' if has_fix else '✗'}")
        print(f"    test_course_dao.py: {'✓' if has_test else '✗'}")
        print(f"    关键文件: {'✓ 齐' if not missing else '✗ 缺 ' + str(missing)}")
        print(f"    顶层目录: {top[:5]}")

# 6. 设计方案 zip 含 src/dao/course_dao.py 修复版 (从源代码/ 路径下查)
print("\n[5/6] 验证 设计方案.zip 内嵌的源代码 (含 W15+ 修复) ...")
with zipfile.ZipFile(OUT_COURSE) as z:
    cd_in_course = [n for n in z.namelist() if n.endswith("src/dao/course_dao.py")]
    if cd_in_course:
        c = z.read(cd_in_course[0]).decode("utf-8")
        print(f"  {cd_in_course[0]}: 含 W15+ 修复: {'✓' if 'outerjoin' in c and 'CourseTeacher' in c else '✗'}")

print("\n[6/6] DONE")
print(f"  {OUT_FULL}  ({OUT_FULL.stat().st_size/1024:.1f} KB)")
print(f"  {OUT_COURSE}  ({OUT_COURSE.stat().st_size/1024/1024:.1f} MB)")
