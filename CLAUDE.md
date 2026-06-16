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

# W14: 多端登录签到烟测
python scripts/smoke_signin_web.py
python scripts/smoke_signin_web_build.py
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
├── services/ ← 业务逻辑（auth / attendance / face / lab_access / leave / report，6 个）
├── dao/ ← SQLAlchemy 数据访问（12 个：base/user/login_attempt/face/course/classroom/enrollment/attendance/leave/lab/training/access_log）
├── models/ ← ORM 模型（12 张表的 Python 类，对应 db/schema.sql）
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
| **`src/ui/styles.py` 是跨层依赖** | `src/utils/charts.py` 用 `from src.ui.styles import (COLOR_BG, COLOR_BUTTON, COLOR_DANGER, COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING, FONT_FAMILY)` 同步 matplotlib 主题色。重写 styles.py 时**只改 COLOR_* 值不删名**；入口函数签名 `apply_global_style / apply_auth_style / welcome_suffix` 也保持不变。W14 引入 design tokens (`RADIUS_*` / `SHADOW_*` / `FONT_SIZE_*` / `SPACING_*`) 时同样**只增常量不删旧的** |
| **FastAPI 嵌入到 PyQt 进程（不独立跑）** | W14 多端登录签到需要 HTTP 服务，但项目本身是桌面应用；独立跑 uvicorn 进程需要管端口/启停/与 GUI 生命周期对齐，体验割裂。改为 `uvicorn.Server` 在 `threading.Thread(daemon=True)` 里跑，`closeEvent` 调 `srv.should_exit = True` 同步停。SigninCodeDialog show → start，close → stop，单进程统一 |
| **W14 二维码签到内容 = URL（不是裸 token）** | 教师电脑起 :5180 FastAPI + H5 签到页，学生手机扫码后浏览器打开 `http://<lan_ip>:5180/signin/<task>/<token>`；二维码内容是完整 URL（带 host+port+path+token），手机浏览器直接渲染表单。`src/utils/network.get_lan_ip()` 自动探本机局域网 IP；端口冲突自动 +1 重试 1 次（`src/services/signin_web.py::SigninWebServer.start`） |

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
| `db/schema.sql` | MySQL DDL（12 张表，utf8mb4） |
| `db/migration_w13.sql` | W13+ 增量迁移：`task_signin_code` 新表 + `attendance_record.signin_method` 字段 |
| `docs/` | 设计文档（PROJECT_PLAN / ARCHITECTURE / STRUCTURE / DEVELOPMENT / DATABASE / WORKFLOWS / TEAM_AND_TIMELINE） |
| `docs/SIGNIN_METHODS.md` | W13+ 签到方式完整文档（刷脸/数字码/二维码对比 + 操作手册） |
| `docs/superpowers/plans/` | 实施计划（按 writing-plans skill 格式）。当前最新：`2026-06-07-W12-p0-fixes-and-deliverables.md`（W12 P0 验收修复 + W13+ 课程交付计划，截止2026-06-20） |
| `tests/` | 单元测试（**179/179** 全过，~55s 4 warning；含 1 项 dtype 回归 + 1 项 collect_for_user 死循环回归 + W12 新增 18 项 camera/admin_tab 覆盖 + W13+ 新增 18 项 signin_methods + W14 新增 11 项 signin_web + 10 项 UI 现代化 + 5 项 task_signin_code_dao） |
| `scripts/` | 运维 + 烟测脚本（init_db / run_dev / seed_demo_data / cleanup_test_users / smoke_full_flow / smoke_real_face / smoke_ui_qtest / smoke_e2e / **smoke_signin_methods** / **smoke_audit_history** / **smoke_qrcode_build** / **smoke_signin_web** / **smoke_signin_web_build**） |
| `dist/` `build/` | PyInstaller onedir打包产物（git ignore，不入库） |
| `models/` | dlib 模型权重（git ignore，运行时下载） |
| `dataset/` | 人脸采集图片（git ignore，运行时生成） |

## 角色与权限

3 种角色，登录后由 `src/ui/login_window.py::_open_role_window()` 路由：
- `student` → `StudentWindow`（**已完整**：人脸注册 / 签到（刷脸+数字码+二维码子 Tab）/ 我的考勤 / 我的请假，**4 Tab**）
- `teacher` → `TeacherWindow`（**已完整**：发起考勤 / 历史考勤 / 统计报表 / 账号，**4 Tab**；「发起考勤」Tab 含 3 种签到方式触发按钮 + 弹窗）
- `lab_admin` → `AdminWindow`（**已完整**：实验室 CRUD / 安全培训 / 准入日志 / 使用率报表 / 人脸管理，**5 Tab**）

测试账号：`.env` 配好后跑 `pytest tests/test_auth_service.py` 会自动创建大量测试账号；也可以手动建 `test001/123456`（学生）和 `teacher01/123456`（教师）；演示用 `teacher001/123456`（已挂 BME201 + 两个 open task）。

## 当前进度

**W14 已合：FastAPI 嵌入 + H5 签到页 + 多端登录（手机扫码 → 浏览器 → 教师端实时反馈）；课程交付物（报告 / PPT / 演示视频 / .zip）待收尾，截止2026-06-20。**

完整 12 周迭代 (W2 → W13+)：

- ✅ **W2**：登录注册、教师端 4 tab + 10 张表 + 3 角色
- ✅ **W3**：人脸识别全链路（face_service + _FaceCache + CameraWidget + 学生端 4 tab + smoke_face）
- ✅ **W4**：实验室准入 7 分支 + 安全培训 + 准入日志 + 4 类 matplotlib 图表
- ✅ **W5**：PyInstaller onedir 380 MB 真一键 exe + smoke_e2e
- ✅ **W6**：leave_request 完整流程（学生申请 / 教师审批）+ 4 个 smoke 脚本
- ✅ **W7**：完整 bug 审计（9 死 import + 2 死方法 + 1 排序 tie-break + 1 测试污染）
- ✅ **W8**：closeEvent 资源泄漏修复 + 注册字段长度校验
- ✅ **W9**：CameraWidget bool→Lock + face_collect 不 accept + 双摄像头冲突
- ✅ **W10**：matplotlib 内存 + dlib 下载超时
- ✅ **W11**：int/float/env 转换 + 20 领域系统扫
- ✅ **W12**：P0 验收修复 12 真 bug + 2 业务功能（管理员人脸管理 + 学生清自己人脸）
- ✅ **W13+**：教师/学生端数字码 + 二维码签到（对分易式手动触发码）+ 13 张表 + 5 个 smoke
- ✅ **W14**：FastAPI 嵌入 + H5 签到页 + 多端登录（手机扫码 → 浏览器 → 教师端实时反馈）
- ✅ 测试：**179/179** 全过（含 1 项 dtype 回归 + 1 项 collect_for_user 死循环回归 + W12 新增 18 项 + W13+ 新增 18 项 + W14 新增 11 项 signin_web + 10 项 UI 现代化 + 5 项 task_signin_code_dao）
- ✅ Smoke：5 个脚本（full_flow / real_face / ui_qtest / e2e / signin_methods）+ audit_history 16/16 OK + smoke_qrcode_build + smoke_signin_web (9 步全链路) + smoke_signin_web_build
- ✅ GitHub：**53 commit** 已推 main
- 📋 下一步：课程交付物（报告 PDF / 答辩 PPT / 演示视频 / 提交物 .zip），详 `docs/superpowers/plans/2026-06-07-W12-p0-fixes-and-deliverables.md` + `docs/W14-defense-outline.md`

## W3 Phase 5 学生端接入时必踩的坑

`face_service.collect_for_user` 设计上**在 Qt 工作线程里跑**（dlib 编码每次 ~50-100ms，不能阻塞主线程）。`on_progress` 回调里如果直接 `label.setText(...)` / `progress_bar.setValue(...)` → **PyQt 段错误**。

正确做法（已写进 `face_service.collect_for_user` docstring）：
- 在 Widget 里 `progress_updated = pyqtSignal(int, int)`
- 启动采集时 `worker.progress_updated.connect(self._on_progress, Qt.QueuedConnection)`
- worker 里 `self.progress_updated.emit(captured, total)` 代替直接调回调

参考：Qt 跨线程信号固定 `Qt.QueuedConnection` 即可。

详细分工见 `docs/TEAM_AND_TIMELINE.md`。
