# 组员上手指南（跨机适配运行）

> 给组员在自己的 Windows 笔记本上跑这个项目的完整步骤。
> 按顺序做, 5-10 分钟跑通 GUI, 15-20 分钟跑通测试。

## 0. 前置条件（一次性）

| 工具 | 版本 | 验证命令 | 备注 |
|---|---|---|---|
| **Python** | **3.10+**（推荐 3.13.x） | `python --version` | 项目代码用 PEP 604 `X \| None` 语法（需 3.10+）；dlib-bin 20.0.1 在 PyPI 有 cp311/cp312/cp313 三个 wheel，3.11/3.12 理论能跑。**3.13.x 是远端 CI 全程验证的版本**，219 单元 + 10 smoke 全过 |
| **MySQL** | **8.0.29+**（**必须**） | `mysql --version` | migration 用 `IF NOT EXISTS` 语法，5.7 / 8.0.28- 不支持；启动 `mysqld` 服务, root 密码记住 |
| **Git** | 任意 | `git --version` | 拉项目用 |
| **Webcam** | 任意 USB / 内置 | (无) | 仅"刷脸签到"需要, 数字码 / 二维码不依赖 |
| **Visual C++ Runtime** | Win10 1903+ 自带 | (无) | dlib-bin 需要, 大多数 Win10/11 已装 |

### 0.1 验证 MySQL 在跑

```powershell
# PowerShell
net start mysql           # 若未启动, 管理员 PowerShell 执行
mysql -u root -p           # 输密码进得去就行
```

### 0.2 确认 `mysql` CLI 在 PATH 里（重要）

```powershell
where.exe mysql
# 期望输出: C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe
# 若 "信息: 未找到文件" — 装 MySQL 时勾了 "Add to PATH" 就行, 否则手动加
```

## 1. 拿到项目

```powershell
# 方式 A: git clone（推荐, 后续更新方便）
git clone https://github.com/<你的仓库地址>/Attendance-Management-system-using-face-recognition.git
cd Attendance-Management-system-using-face-recognition

# 方式 B: 解压老师发的 .zip
# 解压到任意位置, 比如 D:\projects\
# cd D:\projects\Attendance-Management-system-using-face-recognition
```

> ⚠️ **路径建议**：项目根目录路径**不要带中文 / 空格**, 否则 dlib / cv2 偶发崩。
> 推荐：`D:\projects\` `E:\code\` `C:\dev\`, 避免 `D:\我的项目\`。

## 2. 建 venv + 装依赖

```powershell
# 在项目根目录
python -m venv .venv

# 激活 venv（每次新开 PowerShell 都要重做）
.\.venv\Scripts\Activate.ps1

# 若提示 "无法加载文件...因为在此系统上禁止运行脚本"
# 管理员 PowerShell 跑一次: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# 然后重新激活

# 装依赖（~3-5 分钟, dlib-bin 100MB wheel 下载占大头）
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> 装完验证：
> ```powershell
> python -c "import PyQt5, dlib, cv2, sqlalchemy, pymysql, bcrypt, qrcode, numpy, matplotlib, fastapi, uvicorn, jinja2, httpx; print('all OK')"
> ```
> 应输出 `all OK`。**4 个 W14+ 依赖**（fastapi / uvicorn / jinja2 / httpx）漏装会导致手机扫码 H5 签到 + H5 polling 崩。

## 3. 配 .env

```powershell
# 从模板复制
Copy-Item .env.template .env

# 编辑填密码（用记事本 / VSCode 都行）
notepad .env
```

`.env` 内容（5 个字段, 必填 `DB_PASSWORD`）：

```ini
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的MySQL密码       ← 改成你自己的
DB_NAME=attendance_lab
```

> 改完保存。**修改 .env 后需要重启程序才生效**。

## 4. 初始化数据库（首次必跑）

```powershell
# W14+ 修复: 自动跑 schema.sql + migration_w13.sql + migration_w14.sql (14 张表)
python scripts\init_db.py
```

**期望输出**：
```
[INFO] 准备初始化 attendance_lab @ 127.0.0.1:3306 ...
[INFO] 将同时跑 migration_w13.sql (W13+ task_signin_code)
[INFO] 将同时跑 migration_w14.sql (W14+ course_teacher)
[OK] schema.sql 执行完成
[OK] migration_w13.sql 执行完成
[OK] migration_w14.sql 执行完成
[OK] 数据库 attendance_lab 初始化完成 (共 3 个 SQL 脚本, 14 张表)
```

> 看到 4 个 `[OK]` 就成功了。**14 张表**（user / face_encoding / course / classroom / laboratory / attendance_task / attendance_record / leave_request / lab_training / lab_access_log / course_enrollment / login_attempt / **task_signin_code** / **course_teacher**）都建好。
>
> 若失败：
> - `[ERR] 未找到 mysql 命令` → MySQL Client 没在 PATH, 装 MySQL 时勾上"Add to PATH"或手动加
> - `[ERR] .env 中没有 DB_PASSWORD` → 第 3 步没配 .env
> - `Access denied` → 密码错了

## 5. 启动 GUI（首次会弹 Windows 防火墙）

```powershell
# ⚠️ 必须在项目根目录跑
python -m src.main
```

**首次启动会自动发生**：
1. `init_db()` 建表（已建就跳过）
2. dlib 模型 120MB 下载（首次, 断网会失败）
3. **Windows 防火墙弹窗**（关键！看下方说明）
4. 预热 + 弹登录窗口

### 5.1 Windows 防火墙授权（首次必点允许）

首次启动会弹 **"Windows Defender 防火墙已阻止 Python 的某些功能"**：

- **专用网络** ✅ 勾上
- **公用网络** ✅ 勾上（**组员在咖啡店/图书馆/校园 WiFi 时这是关键**）
- 点 **"允许访问"**

> **为什么要这一步**：W14 多端签到启了 `uvicorn` HTTP 服务（端口 5180），监听 `0.0.0.0`（全网卡），学生手机扫码要连进来。Windows 防火墙若不允许，**学生手机连不上，教师以为"网络问题"**。
>
> **如果不小心点了"取消"**：补上 →
> ```powershell
> # 管理员 PowerShell
> New-NetFirewallRule -DisplayName "AttendanceSigninWeb" -Direction Inbound -LocalPort 5180 -Protocol TCP -Action Allow
> ```
> 然后重启 `python -m src.main`。

### 5.2 启动成功标志 — `app.log` 应有

```
W5: 文件日志已启用 -> D:\...\app.log
=== 应用启动 ===
init_db: 开始导入 models
init_db: models 导入完成, 调 create_all
init_db: create_all 完成
数据库初始化完成
人脸编码缓存预热完成: N 个用户
dlib 模型路径 OK: sp=shape_predictor_68_face_landmarks.dat (95MB), fr=dlib_face_recognition_resnet_model_v1.dat (21MB)
```

> 看不到 "数据库初始化完成" 或 "dlib 模型路径 OK" 那一行？见 [故障排除](#故障排除) T1 / T4。

### 5.3 演示账号

| 角色 | 用户名 | 密码 | 说明 |
|---|---|---|---|
| 学生 | `test001` | `123456` | 跑 `pytest tests/test_auth_service.py` 会自动建 |
| 教师 | `teacher01` | `123456` | 跑 `scripts/seed_demo_data.py` 会自动建 |
| 管理员 | `labadmin01` | `123456` | 跑 `scripts/seed_demo_data.py` 会自动建 |
| 演示 | `teacher001` | `123456` | W4 预置, 已挂 BME201 + 2 open task |

若 `test001 / teacher01` 跑不进去，跑一次 seed：

```powershell
python scripts\seed_demo_data.py
```

## 6. 跑测试（验证环境 OK）

```powershell
# 全测 (219 项 / ~67s / 2 warnings — uvicorn 内部 websockets.legacy + WebSocketServerProtocol 第三方依赖 deprecation, 与本项目无关)
python -m pytest tests/ -q

# 期望结尾:
# 219 passed in ~60s
```

若失败先看 [故障排除](#故障排除)。

**10 个 smoke 端到端脚本**（更接近真实用户行为）：

```powershell
python scripts\smoke_full_flow.py            # 完整业务流 (W6)
python scripts\smoke_real_face.py            # dlib 真脸 + 摄像头 (W6, 需要 webcam)
python scripts\smoke_ui_qtest.py             # QTest 真实 UI (W6)
python scripts\smoke_e2e.py                  # 打包后端到端 (W5)
python scripts\smoke_signin_methods.py       # W13+ 数字码 + 二维码签到
python scripts\smoke_audit_history.py        # W7-W12 历史修复回归 (16/16 OK)
python scripts\smoke_full_regression.py      # 6 service + 13 dao 全公开方法 (~30 项)
python scripts\smoke_qrcode_build.py         # W14+ 防 hiddenimports 漏配 (二维码)
python scripts\smoke_signin_web.py           # W14 H5 多端签到 (9 步)
python scripts\smoke_signin_web_build.py     # W14 H5 打包验证
```

## 7. 打 exe（可选, 给老师 / 演示用）

```powershell
# 装 pyinstaller（已装在 requirements 里, 这步可跳）
pip install pyinstaller

# 打包 (~5 分钟, 产物 ~380 MB onedir 目录)
pyinstaller build.spec

# 产物: dist\attendance-system\attendance-system.exe
# 双击即可运行（首次会跑 init_db + 下 dlib 模型）
```

详细见 [README.md](../README.md) 的「PyInstaller 打包」章节 + `build.spec`。

## 故障排除

### T1. 启动 GUI 弹 "无法连接或初始化数据库"

按顺序排查：
1. MySQL 服务在跑？`net start mysql`（管理员 PowerShell）
2. `.env` 的 `DB_PASSWORD` 填对了？
3. `.env` 的 `DB_PORT=3306` 和实际一致？
4. 端口被占？`netstat -ano | findstr :3306`

### T2. 教师点"📱 二维码签到"弹窗显示"⚠️ 渲染失败：No module named 'qrcode'"

→ 没装 `qrcode` 包。W14 修复后 requirements.txt 已含, 但老 checkout 可能漏装：

```powershell
pip install 'qrcode>=7.4,<9.0'
```

### T3. 学生 / 教师点数字码 / 二维码签到报 "Table 'attendance_lab.task_signin_code' doesn't exist"

→ 没跑 migration_w13.sql。W14 修复后 init_db.py 会自动跑, 但老数据库可能要手动补：

```powershell
python scripts\init_db.py    # 跑一遍, 幂等
```

### T4. dlib 模型首次下载慢 / 失败

- `models/` 目录需可写（首次自动建）
- 需联网（GitHub raw）
- 下载失败可重试（已下载的 .bz2 不会自动删, 续传）
- 想跳过下载: 把别人已下载的 `models\shape_predictor_68_face_landmarks.dat` + `dlib_face_recognition_resnet_model_v1.dat` 拷到本地 `models\` 即可

### T5. PowerShell 输出 GBK 乱码

- 不影响功能
- 改用 Windows Terminal 或 cmd 跑
- 或在 PowerShell 顶部加：`[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`

### T6. 摄像头打不开

1. 摄像头被其他程序（QQ / 微信 / Zoom）占用
2. Windows 设置 → 隐私 → 摄像头 → 允许桌面应用访问

### T7. `git push` 失败 (Connection refused / timeout)

全局 `.gitconfig` 配了代理 `127.0.0.1:17891` 会阻断 GitHub。命令级绕开：

```powershell
git -c http.proxy= -c https.proxy= push -u origin main
```

## 跟上游同步最新代码

```powershell
git pull origin main
pip install -r requirements.txt --upgrade     # 万一加了新包
python scripts\init_db.py                      # 万一加了新表
python -m src.main                             # 验证 GUI 起来
```

## 项目速览

- **架构**：4 层 (ui → service → dao → model) + utils
- **14 张表** (schema.sql 12 + migration_w13.sql 1 + migration_w14.sql 1)
- **7 个 service** / **13 个 widget** / **5 个主窗口** (login / register / student / teacher / admin)
- **3 种签到方式**：刷脸 / 数字码 (对分易式 60s 倒计时) / 二维码 (base64 token)
- **W14 多端登录签到**：FastAPI 嵌入 + H5 签到页 (手机扫码 → 浏览器 → 教师端实时反馈)
- **依赖**：PyQt5 + SQLAlchemy 2.0 + dlib-bin + opencv + bcrypt + qrcode + fastapi + uvicorn + jinja2 + httpx
- **测试**：219 单元 + 10 smoke
- **打包**：PyInstaller onedir 380 MB

详细看 [README.md](../README.md) + [CLAUDE.md](../CLAUDE.md) + [docs/SIGNIN_METHODS.md](SIGNIN_METHODS.md) + [docs/TESTING_CHECKLIST.md](TESTING_CHECKLIST.md)；smoke 用法见 [README.md § 验收](../README.md#验收)。

---

**遇到问题先看故障排除；还不行就群里吼一声。**
