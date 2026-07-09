# 老师 / 验收人快速清单（10 步跳完能走）

> 验收人视角的精简版。5-10 分钟内能验证项目能跑 + 主要功能完整。
> 完整版见 [docs/TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) / [docs/HANDOFF.md](HANDOFF.md)。

## 验收前 5 分钟（环境检查）

```powershell
# 0. 工具
python --version         # 期望: Python 3.13.6 或 3.13.9
mysql --version          # 期望: mysql  Ver 8.0.x
git --version            # 任意

# 1. 装依赖（3-5 分钟, dlib-bin 100MB 占大头）
cd 项目根目录
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# 期望: 15 个包全装好 (PyQt5 / SQLAlchemy / dlib-bin / qrcode / fastapi / ...)

# 2. 配 .env
Copy-Item .env.template .env
notepad .env             # 改 DB_PASSWORD=你的MySQL密码

# 3. 建库（一键梭 14 张表）
python scripts\init_db.py
# 期望: 3 个 [OK] (schema.sql + migration_w13.sql + migration_w14.sql)
```

## 验收 10 步

| # | 步骤 | 命令 / 操作 | 期望 |
|---|---|---|---|
| 1 | **跑测试** | `pytest tests/ -q` | **219 passed in ~67s 3 warning** |
| 2 | **跑 smoke** | `python scripts\smoke_full_flow.py` | OK, ~30s |
| 3 | **启动 GUI** | `python -m src.main` | 登录窗口弹出, `app.log` 有"dlib 模型路径 OK" |
| 4 | **刷脸签到** | 学生 test001 录人脸 → 教师 teacher01 发起任务 → 学生刷脸 | attendance_record 多 1 行 signin_method='face' |
| 5 | **数字码签到** | 教师点"🎲 数字签到" → 弹 4 位码 → 学生敲码 | attendance_record 多 1 行 signin_method='digit' |
| 6 | **二维码签到** | 教师点"📱 二维码签到" → 弹二维码 → 学生摄像头扫 | attendance_record 多 1 行 signin_method='qr' |
| 7 | **手机扫码 H5** | 教师点二维码签到 → 记下弹窗里的 URL → **手机浏览器**打开 | H5 页面渲染, 输 test005/123456 提交 → 教师端列表多 1 行 |
| 8 | **关闭任务** | 教师点"结束选中任务" → 确认 | 没签到的学生自动 absent, 请过假的变 leave |
| 9 | **看报表** | 教师端「统计报表」Tab + 管理员端「使用率报表」Tab | matplotlib 4 类图表渲染 |
| 10 | **打 exe** | `pyinstaller build.spec` (~5 分钟) | `dist/attendance-system/attendance-system.exe` 15 MB, 同级 models/ + .env.template 都在 |

## 通过标准

- [ ] 第 1-3 步全过（环境 + 启动 OK）
- [ ] 第 4-6 步 attendance_record 至少 3 行不同 signin_method
- [ ] 第 7 步手机扫码能进 H5（**第一次会弹 Windows 防火墙, 点允许**）
- [ ] 第 8 步自动缺勤逻辑正确
- [ ] 第 9 步图表能渲染（无空白 / 无错误）
- [ ] 第 10 步打包成功, 双击 exe 能起

**全部勾上 = 通过验收**。

## 1 分钟故障速查（验收时遇到问题先看这）

| 现象 | 原因 | 修法 |
|---|---|---|
| `pip install dlib-bin` 失败 | Python 不是 3.13 / 没 pip | 重装 Python 3.13 + `python -m pip install --upgrade pip` |
| 启动弹"找不到 .env" | 没复制模板 | `Copy-Item .env.template .env` |
| 启动弹"无法连接数据库" | MySQL 没启 / 密码错 | `net start mysql` + 改 .env |
| 教师点数字码/二维码签到报错 | migration_w13 没跑 | `python scripts\init_db.py` 重跑 |
| **手机扫码连不上** | Windows 防火墙阻止 | 弹防火墙时勾"专用+公用"+允许; 或跑 `New-NetFirewallRule -DisplayName "AttendanceSigninWeb" -Direction Inbound -LocalPort 5180 -Protocol TCP -Action Allow` (管理员 PowerShell) |
| **手机扫码后 URL 是 127.0.0.1** | 教师电脑网络出不去, get_lan_ip 兜底失败 | 教师电脑连能访问阿里 DNS (223.5.5.5) 的网络重试; 或重启 `python -m src.main` |
| pytest 报"Access denied" | DB_PASSWORD 错 | 改 .env |
| pytest 报"Table doesn't exist" | 没跑 init_db.py | `python scripts\init_db.py` |
| PyInstaller 报"hidden import" | 漏列 service | 已在 `build.spec` 列出 13 个, 不该出问题; 若仍有问题直接清缓存 `pyinstaller --clean build.spec` + 重装依赖 |
| 摄像头打不开 | 隐私设置 / 被占用 | 关 QQ/微信/Zoom, 设置→隐私→摄像头→允许桌面应用 |

## 5 分钟能看完的"为什么这个项目通过验收"

1. **14 张表 + 19 FK + UNIQUE 约束** — 完整的数据建模, 不是 demo 级
2. **3 种签到方式 + W14 多端登录** — 不是只刷脸, 是 4 种签到场景全覆盖
3. **219 单元 + 10 smoke 端到端** — 自动化测试覆盖, 不是只跑通
4. **6 次 bug 审计 + 跨机可行性体检** — 不是写完就交付, 反复修过
5. **380 MB onedir 打包** — 真一键 exe, 不是只能 dev 跑
6. **完整文档** (29 篇 .md) — 任何接手的人都能看懂, 不靠口口相传

**项目收尾 2026-06-17, 验收日 2026-06-20, 3 天缓冲。**
