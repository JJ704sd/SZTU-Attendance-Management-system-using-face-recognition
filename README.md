# 智能考勤与实验室准入系统

> **深圳技术大学健康与环境工程学院「数据库原理」课程设计（2025-2026-2）**
> 桌面应用：PyQt5 + dlib (人脸识别) + MySQL 8.0 + SQLAlchemy 2.0
> 截止 2026-06-20

## 项目一句话

学生刷脸考勤 + 教师 3 种签到方式（刷脸 / 数字码 / 二维码）+ 实验室门禁准入 + 管理员 / 教师可视化报表，一站式 PyQt5 桌面应用。

## 核心亮点

- **3 种签到方式（W13+ 重大功能）**：刷脸（dlib 距离匹配）/ 数字码（对分易式手动触发 60s 倒计时）/ 二维码（base64 token + cv2.QRCodeDetector）— 共用 `_create_record` 公共核，统一 UNIQUE 拦截 + 迟到判定 + `signin_method` 字段入库
- **5 次审计修复**（W7-W12 共 36 真 bug）：死 import / 死方法 / 排序 tie-break / 测试污染 / bool Lock race / 资源泄漏 / 双摄像头冲突 / int-env 转换
- **PyInstaller onedir 380 MB 真一键 exe**：双击即跑，开发与交付同链路
- **测试覆盖 103/103**：含 1 dtype 回归 + 1 collect_for_user 死循环回归 + 6 smoke 端到端（业务流 / 真脸 / QTest / 打包 / W13+ 签到 / W7-W12 历史修复回归）

## 快速上手

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配 .env (含 DB 密码)
cp .env.template .env
# 编辑 .env 填 DB_PASSWORD

# 3. 初始化数据库（首次）
python scripts/init_db.py

# 4. 启动 GUI —— ⚠️ 必须在项目根目录跑
python -m src.main
```

**演示账号**：
- 学生：`test001 / 123456`（如被 W4 防爆破锁定,演示前清 `login_attempt` 表）
- 教师：`teacher01 / 123456`（基础）或 `teacher001 / 123456`（W13+ 演示用，已挂 BME201 + 两个 open task）

详见 [`QUICKSTART.md`](QUICKSTART.md) 或 [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)。

## 3 角色 / 4-5 Tab / 5 业务线

| 角色 | Tab | 业务线 |
|---|---|---|
| **学生** (student) | ① 人脸注册 / ② 签到（刷脸+数字码+二维码子 Tab）/ ③ 我的考勤 / ④ 我的请假 | 注册登录 / 考勤 / 请假 |
| **教师** (teacher) | ① 发起考勤（含 3 种签到方式触发按钮 + 弹窗） / ② 历史考勤（含请假审批） / ③ 统计报表 / ④ 账号 | + 报表 |
| **管理员** (lab_admin) | ① 实验室管理 / ② 安全培训 / ③ 准入日志 / ④ 使用率报表 / ⑤ 人脸管理 (W12 新增) | + 实验室准入 / 报表 |

## 关键技术决策

- **dlib-bin 20.0.1** (cp311/cp312/cp313 预编译 wheel) —— 避开 Windows 上 cmake 编译坑
- **face encoding dtype = float32** —— W3 决定，避免序列化/比对时量纲不一致（`test_face_encodings_dtype_is_float32` 锁住）
- **PyInstaller onedir** —— 380 MB，**真一键双击 exe**
- **4 层架构严格自顶向下** —— ui → service → dao → models（dao 构造函数注入 session 便于测试）
- **3 种签到方式统一 `_create_record` 公共核** (W13+) —— 刷脸 / 数字码 / 二维码走同一 UNIQUE 拦截 + 迟到判定 + signin_method 字段
- **SQLAlchemy 2.0 ORM** —— 防 SQL 注入 + 跨数据库可移植（演示可一键切 SQLite）
- **bcrypt 哈希** —— 课程要求"密码不能明文"

## 验收

```bash
# 单元测试 (103 项 / ~40s 0 warning)
.venv\Scripts\python.exe -m pytest tests/ -q

# 6 个 smoke 端到端脚本
.venv\Scripts\python.exe scripts\smoke_full_flow.py        # 完整业务流 (W6)
.venv\Scripts\python.exe scripts\smoke_real_face.py        # dlib 真脸 + 摄像头 (W6)
.venv\Scripts\python.exe scripts\smoke_ui_qtest.py         # QTest 真实 UI (W6)
.venv\Scripts\python.exe scripts\smoke_e2e.py              # 打包后端到端 (W5)
.venv\Scripts\python.exe scripts\smoke_signin_methods.py   # W13+ 数字码 + 二维码
.venv\Scripts\python.exe scripts\smoke_audit_history.py    # W7-W12 历史修复回归
.venv\Scripts\python.exe scripts\smoke_full_regression.py  # 6 service + 13 dao 全公开方法

# 重新打 .exe
pyinstaller build.spec
```

详细说明见 [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md) + [`docs/PACKAGING.md`](docs/PACKAGING.md)。

## 文档导航

| 想看什么 | 文档 |
|---|---|
| 5 分钟跑通 | [`QUICKSTART.md`](QUICKSTART.md) |
| 项目架构 / 4 层依赖 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 数据库 13 张表设计 (12 schema + 1 w13+ migration) | [`docs/DATABASE.md`](docs/DATABASE.md) |
| 业务流程 (考勤/准入/请假) | [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) |
| 开发者上手 30 分钟 | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| 端到端验证 (W3 学生跑通) | [`docs/MANUAL_E2E.md`](docs/MANUAL_E2E.md) |
| **PyInstaller 打包 (W5)** | [`docs/PACKAGING.md`](docs/PACKAGING.md) |
| **Smoke 测试指南 (W6)** | [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md) |
| **3 种签到方式 (W13+, 刷脸/数字码/二维码)** | [`docs/SIGNIN_METHODS.md`](docs/SIGNIN_METHODS.md) |
| **演示视频录制脚本 (W8)** | [`docs/DEMO_RECORDING.md`](docs/DEMO_RECORDING.md) + [`RECORD_STEP_BY_STEP.md`](docs/RECORD_STEP_BY_STEP.md) + 字幕 [`demo_narration.srt`](docs/demo_narration.srt) |
| 计划文档 (W3-W12+W13+) | [`docs/superpowers/plans/`](docs/superpowers/plans/) |
| AI 协作者上下文 | [`CLAUDE.md`](CLAUDE.md) |

## 仓库结构

```
.
├── README.md                  ← 你正在看
├── QUICKSTART.md              ← 5 分钟跑通
├── CLAUDE.md                  ← AI 协作者上下文 (架构/陷阱/当前进度)
├── requirements.txt           ← 主依赖 (W14 后已清空 dlib-bin 备选注释)
├── build.spec                 ← PyInstaller 配置 (W5)
├── .env.template              ← 环境变量模板 (W5)
├── .gitignore
│
├── db/
│   ├── schema.sql             ← MySQL 12 张表 DDL
│   └── migration_w13.sql      ← W13+ 增量 (task_signin_code 新表 + signin_method 字段)
│
├── docs/                      ← 设计文档 (10 个 + 录屏脚本)
│   ├── ARCHITECTURE.md / DATABASE.md / WORKFLOWS.md / DEVELOPMENT.md
│   ├── MANUAL_E2E.md          ← W3 端到端
│   ├── PACKAGING.md           ← W5 打包
│   ├── SMOKE_TESTS.md         ← W6 smoke 指南
│   ├── SIGNIN_METHODS.md      ← W13+ 3 种签到方式
│   ├── DEMO_RECORDING.md + RECORD_STEP_BY_STEP.md + demo_narration.md/srt
│   ├── TODO.md                ← W11 36 领域扫后续待办
│   └── superpowers/plans/     ← W3-W12+W13+ 计划 (5 个)
│
├── src/                       ← 项目代码 (4 层架构)
│   ├── main.py                ← 入口
│   ├── config.py / db.py / constants.py
│   ├── models/                ← 8 个 ORM 文件 (attendance.py 含 3 表)
│   ├── dao/                   ← 13 个数据访问类 (W14 清理掉 attendance_dao 里冗余的 LeaveRequestDao)
│   ├── services/              ← 6 个业务服务 (auth/face/attendance/lab/leave/report)
│   ├── ui/                    ← PyQt5 表现层 (5 主窗口 + 14 widget)
│   └── utils/                 ← 工具 (dlib/paths/charts/crypto)
│
├── tests/                     ← 103 项单元测试 (18 个文件)
│
├── scripts/                   ← 运维 + 7 个端到端 smoke
│   ├── init_db.py / seed_demo_data.py / cleanup_test_users.py
│   ├── run_dev.sh / run_dev.bat
│   ├── smoke_full_flow.py        ← W6 业务流
│   ├── smoke_real_face.py        ← W6 真脸
│   ├── smoke_ui_qtest.py         ← W6 QTest
│   ├── smoke_e2e.py              ← W5 打包后端到端
│   ├── smoke_signin_methods.py   ← W13+ 数字码 + 二维码
│   ├── smoke_audit_history.py    ← W7-W12 16 项历史修复回归 (W14 加)
│   └── smoke_full_regression.py  ← 6 service + 13 dao 全公开方法 (W14 加)
│
└── models/                    ← dlib 模型 (git 忽略, 运行时下载 ~120 MB)
```

## 迭代里程碑（W2 → W13+,共 14 周）

| 周 | 主题 | 关键产出 |
|---|---|---|
| W2 | 登录注册 + 教师端 4 Tab | 3 角色 + 10 张表 + bcrypt |
| W3 | 人脸识别全链路 | face_service + _FaceCache + CameraWidget + 学生端 4 Tab + float32 encoding |
| W4 | 实验室准入 7 分支 | 实验室 / 培训 / 准入日志 + 4 类 matplotlib 图表 |
| W5 | PyInstaller 打包 | onedir 380 MB 真一键 exe + smoke_e2e |
| W6 | leave_request 流程 | 学生申请 / 教师审批 / 4 个 smoke |
| W7 | 第 1 次审计 | 9 死 import + 2 死方法 + 1 排序 tie-break + 1 测试污染 (pytest 81/81) |
| W8 | 第 2 次审计 | closeEvent 资源泄漏 + 注册字段长度校验 (pytest 82/82) |
| W9 | 第 3 次审计 | bool→Lock + face_collect accept + 双摄像头冲突 (pytest 82/82) |
| W10 | 第 4 次审计 | matplotlib 内存 + dlib 下载超时 |
| W11 | 第 5 次审计 (20 领域扫) | 7 int/float/env 转换 bug |
| W12 | P0 验收 + 业务功能 | 12 真 bug + 2 功能 (管理员人脸管理 + 学生清自己人脸) (pytest 100/100) |
| W13+ | 数字码 + 二维码签到 | task_signin_code 新表 + signin_method 字段 + 3 签到方式统一公共核 (pytest 103/103) |
| W14 | 全功能回归 + 项目整理 | 修 1 FK 1452 race + 1 GBK 编码炸 + 1 W13+ 漏 stage + 删 2 冗余文件 + 1 死类 + 加 2 回归 smoke |

## 提交记录

`git log --oneline` —— 共 **56 个 commit** (W2 → W14, 13 周迭代 + 6 次审计 + 收口)。

## 已知约束（项目层面接受,不动）

- `LabAccessService.check_access` / `LeaveService.list_pending_for_task` 是 service 公开 API 但 UI 没调 — W4/W6 设计如此,docstring 写明给"门口刷脸机"扩展
- `_FaceCache` 单例 dict 读写 race — N<1000 + GIL,W4 接受
- `FaceEncodingDao.set_primary` 2 次 update 中间可能短暂不一致 — W3 接受
- macOS / Linux 打包未测 — 课程用 Windows 验收,W5 已 lock
- 摄像头 + offscreen + QMessageBox 在 Windows 会段错误 — 直接带显示器跑

## 课程交付物（截止 2026-06-20,本周内完成）

- [ ] 课程报告 PDF
- [ ] 答辩 PPT（15-20 页, 架构 + 核心功能 + 演示截图）
- [ ] 演示视频（5-10 分钟, 跟着 `docs/DEMO_RECORDING.md` + `RECORD_STEP_BY_STEP.md` + `demo_narration.srt` 录）
- [ ] 提交物 .zip（项目源码 + 文档 + 视频 + 报告, 不含 .venv / build / dist）
