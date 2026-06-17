# 项目交接手册（HANDOFF）

> **这是项目交付的"总入口"**。任何接手这个项目的人（组员 / 老师 / 答辩评委 / 半年后的自己）**先读这一篇**，再按需跳到其它文档。
>
> 写于 W15+ 收尾，**全部跨机可行性 bug 已修**（commit 2c2fd10）。

## 1. 30 秒总览

| 维度 | 数据 |
|---|---|
| **项目名** | 智能考勤与实验室准入系统 |
| **课程** | 深圳技术大学「数据库原理」课程设计 |
| **作者** | (课程组, 见 `git log`) |
| **截止** | 2026-06-20（验收日） |
| **栈** | Python 3.13.6/3.13.9 + PyQt5 5.15 + MySQL 8.0.29+ + dlib-bin 20.0.1 + SQLAlchemy 2.0 |
| **架构** | 4 层 (ui → service → dao → model) + utils |
| **数据** | **14 张表** (schema.sql 12 + migration_w13.sql 1 + migration_w14.sql 1) |
| **代码** | **107 个 .py** / 6 service / 14 widget / 4 主窗口 |
| **测试** | **188 单元 / 8 smoke 端到端**（全过 ~55s） |
| **打包** | PyInstaller onedir **~380 MB** |
| **3 种签到** | 刷脸 (dlib 距离匹配) / 数字码 (对分易式 60s 倒计时) / 二维码 (base64 token) |
| **W14+ 新功能** | FastAPI 嵌入 + H5 签到页 (手机扫码 → 浏览器 → 教师端实时反馈) |
| **迭代** | W2 → W15+, 共 14 周, 73 commit, 5 次 bug 审计 + 跨机可行性体检 |

## 2. 你应该读哪一篇？

| 你是谁 | 读这篇 | 重点看什么 |
|---|---|---|
| **课程组员**（在自己电脑跑） | [docs/TEAM_SETUP.md](TEAM_SETUP.md) | 0-5 步上手 + 防火墙 + 故障排除 |
| **老师 / 验收人**（5 分钟看完） | 本文档 § 6「10 步验收」 | 每个勾打上即可 |
| **答辩演示人**（录视频 + 答辩） | [docs/TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) + [docs/DEMO_RECORDING.md](DEMO_RECORDING.md) | 10 步 + 录屏脚本 |
| **半年后的自己**（接手维护） | 本文档 + [CLAUDE.md](../CLAUDE.md) + [docs/ARCHITECTURE.md](ARCHITECTURE.md) | 仓库结构 + 4 层依赖 |
| **想跑通 188 项测试** | [docs/SMOKE_TESTS.md](SMOKE_TESTS.md) | 8 个 smoke 命令 |
| **想打 .exe** | [docs/PACKAGING.md](PACKAGING.md) | onedir 模式说明 |

## 3. 仓库结构（一图看全）

```
Attendance-Management-system-using-face-recognition/  ← 你解压后看到的
├── README.md                      ← 项目门面 (5 分钟看完)
├── QUICKSTART.md                  ← 5 分钟跑通 (跟 README 互补)
├── CLAUDE.md                      ← 给 AI agent 的项目说明 (架构 + 决策 + 坑)
├── LICENSE                        ← MIT
├── requirements.txt               ← 15 个依赖 (PyQt5 + SQLAlchemy + dlib-bin + qrcode + ...)
├── .env.template                  ← .env 模板 (组员复制改名后填 DB_PASSWORD)
├── build.spec                     ← PyInstaller 打包配置
├── start.bat / kill_all_python.bat ← Windows 启动 / 多 GUI 清理
│
├── src/                           ← **核心代码** (4 层架构)
│   ├── main.py                    ← 应用入口 (python -m src.main)
│   ├── config.py                  ← 全局配置 (读 .env)
│   ├── db.py                      ← SQLAlchemy engine + session_scope
│   ├── ui/                        ← PyQt5 窗口 (4 主窗口 + 13 widget)
│   │   ├── login_window.py        ← 登录 (3 角色路由)
│   │   ├── register_window.py     ← 注册
│   │   ├── student_window.py      ← 学生端 (4 Tab: 人脸注册/签到/考勤/请假)
│   │   ├── teacher_window.py      ← 教师端 (4 Tab: 发起考勤/历史/统计/账号)
│   │   ├── admin_window.py        ← 管理员端 (5 Tab: 实验室/培训/准入日志/报表/人脸)
│   │   ├── styles.py              ← 全局 QSS + design tokens
│   │   └── widgets/                ← 13 子控件
│   ├── services/                  ← 业务逻辑 (6 个)
│   │   ├── auth_service.py        ← 注册/登录/改密
│   │   ├── attendance_service.py  ← 3 种签到方式统一公共核 (_create_record)
│   │   ├── face_service.py        ← 人脸识别 + 采集
│   │   ├── lab_access_service.py  ← 实验室准入 7 分支
│   │   ├── leave_service.py       ← 请假申请/审批
│   │   ├── report_service.py      ← 4 类统计报表
│   │   └── signin_web.py          ← W14 FastAPI 嵌入 (H5 签到)
│   ├── dao/                       ← SQLAlchemy 数据访问 (12 个)
│   ├── models/                    ← ORM 模型 (8 个, 4 张表无 ORM 走纯 SQL)
│   └── utils/                     ← 工具层
│       ├── crypto.py              ← bcrypt 哈希
│       ├── face_helper.py         ← dlib 4 核心 API (face_locations/encodings/distance/compare_faces)
│       ├── charts.py              ← matplotlib 4 类图表
│       ├── paths.py               ← APP_ROOT 单例 (PyInstaller 兼容)
│       └── network.py             ← LAN IP 探测 (W15+ 改阿里 DNS)
│
├── db/                            ← **数据库 DDL**
│   ├── schema.sql                 ← 12 张表 baseline
│   ├── migration_w13.sql          ← W13+ (task_signin_code + signin_method)
│   └── migration_w14.sql          ← W14+ (course_teacher 多对多)
│
├── docs/                          ← **完整文档** (这一篇就是入口)
│   ├── HANDOFF.md                 ← 你正在读
│   ├── TEAM_SETUP.md              ← 组员跨机上手 9 步
│   ├── TESTING_CHECKLIST.md       ← 10 步亲自测试 + 故障速查
│   ├── ARCHITECTURE.md            ← 4 层依赖图 + 数据流
│   ├── DATABASE.md                ← 14 张表设计
│   ├── WORKFLOWS.md               ← 业务流程 (考勤/准入/请假)
│   ├── DEVELOPMENT.md             ← 开发者 30 分钟上手
│   ├── PACKAGING.md               ← PyInstaller 打包
│   ├── SMOKE_TESTS.md             ← 8 smoke 端到端
│   ├── SIGNIN_METHODS.md          ← 3 种签到方式详细说明
│   ├── MANUAL_E2E.md              ← 端到端手测
│   ├── DEMO_RECORDING.md           ← 演示视频录制脚本
│   ├── RECORD_QUICKSTART.md       ← 录屏 5 分钟速成
│   ├── RECORD_STEP_BY_STEP.md     ← 录屏分步脚本
│   ├── demo_narration.md / .srt   ← 演示旁白文稿
│   ├── CHANGELOG.md               ← 版本变更
│   ├── TODO.md                    ← 后续待办
│   ├── W14-defense-outline.md     ← 答辩提纲
│   └── superpowers/plans/         ← 5 份 W3-W14 实施计划
│
├── scripts/                       ← **运维 + 烟测** (12 个)
│   ├── init_db.py                 ← ⭐ 一键建 14 张表 (跨机适配修过)
│   ├── run_dev.sh / .bat          ← 开发模式启动
│   ├── seed_demo_data.py          ← 演示数据 seed
│   ├── cleanup_test_users.py      ← 清理测试用户
│   ├── smoke_*.py                 ← 7 个端到端烟测
│   └── import_schedule.py         ← 课表导入 (W14+)
│
├── tests/                         ← **单元测试** (188 项, pytest)
│   ├── conftest.py                ← session 级自动清理 fixture
│   ├── test_*.py                  ← 按模块覆盖
│
├── models/                        ← dlib 模型 (git ignore, 运行时下载 ~120MB)
├── dataset/                       ← 人脸采集图 (git ignore, 运行时生成)
├── dist/                          ← PyInstaller 产物 (git ignore, ~400MB)
├── build/                         ← PyInstaller 中间产物 (git ignore)
├── .venv/                         ← Python 虚拟环境 (git ignore)
├── .opencode/ / .mavis/ / .worktrees/  ← Mavis 工具缓存 (git ignore)
└── backups/                       ← 临时数据库备份 (git ignore)
```

## 4. 3 步上手（任何人）

```powershell
# 1. 配 .env (改 DB_PASSWORD)
Copy-Item .env.template .env
notepad .env

# 2. 建库 + 装依赖
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\init_db.py          # 一键建 14 张表

# 3. 启动 GUI
python -m src.main
# 首次会: 下 dlib 模型 + 弹 Windows 防火墙(点"允许")+ 弹登录窗口
```

详细见 [docs/TEAM_SETUP.md](TEAM_SETUP.md)。

## 5. 关键决策（不要推翻）

| 决策 | 原因 |
|---|---|
| `dlib-bin==20.0.1` 而非源码编译 | Python 3.13 + Windows 上 cmake 编译坑多；`dlib-bin` 是预编译 wheel |
| 不依赖 `face_recognition` 库 | 1.3.0 在 cp313 上无 wheel；自写 `src/utils/face_helper.py` 4 核心 API |
| `dlib` 模型不入 git | 单文件 95 MB 接近 GitHub 100 MB 警告线；首次运行时下载 |
| bcrypt 而非明文 | 课程要求"密码不能明文" |
| SQLAlchemy 2.0 ORM | 防 SQL 注入 + 跨数据库可移植（演示可一键切 SQLite） |
| `face encoding` 统一 `np.float32` | 序列化/比对链路不会再因量纲不一致出错，有 `test_face_encodings_dtype_is_float32` 锁住 |
| PyQt5 而非 Tkinter | 控件丰富，4 个主窗口有大量表格 + 表单 |
| `src/utils/paths.py::APP_ROOT` 单例 | dev 走 `Path(__file__).resolve().parent.parent.parent`；打包后走 `Path(sys.executable).resolve().parent` |
| W14 FastAPI 嵌入 PyQt 进程（不独立跑） | 独立 uvicorn 进程需要管端口/启停/跟 GUI 生命周期对齐；改用 `uvicorn.Server` + `threading.Thread(daemon=True)` |

## 6. 10 步验收（老师 / 评委用）

> 每步预期都有明确标志。**所有勾打上 = 通过**。

| # | 步骤 | 预期 | 通过 |
|---|---|---|---|
| 0 | **环境**: Python 3.13.6/3.13.9 + MySQL 8.0.29+ 装好 | `python --version` + `mysql --version` | ☐ |
| 1 | `pip install -r requirements.txt` | 15 个包全装好（PyQt5 + dlib-bin + ...） | ☐ |
| 2 | `python scripts/init_db.py` | 3 个 SQL 全跑通, 14 张表建好 | ☐ |
| 3 | `python -m src.main` 启动 GUI | 登录窗口弹出, `app.log` 有"dlib 模型路径 OK" | ☐ |
| 4 | **刷脸签到**: 学生采集人脸 → 教师发起任务 → 学生刷脸 | attendance_record 多一行 signin_method='face' | ☐ |
| 5 | **数字码签到**: 教师弹码 → 学生敲 4 位 → 出勤 | attendance_record 多一行 signin_method='digit' | ☐ |
| 6 | **二维码签到**: 教师弹码 → 学生扫 → 出勤 | attendance_record 多一行 signin_method='qr' | ☐ |
| 7 | **手机扫码 H5**: 教师点"二维码签到" → 手机浏览器打开 H5 → 提交 | attendance_record 多一行 signin_method='qr' (从手机来) | ☐ |
| 8 | **关闭任务**: 教师点"结束选中任务" | 没签到的学生自动 absent, 请过假的变 leave | ☐ |
| 9 | **自动化测试**: `pytest tests/ -q` | 188 passed in ~55s | ☐ |

详细手机扫码步骤 + 防火墙授权 + 故障排除见 [docs/TESTING_CHECKLIST.md](TESTING_CHECKLIST.md)。

## 7. 仓库统计（交付时）

| 指标 | 数据 |
|---|---|
| Git commit 数 | 73 (W2 → W15+) |
| 入库文件数 | 147 (107 .py + 23 .md + 5 .sql + 12 .bat/.spec/.template) |
| 入库代码大小 | ~970 KB (压缩后 ~400 KB) |
| 测试覆盖 | 188 单元 / 8 smoke 端到端 / 0 warning（除 7 个第三方库 deprecation） |
| 迭代周数 | 14 周 (W2 / W3 / W4 / W5 / W6 / W7 / W8 / W9 / W10 / W11 / W12 / W13+ / W14 / W15+) |
| Bug 审计次数 | 5 次 (W7/W8/W9/W10/W11) + W12 P0 验收 + W14 收尾 + W15+ 跨机可行性 |
| 跨机可行性 P0 数 | 0 (4 修 + 5 P1 修 + 3 改进) |

## 8. 已知约束（项目层面接受，不动）

- `LabAccessService.check_access` / `LeaveService.list_pending_for_task` 是 service 公开 API 但 UI 没调 — W4/W6 设计如此，docstring 写明给"门口刷脸机"扩展
- `_FaceCache` 单例 dict 读写 race — N<1000 + GIL，W4 接受
- `FaceEncodingDao.set_primary` 2 次 update 中间可能短暂不一致 — W3 接受
- `FaceEncoding` 用 SQLAlchemy `SmallInteger` 而非 SQL `TINYINT(1)` — ORM 工具可能误判 schema drift，不影响业务
- `dlib` 模型首次下载 5-10 分钟（120MB 联网）— 仅首次
- `signin_web` watchdog 6 次连续失败才重建（30s 容错，避免网络抖动误判）

## 9. 跨机可行性

| 维度 | 状态 |
|---|---|
| Python 版本 | **3.13.6 / 3.13.9** (项目代码用 PEP 604 `X \| None` 需 3.10+) |
| MySQL 版本 | **8.0.29+** (migration 用 `IF NOT EXISTS` 语法) |
| 路径硬编码 | **0 个** (所有路径走 `APP_ROOT` 单例 + `Path(__file__).resolve()`) |
| 平台特定代码 | **0 个** (0 pywin32, 0 sys.platform, 0 shell=True) |
| 防火墙授权 | **首次必弹** (W14 H5 监听 0.0.0.0:5180) |
| 国内网络 | **阿里 DNS 兜底** (get_lan_ip 改 223.5.5.5) |
| dlib 模型下载 | **gitee 镜像兜底** (GitHub raw 被墙时自动试镜像) |
| 端口冲突 | **重试 5 次** (5180-5184, 全失败才放弃) |

## 10. 给接手维护的人

**半年后你接手这个项目，建议这样**:

1. **先读 [CLAUDE.md](../CLAUDE.md)** — 3 分钟了解架构 + 决策 + 坑
2. **跑 `pytest tests/ -q`** — 5 分钟验证环境
3. **跑 8 个 smoke** — 10 分钟验证业务流
4. **看 [docs/ARCHITECTURE.md](ARCHITECTURE.md)** — 30 分钟理解 4 层依赖
5. **看 [docs/superpowers/plans/](superpowers/plans/)** — 5 份 W3-W14 实施计划，看迭代过程
6. **改任何代码前先跑测试** — 188 项测试覆盖了主要业务流

**如果遇到"代码改完测试挂了"**:
- 先看 `git log -p` 最近几个 commit 的 diff
- 再看 [docs/CHANGELOG.md](CHANGELOG.md) 版本变更
- 必要时 `git revert <hash>` 回到上个稳定状态

**如果遇到"代码改完打包挂了"**:
- 跑 `pyinstaller --clean build.spec` 清缓存
- 跑 `pip install -r requirements.txt --upgrade --force-reinstall` 重装依赖
- 看 [docs/PACKAGING.md](PACKAGING.md)

---

**有任何问题**：先翻 [docs/TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) 故障速查 + [docs/TEAM_SETUP.md](TEAM_SETUP.md) 故障排除。  
**还不行就 git log 看最近 commit**。  
**还不行就回滚到上一个稳定 commit**。

—— 项目收尾 ✨
