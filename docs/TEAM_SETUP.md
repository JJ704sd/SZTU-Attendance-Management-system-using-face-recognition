# 组员上手指南（跨机适配运行）

> 给组员在自己的 Windows 笔记本上跑这个项目的完整步骤。
> 按顺序做, 5-10 分钟跑通 GUI, 15-20 分钟跑通测试。

## 0. 前置条件（一次性）

| 工具 | 版本 | 验证命令 | 备注 |
|---|---|---|---|
| **Python** | 3.11 / 3.12 / 3.13 任意一个 | `python --version` | 推荐 3.11+（dlib-bin 在三个版本都有 wheel） |
| **MySQL** | 8.0+ | `mysql --version` | 启动 `mysqld` 服务, root 密码记住 |
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
> python -c "import PyQt5, dlib, cv2, sqlalchemy, pymysql, bcrypt, qrcode, numpy, matplotlib; print('all OK')"
> ```
> 应输出 `all OK`。**`qrcode` 是 W14 修复加上的, 必须装**（教师端二维码签到依赖）。

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
# W14 修复: 自动跑 schema.sql + migration_w13.sql (13 张表)
python scripts\init_db.py
```

**期望输出**：
```
[INFO] 准备初始化 attendance_lab @ 127.0.0.1:3306 ...
[INFO] 将同时跑 migration_w13.sql (W13+ 增量迁移)
[OK] schema.sql 执行完成
[OK] migration_w13.sql 执行完成
[OK] 数据库 attendance_lab 初始化完成 (共 2 个 SQL 脚本)
```

> 看到 3 个 `[OK]` 就成功了。13 张表（user / face_encoding / course / classroom / laboratory / attendance_task / attendance_record / leave_request / lab_training / lab_access_log / course_enrollment / login_attempt / **task_signin_code**）都建好。
>
> 若失败：
> - `[ERR] 未找到 mysql 命令` → MySQL Client 没在 PATH, 装 MySQL 时勾上"Add to PATH"或手动加
> - `[ERR] .env 中没有 DB_PASSWORD` → 第 3 步没配 .env
> - `Access denied` → 密码错了

## 5. 启动 GUI

```powershell
# ⚠️ 必须在项目根目录跑, 不能 cd src
python -m src.main
```

**首次启动 5-10 秒**（dlib 模型 120MB 首次下载，要联网），后续启动 2 秒。

**自动行为**：
1. `init_db()` 自动建表（已建就跳过）
2. `_FaceCache` 预热（库中没人脸 → warning 但不挂）
3. `face_helper.ensure_models()` 验 dlib 模型路径（首次跑会下 120MB）
4. 弹登录窗口

**演示账号**：

| 角色 | 用户名 | 密码 | 说明 |
|---|---|---|---|
| 学生 | `test001` | `123456` | 跑 `pytest tests/test_auth_service.py` 会自动建 |
| 教师 | `teacher01` | `123456` | 跑 `scripts/seed_demo_data.py` 会自动建 |
| 管理员 | `labadmin01` | `123456` | 跑 `scripts/seed_demo_data.py` 会自动建 |
| 演示 | `teacher001` | `123456` | W4 预置, 已挂 BME201 + 2 open task |

若 `test001 / teacher01` 跑不进去, 跑一次 seed：

```powershell
python scripts\seed_demo_data.py
```

## 6. 跑测试（验证环境 OK）

```powershell
# 全测 (136 项 / ~47s / 0 warning)
python -m pytest tests/ -q

# 期望结尾:
# 136 passed in ~45s
```

若失败先看 [故障排除](#故障排除)。

**7 个 smoke 端到端脚本**（更接近真实用户行为）：

```powershell
python scripts\smoke_full_flow.py         # 完整业务流 (W6)
python scripts\smoke_real_face.py         # dlib 真脸 + 摄像头 (W6, 需要 webcam)
python scripts\smoke_ui_qtest.py          # QTest 真实 UI (W6)
python scripts\smoke_e2e.py               # 打包后端到端 (W5)
python scripts\smoke_signin_methods.py    # W13+ 数字码 + 二维码签到
python scripts\smoke_audit_history.py     # W7-W12 历史修复回归 (16/16 OK)
python scripts\smoke_full_regression.py   # 6 service + 13 dao 全公开方法 (~30 项)
```

## 7. 打 exe（可选, 给老师 / 演示用）

```powershell
# 装 pyinstaller（已装在 requirements 里, 这步可跳）
pip install pyinstaller

# 打包 (~5 分钟, 产物 ~400 MB onedir 目录)
pyinstaller build.spec

# 产物: dist\attendance-system\attendance-system.exe
# 双击即可运行（首次会跑 init_db + 下 dlib 模型）
```

详细见 [docs/PACKAGING.md](PACKAGING.md)。

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
- **13 张表** (schema.sql 12 + migration_w13.sql 1)
- **6 个 service** / **13 个 widget** / **4 个主窗口** (login / register / student / teacher / admin)
- **3 种签到方式**：刷脸 / 数字码 (对分易式 60s 倒计时) / 二维码 (base64 token)
- **依赖**：PyQt5 + SQLAlchemy 2.0 + dlib-bin + opencv + bcrypt + qrcode
- **测试**：136 单元 + 7 smoke
- **打包**：PyInstaller onedir 380 MB

详细看 [README.md](../README.md) + [CLAUDE.md](../CLAUDE.md) + [docs/PACKAGING.md](PACKAGING.md) + [docs/SMOKE_TESTS.md](SMOKE_TESTS.md) + [docs/SIGNIN_METHODS.md](SIGNIN_METHODS.md)。

---

**遇到问题先看故障排除；还不行就群里吼一声。**
