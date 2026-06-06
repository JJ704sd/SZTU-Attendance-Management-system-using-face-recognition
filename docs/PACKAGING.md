# 打包与分发指南 (PACKAGING)

> W5 产出：把 PyQt5 桌面应用打成单目录可执行 (`dist/attendance-system/`)，
> 老师/同学拷一目录、改 `.env`、双击 exe 就能用，不依赖 Python 3.11 环境。

## 1. 怎么打 (开发者视角)

### 1.1 一次命令

```bash
# 在项目根目录
pyinstaller build.spec
# 或: .venv\Scripts\python.exe -m PyInstaller --noconfirm build.spec
```

输出：`dist/attendance-system/attendance-system.exe` (10.8 MB) +
`_internal/` (~250 MB，PyQt5 + dlib + numpy + matplotlib) + `models/` (122 MB) +
`.env.template` (用户配置模板)。

### 1.2 关键技术点 (build.spec)

| 决策 | 原因 |
|---|---|
| **onedir 模式**（不是 onefile）| 启动快 (~2s)，调试容易。onefile 启动要解压 5-10s |
| **console=False** | GUI 应用无控制台 |
| **hiddenimports 显式列 16 项** | PyInstaller 静态分析扫不到 pymysql dialect / bcrypt C ext / 项目 service / dao |
| **--collect-all PyQt5** | platforms/plugins 兜底自动包含 |
| **excludes 12 项** | tkinter / pytest / IPython 等瘦身 |
| **post-build 拷 models/ + .env.template** | dlib 模型不入 exe (122 MB 太大)；用户 .env 含密码不入 git |

### 1.3 路径兼容 (src/utils/paths.py)

```python
def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent  # 打包后: exe 同级
    return Path(__file__).resolve().parent.parent.parent  # dev: 项目根
```

所有资源路径 (`models/`、`dataset/`、`.env`、`app.log`) 都基于 `APP_ROOT` 单例。

### 1.4 dlib 模型

- **不打包**进 exe（122 MB 让 exe 太大）
- 首次启动 `face_helper.ensure_models()` 检查 `<APP_ROOT>/models/`
- 缺失则从 GitHub 下载 `shape_predictor_68_face_landmarks.dat.bz2` (95 MB) +
  `dlib_face_recognition_resnet_model_v1.dat.bz2` (21 MB)
- 首次启动**需联网**；之后离线运行 OK
- post-build 阶段如果项目根 `models/` 已有 .dat，会自动拷到 `dist/attendance-system/models/`

## 2. 用户上手 3 步 (分发视角)

### 2.1 第一步：拷目录

把 `dist/attendance-system/` 整个目录拷到客户机任意位置。
例如 `D:\Programs\attendance-system\`。

### 2.2 第二步：配 .env

在 `dist/attendance-system/` 目录下：

```powershell
# 复制模板
Copy-Item .env.template .env

# 编辑填密码
notepad .env
```

`.env.template` 包含 5 个字段，最关键的是 `DB_PASSWORD=YOUR_MYSQL_PASSWORD_HERE`。

### 2.3 第三步：双击 exe

双击 `dist/attendance-system/attendance-system.exe`。

- **首次启动**：连接 MySQL 建表 + 预热 dlib 模型缓存 + 弹登录窗口 (~5-10s)
- **后续启动**：~2s 即可

如果 MySQL 没建库，程序会用 `Base.metadata.create_all` 自动建 12 张表。

## 3. 已知问题 + 排查

### 3.1 MySQL 没启 / 密码错

**症状**：弹错误框 "无法连接或初始化数据库"。

**排查**：
1. MySQL 服务启动？`net start mysql` 或服务管理器
2. `.env` 的 `DB_PASSWORD` 填对了？
3. 端口对？默认 3306

### 3.2 首次启动卡住

**症状**：双击 exe 后 30s 内窗口没出来。

**排查**：看 `dist/attendance-system/app.log`（自动记录启动链路）：
- `W5: 文件日志已启用` → ok
- `init_db: 开始导入 models` → ok
- `dlib 模型路径 OK` → 模型加载成功
- 第一次刷脸才会真正加载 dlib 模型，启动时只验路径

### 3.3 摄像头打不开 (刷脸时)

**症状**：学生端"我的签到"页提示"摄像头不可用"。

**排查**：
1. 摄像头被其他程序（QQ / 微信 / Zoom）占用？
2. Windows 隐私设置允许桌面应用访问摄像头？

### 3.4 体积大 (~380 MB)

**预期**：onedir 模式正常量级（PyQt5 70 + dlib 100 + numpy 50 + matplotlib 50 + 其它）。

**不要切 onefile**：启动 5-10s 解压更糟。

### 3.5 在没 Python 的机器跑

**完全 OK**：PyInstaller 打包后 exe 是独立可执行，不依赖系统 Python。

唯一依赖：Windows 10/11 + Visual C++ 2015+ runtime (Win10 1903+ 自带)。

### 3.6 关掉 exe 时有 stderr 报错

PyInstaller 6.x 在子进程关闭时偶尔报 `_internal/PyInstaller/...` 路径问题，**不影响功能**。

## 4. 验证打包产物 (开发者自查)

跑 smoke_e2e.py 自动验证（PowerShell）：

```powershell
.venv\Scripts\python.exe scripts\smoke_e2e.py
```

预期输出（PASS）：

```
[setup] copied .env -> .../attendance-e2e-XXX/attendance-system/.env
[start] .../attendance-system.exe
[OK] 进程 <PID> 还活着 (10.0s)
[OK] app.log 有 8 行
  [OK] log 含 'W5: 文件日志已启用'
  [OK] log 含 '=== 应用启动 ==='
  [OK] log 含 'init_db: 开始导入 models'
  [OK] log 含 'init_db: models 导入完成'
  [OK] log 含 'init_db: create_all 完成'
  [OK] log 含 '数据库初始化完成'
  [OK] log 含 'dlib 模型路径 OK'
[cleanup] killing PID <PID>

[PASS] 端到端 E2E 全过
```

退出码 0=PASS / 1=FAIL。

## 5. 重新打包时机

| 场景 | 是否需要重打 |
|---|---|
| 改 UI / 业务代码 | ✅ 必打 |
| 改 `requirements.txt` | ✅ 必打 |
| 改 `.env.template` | ❌ 用户自己复制 |
| 改 docs | ❌ |
| 模型有更新 | ❌ 单独拷 .dat 到 `dist/attendance-system/models/` |

## 6. W5 范围外

- **代码签名**：`attendance-system.exe` 没数字签名，Windows SmartScreen 可能弹"未知发布者"。**点"仍要运行"即可**。生产可考虑购买签名证书。
- **安装包 (NSIS / Inno Setup)**：当前只交付 onedir 目录，没做 .msi / .exe 安装包。Phase 5+ 可加。
- **自动更新**：无。每次更新都重打 + 用户重拷。
- **Mac / Linux**：当前 spec 只打了 Windows 平台。Mac/Linux 需另写 spec。
