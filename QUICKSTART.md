# 快速启动

## 当前状态（W13+ 收口）

✅ Python 3.13 + PyQt5 + SQLAlchemy 2.0 + bcrypt + PyMySQL 装好
✅ MySQL 8.0 连上，建库 `attendance_lab`，**13 张表**（12 schema + 1 w13+ migration）
✅ dlib-bin 20.0.1 装好，dlib 模型已自动下载（~120 MB）
✅ pytest **103/103** 全过，~40s 0 warning
✅ 6 个 smoke 脚本全过（full_flow / real_face / ui_qtest / e2e / signin_methods / audit_history）
✅ 3 角色（学生 / 教师 / 管理员）端到端跑通，含 3 种签到方式（刷脸 / 数字码 / 二维码）
✅ PyInstaller onedir 380 MB 一键 exe 可打包

## 5 分钟跑起来

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env（首次）
cp .env.template .env       # Windows: copy .env.template .env
# 编辑 .env，把 DB_PASSWORD 改成你的 MySQL 密码

# 3. 初始化数据库（建库 + 12 张表）
python scripts/init_db.py

# 4.（可选）W13+ 增量迁移：13 张表 + signin_method 字段
#    init_db.py 已内置 w13 migration, 跑过 init_db 不需要再跑 migration_w13.sql
#    （仅当你的库是 W12 及更早部署的, 手动跑: mysql ... < db/migration_w13.sql）

# 5. 启动应用
python -m src.main
```

## 启动 GUI

**推荐方式**（在项目根目录）：

```bash
cd "D:/Attendance-Management-system-using-face-recognition"
python -m src.main
```

**等价方式**（用启动脚本）：

```bash
bash scripts/run_dev.sh        # Linux/macOS
scripts\run_dev.bat            # Windows
```

> ⚠️ 一定要在项目根目录执行，不能 `cd src` 之后再 `python main.py`，那样 `src` 自己找不到自己。
> ⚠️ 不要在 offscreen 模式下触发按钮（Windows PyQt5 offscreen 与 QMessageBox 有已知冲突）。
> 直接在带显示器的本地终端跑就行。

## 测试账号

| 用户名 | 密码 | 角色 | 备注 |
|---|---|---|---|
| `test001` | `123456` | 学生 | 已注册，方向：智能医学工程 |
| `teacher01` | `123456` | 教师 | 已注册，教 BME201 |
| `teacher001` | `123456` | 教师 | W13+ 演示用，已挂 BME201 + 两个 open task |

> 跑 `pytest tests/test_auth_service.py` 会自动注册大量测试账号，**不影响真实数据**（用户名带随机后缀 + session 级 autouse fixture 跑完自动清）。

## 你可以做的验证

### 1. 登录窗口
- 用 `test001/123456` 登录，角色选「学生」→ 应该看到「登录成功」提示
- 用 `test001/123456` 登录，角色选「教师」→ 应该看到「角色不匹配」提示
- 用错密码 → 应该看到「用户名或密码错误」
- 同一 IP 5 分钟内 5 次密码错 → 触发暴力破解保护（封禁 15 分钟）

### 2. 学生端（test001 登录后，4 Tab）
- Tab 1 **人脸注册** → 启动摄像头采集 30 张，自动训练
- Tab 2 **签到**（子 Tab 切换 3 种方式）：
  - 🤳 **刷脸签到** → 摄像头识别，距离 < 0.4 视为本人
  - 🔢 **数字码签到** → 输入教师弹的 4 位数字
  - 📷 **二维码签到** → 摄像头扫教师弹的 QR
- Tab 3 **我的考勤** → 看历史签到 + 状态
- Tab 4 **我的请假** → 申请 / 撤回

### 3. 教师端（teacher01 / teacher001 登录后，4 Tab）
- Tab 1 **发起考勤** → 选课程 + 教室 + 时间段 → 创建任务
  - 创建后 Tab 右下角可点「🎲 数字签到」/「📱 二维码签到」→ 弹码窗口（60s 倒计时 + 旧码失效）
- Tab 2 **历史考勤** → 看任务列表，结束选中任务自动补齐缺勤
- Tab 3 **统计报表** → 出勤率 / 请假率
- Tab 4 **账号** → 改密

### 4. 管理员端（lab_admin 角色，5 Tab）
- Tab 1 **实验室 CRUD** → 增删改实验室 + 准入级别
- Tab 2 **安全培训** → 录入 / 续期学生培训记录
- Tab 3 **准入日志** → 看历史准入（granted/denied + 原因）
- Tab 4 **使用率报表** → 4 类 matplotlib 图表
- Tab 5 **人脸管理** (W12 新增) → 查 / 删任意用户人脸数据

## 运行测试

```bash
# 全量（103 项）
pytest tests/ -v

# 单独跑
pytest tests/test_auth_service.py -v
pytest tests/test_attendance_service.py -v
pytest tests/test_face_helper.py -v

# W13+ 数字码 + 二维码
pytest tests/test_attendance_service.py::test_generate_signin_code -v
pytest tests/test_task_signin_code_dao.py -v
```

## Smoke 端到端

```bash
.venv\Scripts\python.exe scripts\smoke_full_flow.py        # W6 业务流
.venv\Scripts\python.exe scripts\smoke_real_face.py        # dlib 真脸 + 摄像头
.venv\Scripts\python.exe scripts\smoke_ui_qtest.py         # QTest 真实 UI
.venv\Scripts\python.exe scripts\smoke_e2e.py              # 打包后端到端
.venv\Scripts\python.exe scripts\smoke_signin_methods.py   # W13+ 数字码 + 二维码
.venv\Scripts\python.exe scripts\smoke_audit_history.py    # W7-W12 历史修复回归
```

## 已知问题

- dlib 在 Python 3.13 上没有官方预编译 wheel，解决方案：
  1. `pip install dlib-bin`（社区编译版，**已采用**）
  2. 不行再 `pip install cmake` + Visual Studio Build Tools + `pip install dlib`
  3. 还不行就降级 Python 到 3.11（推荐 venv 隔离）
- PyQt5 在 Windows offscreen 模式下触发 QMessageBox 会段错误；直接带显示器跑就行。
- W13+ smoke 脚本里没有 ✓/✗ Unicode 字符（Windows PowerShell 5.1 默认 GBK 编码不支持）。
- LabAccessService.check_access / LeaveService.list_pending_for_task 是 service 层 API，目前没有 UI 入口调用（W4/W6 设计如此，docstring 写明给"门口刷脸机"扩展；smoke 已覆盖 7 分支）。属已知项目约束。

## 目录速查

```
src/      主代码（ui / services / dao / models / utils）
db/       schema.sql (12 表) + migration_w13.sql (1 表 + 1 字段)
docs/     PROJECT_PLAN / ARCHITECTURE / DATABASE / WORKFLOWS / SIGNIN_METHODS / ...
tests/    18 个测试文件，103 个用例
scripts/  init_db / run_dev / 5 smoke + 1 audit_history
```

详细结构见 [docs/STRUCTURE.md](docs/STRUCTURE.md)。
