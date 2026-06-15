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
| 数据库 13 张表设计 (12 schema + 1 w13+ migration) | [`docs/DATABASE.md`](docs/DATABASE.md) |
| 业务流程 (考勤/准入/请假) | [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) |
| 开发者上手 30 分钟 | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| 端到端验证 (W3 学生跑通) | [`docs/MANUAL_E2E.md`](docs/MANUAL_E2E.md) |
| **PyInstaller 打包 (W5)** | [`docs/PACKAGING.md`](docs/PACKAGING.md) |
| **Smoke 测试指南 (W6)** | [`docs/SMOKE_TESTS.md`](docs/SMOKE_TESTS.md) |
| **3 种签到方式 (W13+, 刷脸/数字码/二维码)** | [`docs/SIGNIN_METHODS.md`](docs/SIGNIN_METHODS.md) |
| 计划文档 (W3-W12+W13+) | [`docs/superpowers/plans/`](docs/superpowers/plans/) |

## 3 角色 / 4-5 Tab / 5 业务线

| 角色 | Tab | 业务线 |
|---|---|---|
| **学生** (student) | ① 人脸注册 / ② 签到（刷脸+数字码+二维码子 Tab）/ ③ 我的考勤 / ④ 我的请假 | 注册登录 / 考勤 / 请假 |
| **教师** (teacher) | ① 发起考勤（含 3 种签到方式触发按钮 + 弹窗） / ② 历史考勤（含请假审批） / ③ 统计报表 / ④ 账号 | + 报表 |
| **管理员** (lab_admin) | ① 实验室管理 / ② 安全培训 / ③ 准入日志 / ④ 使用率报表 / ⑤ 人脸管理 (W12 新增) | + 实验室准入 / 报表 |

## 关键技术决策

- **dlib-bin 20.0.1** (cp311/cp312/cp313 预编译 wheel) —— 避开 Windows 上 cmake 编译坑
- **face encoding dtype = float32** —— W3 决定，避免序列化/比对时量纲不一致
- **PyInstaller onedir** —— 380 MB，**真一键双击 exe**
- **4 层架构严格自顶向下** —— ui → service → dao → models
- **3 种签到方式统一 _create_record 公共核** (W13+) —— 刷脸 / 数字码 / 二维码走同一 UNIQUE 拦截 + 迟到判定 + signin_method 字段

## 验收

```bash
# 单元测试 (103 项)
.venv\Scripts\python.exe -m pytest tests/ -q

# 5 个 smoke 脚本
.venv\Scripts\python.exe scripts\smoke_full_flow.py        # 完整业务流 (W6)
.venv\Scripts\python.exe scripts\smoke_real_face.py        # dlib 真脸 + 摄像头 (W6)
.venv\Scripts\python.exe scripts\smoke_ui_qtest.py         # QTest 真实 UI (W6)
.venv\Scripts\python.exe scripts\smoke_e2e.py              # 打包后端到端 (W5)
.venv\Scripts\python.exe scripts\smoke_signin_methods.py   # 数字码 + 二维码 (W13+)
.venv\Scripts\python.exe scripts\smoke_audit_history.py    # W7-W12 历史修复回归

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
            ├── db/migration_w13.sql       ← W13+ 增量 (task_signin_code 新表 + signin_method 字段)
            ├── docs/                      ← 设计文档
            │   ├── ARCHITECTURE.md
            │   ├── DATABASE.md
            │   ├── WORKFLOWS.md
            │   ├── DEVELOPMENT.md
            │   ├── MANUAL_E2E.md          ← W3 端到端
            │   ├── PACKAGING.md           ← W5 打包
            │   ├── SMOKE_TESTS.md         ← W6 smoke 指南
            │   ├── SIGNIN_METHODS.md      ← W13+ 3 种签到方式
            │   └── superpowers/plans/     ← W3-W12+W13+ 计划
            │
            ├── src/                       ← 项目代码 (4 层)
            │   ├── main.py                ← 入口
            │   ├── config.py / db.py / constants.py
            │   ├── models/                ← 12 张表 ORM
            │   ├── dao/                   ← 13 个数据访问类
            │   ├── services/              ← 6 个业务服务 (auth/face/attendance/lab/leave/report)
            │   ├── ui/                    ← PyQt5 表现层
            │   └── utils/                 ← 工具 (dlib/paths/charts/crypto)
            │
            ├── tests/                     ← 单元测试 (103 项)
            │
            ├── scripts/                   ← 运维 / 烟测
            │   ├── init_db.py
            │   ├── seed_demo_data.py
            │   ├── cleanup_test_users.py
            │   ├── run_dev.sh / run_dev.bat
            │   ├── smoke_full_flow.py        ← W6 业务流
            │   ├── smoke_real_face.py        ← W6 真脸
            │   ├── smoke_ui_qtest.py         ← W6 QTest
            │   ├── smoke_e2e.py              ← W5 打包后端到端
            │   ├── smoke_signin_methods.py   ← W13+ 数字码 + 二维码
            │   └── smoke_audit_history.py    ← W7-W12 历史修复回归
            │
            └── models/                    ← dlib 模型 (git 忽略, 运行时下载)
            ```

## 提交记录

`git log --oneline` —— W2 → W13+ 共 **53 个 commit** (W3-W13+ 八轮迭代: face 识别 / 实验室准入 / 报表 / 打包 / leave / 5 次审计 / W13+ 数字码二维码)。
