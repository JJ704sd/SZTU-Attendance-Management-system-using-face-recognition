# Changelog

所有重要变更都会记录在此文件。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## W14 (2026-06-16) — 多端登录签到

### 新增
- **FastAPI 嵌入到 PyQt 进程，提供 H5 签到页**：学生用手机扫码 → 浏览器打开签到页 → 输入学号密码 → 签到成功，教师端实时反馈
- **教师端弹「二维码签到」时起 :5180 端口**（默认端口由 `SIGNIN_WEB_PORT` 控制，冲突时自动 +1 重试 1 次）
- **`src/services/signin_web.py::SigninWebServer`**：封装 `uvicorn.Server` 在 `threading.Thread(daemon=True)` 内跑，关闭/退出时 `should_exit=True` 同步停
- **`src/ui/web_templates/signin.html`**：H5 签到表单（Jinja2 模板）
- **`src/utils/network.py::get_lan_ip()`**：自动探本机局域网 IP（socket connect / 解析路由表）
- **`scripts/smoke_signin_web.py`**：9 步端到端烟测（注册 → task → qr 码 → server 启停 → 签到页 → POST 签到 → DB 验证 → status 轮询 → 端口释放 → cleanup）
- **`scripts/smoke_signin_web_build.py`**：烟测 exe 是否包含 fastapi/uvicorn/starlette/jinja2/httpx 模块（防 PyInstaller hiddenimports 漏配）
- **`scripts/prepare_deliverable_zip.py`**：课程交付物 zip 打包脚本（输出 `dist/deliverable-2026-06-20.zip`，排除 `.env` / `.venv` / `dist` / 个人报告 / 课程要求 PDF）
- **`docs/W14-defense-outline.md`**：答辩 PPT 大纲（15 页）+ 截图需求清单

### 改动
- **`requirements.txt`**：+4 行（`fastapi==0.115.0` / `uvicorn==0.32.0` / `jinja2==3.1.4` / `httpx==0.27.2`）
- **`build.spec`**：+14 hiddenimports（`fastapi.*` / `uvicorn.*` / `starlette.*` / `jinja2` / `httpx._*`）+ 项目内 3 个新 service/utility module 兜底
- **打包体积**：385 → 396 MB（+10 MB，含 FastAPI/uvicorn/jinja2/pydantic/websockets）
- **`src/ui/signin_code_dialog.py`**：二维码内容改为完整 URL（`http://<lan_ip>:<port>/signin/<task>/<token>`），弹窗新增「实时签到列表」+ QTimer 2 秒 polling `/api/signin/status`
- **`src/ui/teacher_window.py`**：发起考勤 Tab 新增「📱 二维码签到」按钮
- **`src/services/attendance_service.py`**：复用 `sign_in_by_qr()` 走 W14 H5 签到链路（业务核零改动）
- **`src/db/schema.sql` + `db/migration_w13.sql`**：13 张表（无新表，复用 `task_signin_code`）
- **`CLAUDE.md`**：「关键技术决策」表追加 2 行（FastAPI 嵌入 / 二维码内容=URL）+ 常用命令追加 smoke 脚本 + 当前进度追加 W14

### 测试
- **179/179** 单元测试全过（含 1 项 dtype 回归 + 1 项 collect_for_user 死循环回归 + W12 新增 18 项 + W13+ 新增 18 项 + W14 新增 11 项 signin_web + 10 项 UI 现代化 + 5 项 task_signin_code_dao）
- **Smoke 全过**：
  - `smoke_full_flow.py`（9 步业务流）
  - `smoke_signin_web.py`（9 步 W14 全链路）
  - `smoke_qrcode_build.py`（防 qrcode hiddenimports 漏配）
  - `smoke_signin_web_build.py`（防 FastAPI hiddenimports 漏配）

### 已知问题
- FastAPI 嵌入进程内 uvicorn 占用 :5180，演示时**需要确保端口未被占用**（`SigninWebServer.start()` 已做 +1 重试）
- H5 签到页只在**教师电脑同一局域网内**有效（演示场景，不暴露公网）
- dlib 模型首次运行时下载约 120 MB（断网会失败）

---

## W13+ (2026-06-15) — 数字码 + 二维码签到

### 新增
- **`task_signin_code` 表**（W13+ 新表）：存数字码/二维码 token + TTL
- **`attendance_record.signin_method` 字段**：`face` / `digit` / `qr`
- **`scripts/smoke_signin_methods.py`**：5 步烟测（face/digit/qr 三种签到方式）
- **`docs/SIGNIN_METHODS.md`**：签到方式完整文档（操作手册 + 对比表）

### 改动
- **`src/services/attendance_service.py`**：新增 `generate_signin_code()` / `sign_in_by_digit()` / `sign_in_by_qr()`
- **`src/ui/signin_code_dialog.py`**：教师端弹窗生成 4 位数字码 / 二维码
- **`src/ui/widgets/digit_signin_widget.py` / `qr_scan_widget.py`**：学生端输入码 / 扫二维码

### 测试
- **新增 18 项** signin_methods 测试
- **5 个 smoke** 脚本全过

---

## W12 (2026-06-07) — P0 验收修复 + 业务功能

### 新增
- **管理员端人脸管理**（`src/ui/widgets/face_admin_tab.py`）：管理员可查看/重置所有人脸
- **学生端清自己人脸**（`src/ui/widgets/face_collect_dialog.py`）

### 修复（12 真 bug）
- 注册密码长度校验
- `sign_in_time` 为 NULL 时报表崩溃
- `attendance_record` 缺勤补齐时 student_id NULL
- `login_attempt` 锁定计数逻辑
- 详见 `docs/superpowers/plans/2026-06-07-W12-p0-fixes-and-deliverables.md`

### 测试
- **新增 18 项** camera / admin_tab 单元测试

---

## 早期版本 (W2-W11)

详见 git log：`git log --oneline | head -50`
- **W2**：登录注册、教师端 4 tab + 10 张表 + 3 角色
- **W3**：人脸识别全链路
- **W4**：实验室准入 7 分支 + 安全培训 + 4 类图表
- **W5**：PyInstaller onedir 一键 exe
- **W6**：请假流程
- **W7**：完整 bug 审计
- **W8-W11**：资源泄漏、字段校验、类型转换等