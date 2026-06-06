# W5 实施计划：PyInstaller 打包

**编写时间**: 2026-06-06 19:08
**截止**: 6-20（跟项目大截止）
**估时**: 1-1.5 天（PyInstaller 调试坑多）
**风格**: 跟 W3/W4 同款 writing-plans，每个 phase 独立可验收

## 目标

把现有 PyQt5 + dlib + matplotlib 桌面应用打成**单目录** (onedir) 可执行，
让同学老师**双击 .exe 启动 GUI**，不依赖 Python 3.11 / pip 装包。

## 范围选择

| 方案 | 体积 | 启动速度 | 选不选 |
|---|---|---|---|
| **A. onedir**（推荐） | ~300 MB（PyQt5 + dlib + matplotlib）| 快（~2s） | ✅ |
| B. onefile | 同上（首次解压慢 5-10s）| 慢 | ❌ |
| C. docker | - | - | 不在范围 |

**onedir** 理由：老师/同学直接拷一整个目录，README 引导双击 exe，
比 onefile 体验好（启动快、调试容易）。

## 现状摸底（06-06 19:08）

- ✅ 入口 `src/main.py`（`python -m src.main`）
- ✅ PyQt5 5.15.11 / dlib-bin 20.0.1 / matplotlib 3.10.9 / SQLAlchemy 2.0.43
- ✅ `models/` 已下好 dlib 2 个模型（22.5 + 99.7 MB = 122 MB）
- ❌ PyInstaller **未装**
- ❌ 无 spec 文件
- ⚠️ `face_helper.ensure_models()` 运行时从 GitHub 下载 → **断网挂**
- ⚠️ `.env` 含 DB_PASSWORD → **不能打包**
- ⚠️ `dataset/` 用户运行时拍照生成 → **不能打包**
- ⚠️ 路径用相对路径 → 打包后 `sys._MEIPASS` 处理

## 打包策略

### 资源处理

| 资源 | 策略 | 理由 |
|---|---|---|
| **dlib 模型 .dat** | **不打包** | 122 MB 让 exe 太大；保持 `face_helper.ensure_models()` 运行时下载；首次启动需联网 |
| **.env** | **不打包** | 含密码 + 用户自配 DB |
| **dataset/** | **不打包** | 用户运行时生成 |
| **QSS 样式** | **打包进去** | `src/ui/styles.py` 编译进 .pyc，跟着 exe |
| **图标 / splash** | 可选 | 时间紧不搞 |

### 路径处理

`face_helper` 当前用相对路径 `models/` → 打包后要兼容 `sys._MEIPASS`：

```python
import sys
from pathlib import Path
if getattr(sys, "frozen", False):
    # PyInstaller 打包后：exe 所在目录
    _APP_ROOT = Path(sys.executable).parent
else:
    _APP_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = _APP_ROOT / "models"
DATASET_DIR = _APP_ROOT / "dataset"
```

在 `src/utils/face_helper.py` 顶部加这个 helper，所有 `models/` / `dataset/` 引用改走它。

### 隐藏 import

PyInstaller 不会自动发现：
- `src.services.face_service._FaceCache`（不在 `__all__`）
- `pymysql`（SQLAlchemy dialect 反射）
- `matplotlib.backends.backend_qt5agg`（PyQt5 embed）
- `bcrypt` 的 C 扩展

走 `hiddenimports=[...]` 显式列。

### Spec 文件 vs 命令行

走 **spec 文件**（`build.spec`），方便迭代 + 进 git。

## Phase 1: 装 PyInstaller + 打第一个 onedir —— 0.5 天

- [ ] `pip install pyinstaller==6.*`
- [ ] 写 `build.spec`：
  - `name='attendance-system'`
  - `onedir=True` / `onefile=False`
  - `console=False`（GUI 应用，无控制台）
  - `icon=None`（先不上图标）
  - `datas=[]`（先把代码包进去，资源下一 phase 处理）
  - `hiddenimports=['pymysql', 'bcrypt', 'matplotlib.backends.backend_qt5agg',
    'src.services.face_service', 'src.services.face_service._FaceCache']`
- [ ] `pyinstaller build.spec`
- [ ] **验收**: `dist/attendance-system/attendance-system.exe` 双击 → 启
  LoginWindow（不连 DB 弹错误框可接受，**只要 GUI 起得来**）
- [ ] **风险预期**: PyQt5 platform plugin 找不到 → 加 `--collect-all PyQt5`

## Phase 2: 路径兼容 + 资源处理 —— 0.5 天

- [ ] `src/utils/face_helper.py` 顶部加 `_APP_ROOT` 路径 helper
- [ ] `face_helper.ensure_models()` 改用 `MODELS_DIR = _APP_ROOT / "models"`
- [ ] `src/services/face_service.py` 采集图片保存路径同步改
- [ ] `models/` 拷到 `dist/attendance-system/models/`（不打包进 exe）
- [ ] **验收**: 拷 `dist/attendance-system/` 到无 Python 环境机器双击
  `attendance-system.exe` → LoginWindow 起 → 注册账号能存人脸到 `dataset/`

## Phase 3: 离线/纯净环境测试 —— 0.3 天

- [ ] 准备一个无 Python 环境（VM 或另一台机器）
- [ ] 拷 `dist/attendance-system/` 整目录过去
- [ ] 创建 `.env` 模板（用环境变量 DB_HOST 等）
- [ ] 双击 exe → LoginWindow 起 → 登录 → 学生端刷脸签到 → 教师端发考勤
- [ ] **验收**: 完整 4 Tab admin GUI / 4 Tab teacher GUI / 3 Tab student GUI 都能用

## Phase 4: 文档 + commit —— 0.2 天

- [ ] 新建 `docs/PACKAGING.md`：写
  - 怎么打（`pyinstaller build.spec`）
  - 分发清单（`dist/attendance-system/` 整个目录 + 单独的 `.env` 模板）
  - 用户上手 3 步（拷目录 → 改 .env → 双击 exe）
  - 已知问题（首次启动需联网下 dlib 模型）
- [ ] 新建 `.env.template`：把 .env 里除 DB_PASSWORD 外的字段都列出来
- [ ] commit + push

---

## 风险 + 备选

| 风险 | 触发 | 应对 |
|---|---|---|
| PyQt5 platform plugin 缺失 | 双击 exe 弹 "could not find Qt platform plugin windows" | spec 加 `--collect-all PyQt5` 或显式 `datas=[(pyqt5_plugins, 'PyQt5/plugins')]` |
| matplotlib 中文乱码 | 打包后 rcParams 找不到字体 | spec 不用 collect matplotlib data，运行时 fallback Microsoft YaHei |
| onedir 太大（300+ MB）| 老师嫌大 | 接受。onedir 调试比 onefile 容易 10 倍，**坚持 onedir** |
| dlib 模型运行时下载失败 | 客户机断网 | 报错时给"手动下 .dat 放 models/"指引；不算 blocker |
| .env 没配置 | 客户机首次启动 | README 第 2 步强提示；.env 缺失时 QMessageBox 友好提示 |
| bcrypt / dlib 编译问题 | PyInstaller 找不到 .pyd | hiddenimports 显式列 |
| MySQL 客户机没装 | 数据库连不上 | README 强提示"需先装 MySQL 8.0+ 并 init_db.py 跑一次" |
| **SQLAlchemy 2.0 + PyMySQL 反射** | 找不到 dialect | hiddenimports `pymysql` |

## 关键文件

| 路径 | 状态 |
|---|---|
| `build.spec` | 新建 |
| `src/utils/face_helper.py` | 顶部加 _APP_ROOT 路径 helper |
| `src/services/face_service.py` | 采集图片保存路径同步 |
| `docs/PACKAGING.md` | 新建 |
| `.env.template` | 新建 |

## 推进节奏

- Phase 1 做完 → 双击 exe 起 GUI → commit → 报告
- Phase 2 做完 → 资源路径在打包后工作 → commit → 报告
- Phase 3 做完 → 端到端测过 → commit → 报告
- Phase 4 文档 + 推 origin

不批量 commit。W5 结束统一 push 1 次（除非用户中途要求推）。
