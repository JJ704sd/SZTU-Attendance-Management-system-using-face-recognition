# 智能考勤与实验室准入系统

> 深圳技术大学健康与环境工程学院「数据库原理」课程设计（2025-2026-2）
> 桌面应用：PyQt5 + dlib (人脸识别) + MySQL 8.0 + SQLAlchemy 2.0
> 截止 2026-06-20

## 项目一句话

学生刷脸考勤 + 实验室门禁准入 + 管理员 / 教师可视化报表，一站式 PyQt5 桌面应用。

## 快速上手

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 配 .env (含 DB 密码)
cp .env.template .env
# 编辑 .env 填 DB_PASSWORD

# 3. 启动
python -m src.main
```

详见 [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)。

## 文档导航

| 想看什么 | 文档 |
|---|---|
| 项目架构 / 4 层依赖 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 数据库 12 张表设计 | [`docs/DATABASE.md`](docs/DATABASE.md) |
| 业务流程 (考勤/准入/请假) | [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) |
| 开发者上手 30 分钟 | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| 端到端验证 (W3 学生跑通) | [`docs/MANUAL_E2E.md`](docs/MANUAL_E2E.md) |
| **PyInstaller 打包 (W5)** | [`docs/PACKAGING.md`](docs/PACKAGING.md) |
| **Smoke 测试指南 (W6)** | [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md) |
| 计划文档 (W3-W6) | [`docs/superpowers/plans/`](docs/superpowers/plans/) |

## 3 角色 / 4 Tab / 5 业务线

| 角色 | Tab | 业务线 |
|---|---|---|
| **学生** (student) | ① 人脸注册 / ② 刷脸签到 / ③ 我的考勤 / ④ 我的请假 | 注册登录 / 考勤 / 请假 |
| **教师** (teacher) | ① 发起考勤 / ② 历史考勤 (含请假审批) / ③ 统计报表 / ④ 账号 | + 报表 |
| **管理员** (lab_admin) | ① 实验室管理 / ② 安全培训 / ③ 准入日志 / ④ 使用率报表 | + 实验室准入 / 报表 |

## 关键技术决策

- **dlib-bin 20.0.1** (cp311/cp312/cp313 预编译 wheel) —— 避开 Windows 上 cmake 编译坑
- **face encoding dtype = float32** —— W3 决定，避免序列化/比对时量纲不一致
- **PyInstaller onedir** —— 380 MB，**真一键双击 exe**
- **4 层架构严格自顶向下** —— ui → service → dao → models

## 验收

```bash
# 单元测试 (82 项)
.venv\Scripts\python.exe -m pytest tests/ -q

# 4 个 smoke 脚本
.venv\Scripts\python.exe scripts\smoke_full_flow.py    # 完整业务流
.venv\Scripts\python.exe scripts\smoke_real_face.py    # dlib 真脸 + 摄像头
.venv\Scripts\python.exe scripts\smoke_ui_qtest.py     # QTest 真实 UI
.venv\Scripts\python.exe scripts\smoke_e2e.py          # 打包后端到端

# 重新打 .exe
pyinstaller build.spec
```

详细说明见 [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md) + [`docs/PACKAGING.md`](docs/PACKAGING.md)。

## 仓库结构

```
.
├── README.md                  ← 你正在看
├── requirements.txt           ← 主依赖
├── build.spec                 ← PyInstaller 配置 (W5)
├── .env.template              ← 环境变量模板 (W5)
├── .gitignore
│
├── db/schema.sql              ← MySQL 12 张表 DDL
├── docs/                      ← 设计文档
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── WORKFLOWS.md
│   ├── DEVELOPMENT.md
│   ├── MANUAL_E2E.md          ← W3 端到端
│   ├── PACKAGING.md           ← W5 打包
│   ├── SMOKE_TESTS.md         ← W6 smoke 指南
│   └── superpowers/plans/     ← W3-W6 计划
│
├── src/                       ← 项目代码 (4 层)
│   ├── main.py                ← 入口
│   ├── config.py / db.py / constants.py
│   ├── models/                ← 12 张表 ORM
│   ├── dao/                   ← 数据访问
│   ├── services/              ← 业务逻辑
│   ├── ui/                    ← PyQt5 表现层
│   └── utils/                 ← 工具 (dlib/paths/charts/crypto)
│
├── tests/                     ← 单元测试 (82 项)
│
├── scripts/                   ← 运维 / 烟测
│   ├── init_db.py
│   ├── run_dev.sh / run_dev.bat
│   ├── smoke_full_flow.py     ← W6 业务流
│   ├── smoke_real_face.py     ← W6 真脸
│   ├── smoke_ui_qtest.py      ← W6 QTest
│   └── smoke_e2e.py           ← W5 打包后端到端
│
└── models/                    ← dlib 模型 (git 忽略, 运行时下载)
```

## 提交记录

`git log --oneline` —— W2 → W8 共 17 个 commit (5 个 W3 + 5 个 W4 + 5 个 W5 + 1 个 W6 plan + 5 个 W6 commits + 1 个 W7 + 1 个 W8)。
