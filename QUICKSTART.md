# 快速启动

## 🚀 第一次跑？跟着这 5 步走（5-10 分钟）

> **场景**：你刚刚 `git clone` 了这个项目，**本机第一次**想把它跑起来。
> 跟着下面顺序做，每步都说清楚要等什么、看什么。

### Step 1: 装 Python 3.13 + MySQL 8.0

- **Python**: 必须 **3.13.x**（其他版本 `dlib-bin` 没预编译 wheel，要 cmake 编译，坑很多）
  - 下载: https://www.python.org/downloads/release/python-3136/
  - 安装时 **勾上 "Add Python to PATH"**
  - 装完验证: `python --version` 应该输出 `Python 3.13.x`
- **MySQL 8.0**: https://dev.mysql.com/downloads/installer/
  - 装完记住你设置的 **root 密码**（待会写进 `.env`）
  - 验证服务在跑: `mysql -uroot -p` 能登进去
- **摄像头**（可选，人脸签到要用）: 任意 USB 摄像头 / 笔记本自带都行

### Step 2: 拉代码 + 建空数据库

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>

# 创建空数据库（MySQL 命令行里执行）
mysql -uroot -p
# 进入 mysql 提示符后:
CREATE DATABASE attendance_lab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

### Step 3: 装依赖（建议用 venv）

```bash
# 创建并激活虚拟环境
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# macOS/Linux:
source .venv/bin/activate

# 装依赖（这一步最慢,可能要 2-3 分钟）
pip install -r requirements.txt
```

> 如果 `pip install dlib-bin` 失败,见底部"常见问题 Q1"。

### Step 4: 配 .env（**必改 DB_PASSWORD**）

```bash
# Windows PowerShell:
Copy-Item .env.template .env
# Windows CMD / macOS / Linux:
cp .env.template .env
```

用记事本 / VSCode 打开 `.env`，**只改一行**：

```ini
DB_PASSWORD=YOUR_MYSQL_PASSWORD_HERE
                  ^^^^^^^^^^^^^^^^^^^^^
                  改成你 MySQL root 密码
```

其他全部保持默认。`DB_NAME` 跟 Step 2 创建的库名保持一致（默认 `attendance_lab`）。

### Step 5: 初始化 + 启动

```bash
# 建表 + 灌演示数据
python scripts/init_db.py
# 看到 "✅ 数据库初始化完成" 就 OK

# 启动 GUI —— ⚠️ 必须在项目根目录跑,不能 cd src
python -m src.main
```

**首次启动会卡 1-3 分钟**: 终端会显示
`[face_helper] 正在下载 dlib 模型 (~120MB)...`
—— 正常,等它下完。下次启动秒开。

**登录测试账号**:
- 学生: `test001` / `123456`
- 教师: `teacher01` / `123456`（或 `teacher001` / `123456`，W13+ 演示用）

---

## 常见问题（5 分钟内卡住先看这里）

| # | 现象 | 解决 |
|---|---|---|
| Q1 | `pip install dlib-bin` 失败 / 报 "找不到匹配版本" | 99% 是 Python 不是 3.13。先 `python --version` 确认。要么装 3.13，要么 `pip install cmake` + VS Build Tools + `pip install dlib`（编译 30+ 分钟，不推荐） |
| Q2 | `init_db.py` 报 `Access denied for user 'root'@'localhost'` | `.env` 里的 `DB_PASSWORD` 跟 MySQL 实际密码不一致。改完重启终端（环境变量要重读） |
| Q3 | 报 `Unknown database 'attendance_lab'` | 回到 Step 2，先 `CREATE DATABASE` |
| Q4 | 启动后白屏 / 摄像头打不开 | 摄像头被别的程序（微信 / 腾讯会议）占用了，关掉再试 |
| Q5 | 教师端弹二维码窗口报 "端口 5180 被占用" | `.env` 里加 `SIGNIN_WEB_PORT=5181`（改个空闲端口） |
| Q6 | 启动后立刻段错误 | 摄像头 + offscreen + QMessageBox 在 Windows 上有冲突。**别在 offscreen 模式下跑 GUI**，正常带显示器跑 |
| Q7 | dlib 模型下载到一半失败 | `models/` 目录下删掉半个文件，重启 `python -m src.main` 会自动重试。或手动从 https://github.com/davisking/dlib-models 下载 `shape_predictor_68_face_landmarks.dat.bz2` 和 `dlib_face_recognition_resnet_model_v1.dat.bz2`，解压到 `models/` |

---

## 当前状态（W15+ 收口）

✅ Python 3.13 + PyQt5 + SQLAlchemy 2.0 + bcrypt + PyMySQL 装好
✅ MySQL 8.0 连上，建库 `attendance_lab`，**14 张表**（12 schema + w13+ task_signin_code + w14+ course_teacher）
✅ dlib-bin 20.0.1 装好，dlib 模型已自动下载（~120 MB）
✅ pytest **188/188** 全过，~72s 7 warning（含 W15+ 新增 3 项 latest API 测试）
✅ 8 个 smoke 脚本全过（full_flow / real_face / ui_qtest / e2e / signin_methods / audit_history / signin_web / signin_web_build）
✅ 3 角色（学生 / 教师 / 管理员）端到端跑通，含 3 种签到方式（刷脸 / 数字码 / 二维码）
✅ W14 多端登录签到（手机扫码 → 浏览器 H5 → 教师端实时反馈）+ W15+ H5 polling 防缓存
✅ UI 现代化（5 主窗体 + 12 widget margin/spacing 加大 + design tokens）
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

# 4.（可选）W13+ / W14+ 增量迁移：14 张表
#    init_db.py 已内置 w13/w14 migration, 跑过 init_db 不需要再跑 migration_*.sql
#    （仅当你的库是 W12 及更早部署的, 手动跑:
#      mysql ... < db/migration_w13.sql
#      mysql ... < db/migration_w14.sql）

# 5. 启动 GUI —— 推荐双击 start.bat
start.bat
```

## 启动 GUI

**推荐方式**（双击 `start.bat`）：

```bash
# Windows: 双击项目根目录的 start.bat
# 内部流程: chcp 65001 >nul + cd /d "%~dp0" + .venv\Scripts\python.exe -m src.main
# 已修 cmd 5.1 编码坑 (圆括号 + 中文乱码), 全 ASCII 实现
```

**等价方式**（命令行）：

```bash
cd "D:/Attendance-Management-system-using-face-recognition"
.venv\Scripts\python.exe -m src.main        # Windows
python -m src.main                          # Linux/macOS
```

**清理多 GUI 进程**（W15+ 新增）：

```bash
# 多个 python.exe 同时跑 / 端口冲突 / SQLAlchemy 行为不一致时
kill_all_python.bat    # Windows 一键清所有 python.exe + 然后再双击 start.bat
```

> ⚠️ 一定要在项目根目录执行，不能 `cd src` 之后再 `python main.py`，那样 `src` 自己找不到自己。
> ⚠️ 不要在 offscreen 模式下触发按钮（Windows PyQt5 offscreen 与 QMessageBox 有已知冲突）。
> ⚠️ **W15+ 永远 "kill all + start one"** —— 多 GUI 进程会抢端口 + 行为诡异。
> 直接在带显示器的本地终端跑就行。

## 测试账号

| 用户名 | 密码 | 角色 | 备注 |
|---|---|---|---|
| `test001` | `123456` | 学生 | 已注册，方向：智能医学工程 |
| `teacher01` | `123456` | 教师 | 已注册，教 BME201 |
| `teacher001` | `123456` | 教师 | W13+ / W14+ 演示用，已挂 BME201 + 两个 open task |
| `demo_student` | `123456` | 学生 | W14+ 多端登录签到演示用，student_id=`202400502133` |
| `001` | `123456` | 学生 | W14+ 学号登录演示用，student_id=`123456`（注意 demo_student 才是 W14 演示账号） |

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
  - 创建后 Tab 右下角可点「🎲 数字签到」/「📱 二维码签到」→ 弹码窗口（**W15+ 5 分钟倒计时** + 旧码失效）
  - **W14+ 多端登录签到**：点「📱 二维码签到」→ 教师电脑起 :5180 FastAPI + H5 签到页 → 学生手机扫码 → 浏览器打开 H5 → 输账密 → 提交 → 教师端实时签到列表自动刷新
  - **W15+ H5 polling**：H5 进入后每 3 秒拉最新 LIVE token，教师中途刷码老 H5 URL 不会失效
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
# 全量（188 项）
pytest tests/ -v

# 单独跑
pytest tests/test_auth_service.py -v
pytest tests/test_attendance_service.py -v
pytest tests/test_face_helper.py -v
pytest tests/test_signin_web.py -v          # W14+W15+ 多端登录
pytest tests/test_task_signin_code_dao.py -v

# W15+ 最新 API
pytest tests/test_signin_web.py -v -k latest
```

## Smoke 端到端

```bash
.venv\Scripts\python.exe scripts\smoke_full_flow.py        # W6 业务流
.venv\Scripts\python.exe scripts\smoke_real_face.py        # dlib 真脸 + 摄像头
.venv\Scripts\python.exe scripts\smoke_ui_qtest.py         # QTest 真实 UI
.venv\Scripts\python.exe scripts\smoke_e2e.py              # 打包后端到端
.venv\Scripts\python.exe scripts\smoke_signin_methods.py   # W13+ 数字码 + 二维码
.venv\Scripts\python.exe scripts\smoke_audit_history.py    # W7-W12 历史修复回归
.venv\Scripts\python.exe scripts\smoke_signin_web.py       # W14+ 9 步全链路
.venv\Scripts\python.exe scripts\smoke_signin_web_build.py # W14+ 打包后多端登录
```

## 已知问题

- dlib 在 Python 3.13 上没有官方预编译 wheel，解决方案：
  1. `pip install dlib-bin`（社区编译版，**已采用**）
  2. 不行再 `pip install cmake` + Visual Studio Build Tools + `pip install dlib`
  3. 还不行就降级 Python 到 3.11（推荐 venv 隔离）
- PyQt5 在 Windows offscreen 模式下触发 QMessageBox 会段错误；直接带显示器跑就行。
- W13+ smoke 脚本里没有 ✓/✗ Unicode 字符（Windows PowerShell 5.1 默认 GBK 编码不支持）。
- **W15+ 多 GUI 进程抢资源**：start.bat 启的 .venv GUI 没关 + PowerShell/system Python 启的另一个 → 5180 端口冲突 + SQLAlchemy 连接池独立。**修法**：跑 `kill_all_python.bat`（全 ASCII）一次清干净 + 双击 start.bat 重启
- **W15+ .bat 必须全 ASCII**：cmd 5.1 默认 GBK 编码解析 .bat 时把 UTF-8 注释里的中文+英文组合字串当命令执行。**修法**：所有 .bat 全 ASCII + 顶部加 `chcp 65001 >nul` + echo 内容避免圆括号
- **W15+ H5 入口路由不校验 token**（W14 时的闭包校验已删）：in-memory state 跟 DB LIVE 永远不一致。真实校验交给 `dao.find_active_by_value(*, is_active=1, expires_at>now)` 实时查 DB
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
