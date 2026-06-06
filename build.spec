# -*- mode: python ; coding: utf-8 -*-
"""
build.spec — 智能考勤与实验室准入系统 打包配置

W5 Phase 1 验收目标:
- onedir 模式（不是 onefile）
- console=False（GUI 应用，无控制台）
- 隐藏 import 显式列（PyInstaller 默认扫描 + hiddenimports 兜底）
- --collect-all PyQt5（platforms/plugins 自动包含）

构建: pyinstaller build.spec
产物: dist/attendance-system/attendance-system.exe
"""
import sys
from pathlib import Path

block_cipher = None

# 1. hidden imports (PyInstaller 静态分析扫不到的)
hiddenimports = [
    # SQLAlchemy 2.0 dialect 反射
    'pymysql',
    'pymysql.cursors',
    'pymysql.connections',
    # C 扩展
    'bcrypt',
    '_bcrypt',
    # matplotlib PyQt5 backend
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_qt5',
    # 项目内 import 兜底（防止 _FaceCache 等私有类漏掉）
    'src.services.face_service',
    'src.services.face_service._FaceCache',
    'src.services.lab_access_service',
    'src.services.report_service',
    'src.services.auth_service',
    'src.services.attendance_service',
    'src.utils.face_helper',
    'src.utils.charts',
    'src.dao.face_dao',
    'src.dao.lab_dao',
    'src.dao.lab_training_dao',
    'src.dao.lab_access_log_dao',
    'src.dao.course_enrollment_dao',
    'src.dao.login_attempt_dao',
]

# 2. datas = 额外要带进 exe 的资源
# 暂时不打包：dlib 模型（运行时下载，.env（含密码），dataset/（用户运行时生成）
datas = []

# 3. excludes = 不打进 exe 的（瘦身）
excludes = [
    'tkinter',  # 用不到
    'test',     # pytest
    'pytest',
    'setuptools',
    'pip',
    'wheel',
    'unittest',
    'pydoc_data',
    'IPython',
]

a = Analysis(
    ['src/main.py'],
    pathex=[str(Path('.').resolve())],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# PyQt5 整个 plugins 目录强制收集
# (PyInstaller 内置 hook 已经会处理，但显式 collect 更稳)
try:
    a = a.copy()  # 不修改原对象
    from PyInstaller.utils.hooks import collect_all
    extras, _, _ = collect_all('PyQt5')
    a.datas += extras
    a.binaries += []
except Exception:
    pass

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir 模式：dll 和数据不进 EXE
    name='attendance-system',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # GUI 应用，无控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='attendance-system',
)
