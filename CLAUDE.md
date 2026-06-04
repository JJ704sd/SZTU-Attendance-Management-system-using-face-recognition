# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目一句话

深圳技术大学健康与环境工程学院「数据库原理」课程设计：**智能考勤与实验室准入系统**（PyQt5 桌面应用 + MySQL 8.0 + dlib 人脸识别）。截止 2026-06-20。

## 常用命令

```bash
# 装依赖（首次）
pip install -r requirements.txt

# 初始化数据库（需要 .env 配好 DB_PASSWORD）
python scripts/init_db.py

# 启动 GUI —— 必须在项目根目录跑，不能 cd src
python -m src.main

# 等价启动方式
bash scripts/run_dev.sh        # Linux/macOS
scripts\run_dev.bat            # Windows
```

### 测试

```bash
# 全量
pytest tests/ -v

# 单文件
pytest tests/test_auth_service.py -v
pytest tests/test_face_helper.py -v

# 单条用例
pytest tests/test_auth_service.py::test_register_and_login_success -v

# 详细报错
pytest tests/ --tb=long
```

测试需要 `.env` 中配置真实的 MySQL 连接；`test_auth_service.py` 用 UUID 随机用户名避免冲突。

## 架构（4 层 + 工具层）

严格**自顶向下依赖**，禁止反向：

```
src/
├── ui/        ← PyQt5 窗口（login / register / student / teacher / admin + widgets/）
├── services/  ← 业务逻辑（auth_service / attendance_service；face/lab_access/report 待 W3-W4）
├── dao/       ← SQLAlchemy 数据访问（base / user / course / classroom / attendance）
├── models/    ← ORM 模型（10 张表的 Python 类，对应 db/schema.sql）
├── db.py      ← SQLAlchemy engine + session_scope() 上下文
├── config.py  ← 读 .env，提供 Config 单例
└── utils/     ← crypto（bcrypt）、face_helper（dlib 封装）
```

- **service** 内部用 `with session_scope() as s:` 自动 commit/rollback/close
- **ui** 调 service，捕获异常后用 `QMessageBox` 弹给用户
- **utils** 不依赖任何项目业务代码，可被任意层调用
- **dao** 通过构造函数注入 session，便于测试 mock

## 关键技术决策（不要推翻）

| 决策 | 原因 |
|---|---|
| **dlib-bin==20.0.1** 而非源码编译 | Python 3.13 + Windows 上 cmake 编译坑多；`dlib-bin` 是预编译 wheel |
| **不依赖 face_recognition 库** | face_recognition 1.3.0 的 dlib 子依赖在 cp313 上无 wheel；`src/utils/face_helper.py` 自写 4 个核心 API（face_locations / face_encodings / face_distance / compare_faces） |
| **dlib 模型不入 git** | 单文件 95 MB 接近 GitHub 100 MB 警告线；首次运行时由 `face_helper.ensure_models()` 从 `https://github.com/davisking/dlib-models/raw/master/...bz2` 下载到 `models/` |
| **bcrypt 而非明文** | 课程要求"密码不能明文" |
| **SQLAlchemy 2.0 ORM** | 防 SQL 注入 + 跨数据库可移植（演示可一键切 SQLite） |
| **PyQt5 而非 Tkinter** | 控件丰富，4 个主窗口有大量表格 + 表单 |
| **face encoding 统一 float32** | `face_helper.face_encodings` 返回 `np.float32`，与 dlib 内部 + `FaceEncoding.encoding` 列注释一致；W3 序列化/比对链路不会再因量纲不一致出错。**不要改回 float64**，有 `test_face_encodings_dtype_is_float32` 锁住 |

## 环境陷阱（容易踩的）

- **必须在项目根目录跑** `python -m src.main`，不能 `cd src && python main.py`——`src` 自己找不到自己（`main.py` 头部有 `sys.path` 兜底但还是建议用 `-m`）
- **Windows + PyQt5 + offscreen + QMessageBox 会段错误**——别在 offscreen 模式下触发按钮，直接带显示器跑
- **dlib 模型 120 MB**——首次 `python -m src.main` 会自动下载，断网会失败
- **`.env` 含明文密码**，不入 git；修改后重启服务生效
- **GitHub 推送需要绕开代理**——全局 `.gitconfig` 配了 `http.proxy=http://127.0.0.1:17891`，会阻断 GitHub HTTPS。命令级加 `-c http.proxy= -c https.proxy=` 即可：
  ```bash
  git -c http.proxy= -c https.proxy= push -u origin main
  ```
- **课程要求 PDF** `2025-2026-2+数据库原理+课程设计要求.pdf` 仍在项目根目录的磁盘上（是学校发的参考资料），但**已从 git 撤库**（commit `f956163`），`.gitignore` 里 `*.pdf` 规则会拦住

## 仓库拓扑

| 目录 | 是什么 |
|---|---|
| `src/` | **本项目代码**（4 层架构） |
| `db/schema.sql` | MySQL DDL（10 张表，utf8mb4） |
| `docs/` | 设计文档（PROJECT_PLAN / ARCHITECTURE / STRUCTURE / DEVELOPMENT / DATABASE / WORKFLOWS / TEAM_AND_TIMELINE） |
| `docs/superpowers/plans/` | 实施计划（按 writing-plans skill 格式）。当前最新：`2026-06-04-W3-face-recognition.md`（W3 6 阶段计划，估时 4.5 天，截止 2026-06-07） |
| `tests/` | 单元测试（18/18 全过，0 warning；含 1 项 dtype 回归测试） |
| `scripts/` | 运维脚本（init_db / run_dev） |
| `reference/patelrahul4884/` | **原项目参考代码**，**不被 import**，仅作对比 |
| `models/` | dlib 模型权重（git ignore，运行时下载） |
| `dataset/` | 人脸采集图片（git ignore，运行时生成） |

## 角色与权限

3 种角色，登录后由 `src/ui/login_window.py::_open_role_window()` 路由：
- `student` → `StudentWindow`（占位，W3 接入刷脸签到）
- `teacher` → `TeacherWindow`（**已完整**：发起考勤 / 历史考勤 / 任务详情 / 改密）
- `lab_admin` → `AdminWindow`（占位，W4 接入实验室 CRUD + 安全培训）

测试账号：`.env` 配好后跑 `pytest tests/test_auth_service.py` 会自动创建大量测试账号；也可以手动建 `test001/123456`（学生）和 `teacher01/123456`（教师）。

## 当前进度

**W2 末，W3 计划就绪待执行。**

- ✅ 已跑通：登录注册、教师端 4 个 tab 完整流程、10 张表 + 3 角色
- ✅ 18/18 单测全过，0 warning（commit `241ab3d`）
- ✅ P0/P1 遗留 bug 全部修完（face_helper dtype / SQLAlchemy 2.0 / 死代码 / PDF 撤库）
- 📋 W3 详细计划：[`docs/superpowers/plans/2026-06-04-W3-face-recognition.md`](docs/superpowers/plans/2026-06-04-W3-face-recognition.md)，按 Phase 1→6 顺序执行
- ❌ 未做：face_service + CameraWidget（Phase 1-2）、学生端刷脸注册/签到/历史（Phase 3-5）、实验室管理端 + 报表（W4）、PyInstaller（W5）、报告 PPT（W6）

详细分工见 `docs/TEAM_AND_TIMELINE.md`。
