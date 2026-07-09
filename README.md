# 智能考勤与实验室准入系统

> **深圳技术大学健康与环境工程学院「数据库原理」课程设计（2025-2026-2）**
> 桌面应用：PyQt5 + dlib (人脸识别) + MySQL 8.0 + SQLAlchemy 2.0
> 截止 2026-06-20

## 项目交付物 (2 个 zip)

| 交付物 | 大小 | 用途 | 命名 |
|---|---|---|---|
| **`完整源代码.zip`** | ~350 KB / 130 文件 | 老师/接手人/组员用, 5 分钟跑起来, 含 5 份 submission + 快速验证 + .env.example | 原名 |
| **`智能考勤与实验室准入系统_设计方案.zip`** | ~341 MB / 1472 文件 | 课程提交用, 含 dist/ 380 MB 可执行文件, 5 份 submission + 源代码 + 使用说明 | **改名为 `<组长学号>_智能考勤与实验室准入系统_设计方案.zip`** |

**先看哪个?**
- **跑起来**: 解压 `完整源代码.zip` → 改 `.env.example` 为 `.env` 填 DB 密码 → `python scripts/init_db.py` → 双击 `start.bat`
- **课程提交**: 把第二个 zip 改名为 `<组长学号>_智能考勤与实验室准入系统_设计方案.zip` 即可

## 项目一句话

学生刷脸考勤 + 教师 3 种签到方式（刷脸 / 数字码 / **二维码多端登录**）+ 实验室门禁准入 + 管理员 / 教师可视化报表，一站式 PyQt5 桌面应用。

## 核心亮点

- **3 种签到方式（W13+ 重大功能）**：刷脸（dlib 距离匹配）/ 数字码（对分易式手动触发 5 分钟倒计时）/ 二维码（base64 token + cv2.QRCodeDetector）— 共用 `_create_record` 公共核，统一 UNIQUE 拦截 + 迟到判定 + `signin_method` 字段入库
- **W14+ 多端登录签到（手机扫码 → H5 → 教师端实时反馈）**：教师电脑起 :5180 FastAPI + H5 签到页；学生手机扫码 → 浏览器打开 H5 → 输账密 → 提交 → 教师端实时签到列表自动刷新
- **W15+ H5 polling 防缓存**：H5 进入后每 3 秒拉 `/api/signin/latest` 拿最新 LIVE token，提交用最新 token（不是 URL 里的老 token），即使教师中途刷码老 H5 URL 也不会失效
- **W15+ UI 现代化**：5 主窗体 + 12 widget margin/spacing 加大 + design tokens（`RADIUS_*` / `SHADOW_*` / `FONT_SIZE_*` / `SPACING_*`），演示场景老人看着不累
- **6 次审计修复**（W7-W15+ 共 36+ 真 bug）：死 import / 死方法 / 排序 tie-break / 测试污染 / bool Lock race / 资源泄漏 / 双摄像头冲突 / int-env 转换 / signin_web 闭包 token 校验 / H5 缓存
- **PyInstaller onedir 380 MB 真一键 exe**：双击即跑，开发与交付同链路
- **测试覆盖 219/219**：含 1 dtype 回归 + 1 collect_for_user 死循环回归 + 10 smoke 端到端（业务流 / 真脸 / QTest / 打包 / W13+ 签到 / W7-W12 历史修复回归 / W14+ 多端登录 9 步 / W14+ 打包后多端登录 / full_regression 6 service + 13 dao 全公开方法）+ 3 W15+ latest API 测试

## 快速上手

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配 .env (含 DB 密码)
cp .env.example .env
# 编辑 .env 填 DB_PASSWORD

# 3. 初始化数据库（首次）
python scripts/init_db.py

# 4. 启动 GUI —— 推荐双击 start.bat (W15+ 修 cmd 5.1 编码坑)
start.bat

# 4b. 等价命令行
python -m src.main

# 4c. 多个 GUI 进程抢资源时 (W15+ 新增)
kill_all_python.bat   # 清干净再双击 start.bat
```

**演示账号**：
- 学生：`test001 / 123456`（如被 W4 防爆破锁定,演示前清 `login_attempt` 表）或 `demo_student / 123456`（W14+ 多端登录演示用，student_id=`202400502133`）
- 教师：`teacher01 / 123456`（基础）或 `teacher001 / 123456`（W13+ / W14+ 演示用，已挂 BME201 + 两个 open task）

详见 [`快速验证.md`](快速验证.md) 或 [`docs/TEAM_SETUP.md`](docs/TEAM_SETUP.md)。

## 3 角色 / 4-5 Tab / 5 业务线

| 角色 | Tab | 业务线 |
|---|---|---|
| **学生** (student) | ① 人脸注册 / ② 签到（刷脸+数字码+二维码子 Tab）/ ③ 我的考勤 / ④ 我的请假 | 注册登录 / 考勤 / 请假 |
| **教师** (teacher) | ① 发起考勤（**W14+ 多端登录二维码签到** + 3 种签到方式触发按钮 + 弹窗） / ② 历史考勤（含请假审批） / ③ 统计报表 / ④ 账号 | + 报表 |
| **管理员** (lab_admin) | ① 实验室管理 / ② 安全培训 / ③ 准入日志 / ④ 使用率报表 / ⑤ 人脸管理 (W12 新增) | + 实验室准入 / 报表 |

## 关键技术决策

- **dlib-bin 20.0.1** (cp311/cp312/cp313 预编译 wheel) —— 避开 Windows 上 cmake 编译坑
- **face encoding dtype = float32** —— W3 决定，避免序列化/比对时量纲不一致（`test_face_encodings_dtype_is_float32` 锁住）
- **PyInstaller onedir** —— 380 MB，**真一键双击 exe**
- **4 层架构严格自顶向下** —— ui → service → dao → models（dao 构造函数注入 session 便于测试）
- **3 种签到方式统一 `_create_record` 公共核** (W13+) —— 刷脸 / 数字码 / 二维码走同一 UNIQUE 拦截 + 迟到判定 + signin_method 字段
- **W14+ FastAPI 嵌入 PyQt 进程**（不独立跑 uvicorn）—— `uvicorn.Server` 在 `threading.Thread(daemon=True)` 里跑，`closeEvent` 同步停
- **W15+ H5 入口路由不校验 token**（只校验 task_id）—— 真实校验交给 `dao.find_active_by_value(*, is_active=1, expires_at>now)` 实时查 DB；**教训：in-memory state 不能当真理**
- **W15+ H5 polling 防缓存** —— `/api/signin/latest` 返最新 LIVE token，H5 每 3s 拉一次，提交用最新
- **SQLAlchemy 2.0 ORM** —— 防 SQL 注入 + 跨数据库可移植（演示可一键切 SQLite）
- **bcrypt 哈希** —— 课程要求"密码不能明文"

## 验收

```bash
# 单元测试 (219 项 / ~67s 3 warning)
.venv\Scripts\python.exe -m pytest tests/ -q

# 10 个 smoke 端到端脚本
.venv\Scripts\python.exe scripts\smoke_full_flow.py        # 完整业务流 (W6)
.venv\Scripts\python.exe scripts\smoke_real_face.py        # dlib 真脸 + 摄像头 (W6)
.venv\Scripts\python.exe scripts\smoke_ui_qtest.py         # QTest 真实 UI (W6)
.venv\Scripts\python.exe scripts\smoke_e2e.py              # 打包后端到端 (W5)
.venv\Scripts\python.exe scripts\smoke_signin_methods.py   # W13+ 数字码 + 二维码
.venv\Scripts\python.exe scripts\smoke_audit_history.py    # W7-W12 历史修复回归
.venv\Scripts\python.exe scripts\smoke_full_regression.py  # 6 service + 13 dao 全公开方法
.venv\Scripts\python.exe scripts\smoke_qrcode_build.py     # W14+ 防 hiddenimports 漏配 (二维码)
.venv\Scripts\python.exe scripts\smoke_signin_web.py       # W14+ 9 步全链路
.venv\Scripts\python.exe scripts\smoke_signin_web_build.py # W14+ 打包后多端登录

# 重新打 .exe
pyinstaller build.spec
```

详细说明见 `requirements.txt` + `build.spec` + `scripts/smoke_*.py`（smoke 用法见下）。

## 文档导航

| 想看什么 | 文档 |
|---|---|
| **项目交接总入口**（HANDOFF） | [`docs/HANDOFF.md`](docs/HANDOFF.md) |
| 5 分钟跑通 | [`快速验证.md`](快速验证.md) |
| 数据库 14 张表设计 (12 schema + 1 w13+ migration + 1 w14+ course_teacher) | [`docs/DATABASE.md`](docs/DATABASE.md) |
| **3 种签到方式 (W13+, 刷脸/数字码/二维码)** | [`docs/SIGNIN_METHODS.md`](docs/SIGNIN_METHODS.md) |
| 老师 / 验收人 10 步清单 | [`docs/CHECKLIST_FOR_REVIEWER.md`](docs/CHECKLIST_FOR_REVIEWER.md) |
| 10 步亲自测试 + 故障速查 | [`docs/TESTING_CHECKLIST.md`](docs/TESTING_CHECKLIST.md) |
| 答辩 PPT 大纲 | [`docs/W14-defense-outline.md`](docs/W14-defense-outline.md) |
| 课程提交 5 份文档（设计方案/参考声明/PPT/演示脚本/组员分工） | [`submission/`](submission/) |
| 计划文档 (W3-W14) | [`docs/superpowers/plans/`](docs/superpowers/plans/) |
| AI 协作者上下文 | [`CLAUDE.md`](CLAUDE.md) |

## 仓库结构

```
.
├── README.md                  ← 你正在看
├── 快速验证.md              ← 5 分钟跑通
├── CLAUDE.md                  ← AI 协作者上下文 (架构/陷阱/当前进度)
├── requirements.txt           ← 主依赖
├── build.spec                 ← PyInstaller 配置 (W5)
├── .env.example               ← 环境变量模板 (W15+ 改名, 旧名 .env.template 已删)
├── .gitignore
│
├── db/
│   ├── schema.sql             ← MySQL 12 张表 DDL
│   ├── migration_w13.sql      ← W13+ 增量 (task_signin_code 新表 + signin_method 字段)
│   └── migration_w14.sql      ← W14+ 增量 (course_teacher 多对多表, Q3=B schema 变更)
│
├── docs/                      ← 设计文档 (7 个 + 录屏脚本 superpowers/plans/)
│   ├── HANDOFF.md             ← 项目交接总入口
│   ├── TEAM_SETUP.md          ← 组员跨机上手 9 步
│   ├── TESTING_CHECKLIST.md   ← 10 步亲自测试 + 故障速查
│   ├── CHECKLIST_FOR_REVIEWER.md ← 老师/验收人 5-10 分钟清单
│   ├── DATABASE.md            ← 14 张表设计
│   ├── SIGNIN_METHODS.md      ← W13+ 3 种签到方式
│   ├── W14-defense-outline.md ← 答辩 PPT 大纲
│   └── superpowers/plans/     ← W3-W14 实施计划 (6 个)
│
├── submission/                ← 课程提交 5 份文档 + 1 清单
│   ├── 01_DESIGN_PROPOSAL.md
│   ├── 02_ATTRIBUTION.md
│   ├── 03_REPORT_PPT_OUTLINE.md
│   ├── 04_DEMO_VIDEO_SCRIPT.md
│   ├── 05_GROUP_MEMBERS.md
│   └── 课程提交物清单.md
│
├── src/                       ← 项目代码 (4 层架构)
│   ├── main.py                ← 入口
│   ├── config.py / db.py
│   ├── models/                ← ORM 文件 (10 个, W14+ 加 course_teacher.py)
│   ├── dao/                   ← 数据访问类 (15 个, 含 task_signin_code + course_teacher)
│   ├── services/              ← 业务服务 (auth/face/attendance/lab/leave/report/signin_web 7 个)
│   ├── ui/                    ← PyQt5 表现层 (5 主窗口 + 13 widget, W15+ UI 现代化)
│   └── utils/                 ← 工具 (face_helper/crypto/charts/network/paths/report_dto)
│
├── tests/                     ← 219 项单元测试 (27 个文件, 含 W15+ 3 项 latest API)
│
├── scripts/                   ← 运维 + 10 个端到端 smoke + W14+ 工具
│   ├── init_db.py / seed_demo_data.py / cleanup_test_users.py
│   ├── build_2_zips.py / prepare_deliverable_zip.py ← W15+ 课程交付物打包
│   ├── run_dev.sh / run_dev.bat              ← 全 ASCII + chcp 65001
│   ├── smoke_full_flow.py        ← W6 业务流
│   ├── smoke_real_face.py        ← W6 真脸
│   ├── smoke_ui_qtest.py         ← W6 QTest
│   ├── smoke_e2e.py              ← W5 打包后端到端
│   ├── smoke_signin_methods.py   ← W13+ 数字码 + 二维码
│   ├── smoke_audit_history.py    ← W7-W12 16 项历史修复回归
│   ├── smoke_qrcode_build.py     ← W14+ 防 hiddenimports 漏配 (二维码)
│   ├── smoke_signin_web.py       ← W14+ 9 步全链路
│   ├── smoke_signin_web_build.py ← W14+ 打包后多端登录
│   ├── import_schedule.py        ← W14+ 课表导入 (Q1=B Q2=A Q3=B Q4=C)
│   └── cleanup_test_classrooms.py ← W14+ 删"测试教室*"残留
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
| **W15+** | **UI 现代化 + signin 修复 + 收口** | **5 主窗体 + 12 widget margin/spacing 加大 + design tokens + signin_web 入口路由 token 校验 bug 修复（删 `tok != token`）+ H5 polling 防缓存（`/api/signin/latest`）+ dialog 启动时 `update_token` 同步 + kill_all_python.bat 多 GUI 进程清理工具 + start.bat 全 ASCII (pytest 188/188)** |

## 提交记录

`git log --oneline` —— 共 **101 个 commit** (W2 → audit-round16 HEAD, 14 周迭代 + 6 次 bug 审计 (W7/W8/W9/W10/W11/W12) + W14 收尾 + W15+ 跨机可行性 4 P0 / 5 P1 修复 + W16 docs/arch/UI 联审)。

## 已知约束（项目层面接受,不动）

- `LabAccessService.check_access` / `LeaveService.list_pending_for_task` 是 service 公开 API 但 UI 没调 — W4/W6 设计如此,docstring 写明给"门口刷脸机"扩展
- `_FaceCache` 单例 dict 读写 race — N<1000 + GIL,W4 接受
- `FaceEncodingDao.set_primary` 2 次 update 中间可能短暂不一致 — W3 接受
- macOS / Linux 打包未测 — 课程用 Windows 验收,W5 已 lock
- 摄像头 + offscreen + QMessageBox 在 Windows 会段错误 — 直接带显示器跑

## 课程交付物（截止 2026-06-20,本周内完成）

- [ ] 课程报告 PDF（建议按 `submission/03_REPORT_PPT_OUTLINE.md` 的 10 个章节写）
- [ ] 答辩 PPT（15-20 页, 架构 + 核心功能 + 演示截图；W14+ 多端登录要单独一节，按 `docs/W14-defense-outline.md` 的 P1-P15 顺序排）
- [ ] 演示视频（5-10 分钟, 跟着 `submission/04_DEMO_VIDEO_SCRIPT.md` 录；**W14+ 多端登录签到 1 分钟专项**：教师屏二维码 → 学生手机扫码 → 浏览器 H5 → 输账密 → 教师端实时反馈）
- [ ] 提交物 .zip（项目源码 + 文档 + 视频 + 报告, 不含 .venv / build / dist / dataset；脚本 `python scripts/build_2_zips.py` 一键生成）
