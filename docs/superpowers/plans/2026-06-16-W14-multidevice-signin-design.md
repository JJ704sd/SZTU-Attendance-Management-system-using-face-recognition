# W14 多端登录签到 — 设计稿（待评审）

> **截止日**: 2026-06-20 课程交付  
> **作者**: Mavis (W14 评审待用户确认)  
> **状态**: 设计稿 v1，待用户拍板后进入实现阶段  
> **本计划配套**: `2026-06-07-W12-p0-fixes-and-deliverables.md`（课程交付总纲）

---

## 0. 一句话目标

教师端点「📱 二维码签到」后，**学生用自己手机扫屏幕上的二维码 → 手机浏览器打开 H5 签到页 → 输入学号+密码 → 签到成功，教师端实时看到「✓ 张三 已签到」**。

整个流程 2 秒内完成，无需安装任何额外 App，仅在演示用的局域网内有效（不暴露公网）。

---

## 1. 背景与动机

### 1.1 现状（W13+ 已有）
- 教师端 `SigninCodeDialog` 弹窗生成二维码，**二维码内容 = 22 字符 base64 token**（裸 token）
- 学生端 `QrScanWidget` 用电脑摄像头扫这个码，扫到后调 `attendance_service.sign_in_by_qr(task_id, user_id, token)` 完成签到
- **痛点**：必须用**教师那台电脑**（摄像头）扫码，演示时学生没有电脑就只能看着

### 1.2 W14 要解决的
- 学生**没带电脑**或**不想用电脑**场景（实际课堂里常见）
- 答辩加分项：教师演示「手机真扫码 + 实时反馈」，区别于"刷脸 demo"的另一条交互线
- 完全复用已有 `sign_in_by_qr` service 接口，**不动业务核**

---

## 2. 方案对比（为什么选 FastAPI 嵌入）

| 方案 | 优点 | 缺点 | 推荐 |
|---|---|---|---|
| **A. FastAPI 嵌入 + H5 页** | 服务端只 bind 局域网，演示完即关；H5 复用现有 `sign_in_by_qr`；UI 用 PyQt 写也能复用样式工具 | 多 1 个 QThread；多 ~10 MB 依赖 | ✅ **强推** |
| B. `http.server` 手写路由 | 0 依赖 | 路由/SSE/H5 模板全手写，答辩翻车成本高 | ❌ |
| C. 第三方（微信扫码 / 钉钉小程序） | 体验好 | 需要企业认证、域名、备案 → 课程作业完全不值得 | ❌ |
| D. 完全不加，纯靠教师喊学号 | 最简单 | 答辩无法体现"多端登录"差异化 | ❌ |

**选 A 的核心理由**：复用 1.1 节已建好的 service 链路，FastAPI 只做「HTTP 适配层」，业务核零改动。

---

## 3. 端到端数据流

### 3.1 时序图（ASCII）

```
[教师 PyQt]                [本地 FastAPI :5180]              [学生手机浏览器]
    │                              │                                │
    │ 1. 点「二维码签到」           │                                │
    │    → SigninCodeDialog.show() │                                │
    │ 2. attendance_service        │                                │
    │    .generate_signin_code(    │                                │
    │      task_id, 'qr')          │                                │
    │    → {token, expires_at}     │                                │
    │ 3. _render_code(             │                                │
    │      url=                    │                                │
    │      "http://192.168.x.x:    │                                │
    │       5180/signin/<task>/    │                                │
    │       <token>")              │                                │
    │    → qrcode.make(url)        │                                │
    │ 4. QThread 启动 uvicorn      │                                │
    │    .Server.serve()           │                                │
    │                              │                                │
    │                              │ 5. 学生微信/相机扫码            │
    │                              │    → GET /signin/<task>/<token>│
    │                              │    → 渲染 H5 签到页            │
    │                              │                                │
    │                              │ 6. 学生提交学号+密码            │
    │                              │   ← POST /api/signin           │
    │                              │      {student_id, password}    │
    │                              │                                │
    │                              │ 7. auth_service.login(         │
    │                              │       username_or_id, password)│
    │                              │ 8. attendance_service          │
    │                              │    .sign_in_by_qr(             │
    │                              │       task_id, user_id, token) │
    │                              │                                │
    │                              │ 9. 返回 {ok:true, status:      │
    │                              │       "present/late",          │
    │                              │       student_name:"张三"}     │
    │                              │ ──────────────────────────────→│
    │                              │                                │ 10. H5 显示
    │                              │                                │   「✓ 张三
    │                              │                                │   签到成功」
    │                              │                                │
    │ 11. 教师端 QTimer 每 2 秒    │                                │
    │     GET /api/status?task=N   │                                │
    │   ← {new_records: [...]}     │                                │
    │ 12. 教师端弹窗「实时签到列表」│                                │
    │     顶部追加「✓ 张三 18:09」 │                                │
    │                              │                                │
    │ 13. 教师关弹窗                │                                │
    │ 14. uvicorn.Server.shutdown()│                                │
    │     → :5180 释放             │                                │
```

### 3.2 关键时序说明

| # | 关键决策 | 备注 |
|---|---|---|
| 2 | 复用 `generate_signin_code` | 已存在，token 写库 `task_signin_code` 表，TTL 60s |
| 3 | **二维码内容 = URL，不是裸 token** | 旧版是 `qrcode.make(token)`，新版是 `qrcode.make(url)` |
| 4 | uvicorn 跑在 QThread | 阻塞 `serve()` 不挂 Qt 事件循环 |
| 5-6 | 学生输学号+密码 | **不靠 IP/User-Agent 识别**（安全） |
| 7 | 复用 `auth_service.login` | bcrypt 校验 + 失败次数拦截，**5 次错就锁账号**（与 PyQt 登录同策略） |
| 8 | 复用 `sign_in_by_qr` | 业务核零改动，签到记录里 `signin_method='qr'` 与旧路径一致 |
| 11-12 | 教师端 **轮询** `/api/status` | 简单可靠；SSE/WebSocket 收益小、复杂度高，**用轮询足够** |
| 14 | 关弹窗即关服务 | 演示结束无残留进程，无端口泄漏 |

---

## 4. API 契约

### 4.1 路由总览

| Method | Path | 说明 |
|---|---|---|
| GET  | `/signin/{task_id}/{token}`            | H5 签到页（HTML） |
| GET  | `/api/signin/info?task={task_id}`       | H5 页加载时调，拿任务名/教师名/课程名展示 |
| POST | `/api/signin`                            | 学生提交学号+密码+token |
| GET  | `/api/signin/status?task={task_id}&since={ts}` | 教师端轮询新签到 |
| GET  | `/api/health`                            | 教师端心跳 |

### 4.2 POST /api/signin 请求体

```json
{
  "task_id": 42,
  "token":   "abc123XYZ-_22charBase64",   // 来自 URL
  "student_id":  "2021001",               // 学号 (或 username)
  "password":    "123456"
}
```

### 4.3 POST /api/signin 响应

```json
// 200 成功
{
  "ok": true,
  "status": "present",   // or "late"
  "student_name": "张三",
  "signin_method": "qr",
  "sign_in_time": "2026-06-16T18:09:33"
}

// 4xx 业务错误（HTTP code + body 都给）
400 {"ok": false, "error": "CODE_INVALID",   "msg": "签到码无效或已过期"}
400 {"ok": false, "error": "CODE_FORMAT",    "msg": "签到码格式错误"}
401 {"ok": false, "error": "AUTH_FAILED",    "msg": "学号或密码错误"}
403 {"ok": false, "error": "ACCOUNT_LOCKED", "msg": "账号已锁定，请联系管理员"}
404 {"ok": false, "error": "TASK_NOT_FOUND", "msg": "考勤任务不存在"}
409 {"ok": false, "error": "ALREADY_SIGNED", "msg": "已签到"}
500 {"ok": false, "error": "INTERNAL",       "msg": "服务异常"}
```

### 4.4 GET /api/signin/status 响应

```json
{
  "ok": true,
  "new_records": [
    {
      "student_name": "张三",
      "status":       "present",
      "sign_in_time": "2026-06-16T18:09:33",
      "signin_method": "qr"
    }
  ]
}
```

教师端用 `(task_id, last_ts)` 做增量轮询 → 减少数据传输。

### 4.5 GET /signin/{task_id}/{token} 响应

返回渲染好的 H5 签到页（HTML），约 80 行，含：
- 顶部 logo + 课程/教师信息
- 表单（学号 + 密码 + 「立即签到」按钮）
- 提交后展示成功/失败反馈
- 自动从 URL 拿 `task_id` + `token`

---

## 5. 文件改动清单（diff 概览）

### 5.1 新增（4 个文件）

#### `src/services/signin_web.py`（新，~180 行）
```python
"""
services/signin_web.py — 教师端「二维码签到」本地 HTTP 服务

W14 新增：在教师 PyQt 进程内嵌入 uvicorn + FastAPI，
供学生手机浏览器扫码后调用 /api/signin 完成签到。

核心原则：
  - 业务核零改动：路由 handler 全部复用
    auth_service.login + attendance_service.sign_in_by_qr
  - 生命周期与 SigninCodeDialog 绑定：
    show() → start()，closeEvent → stop()
  - 端口从 .env 读 SIGNIN_WEB_PORT（默认 5180），冲突时 +1
  - 只 bind 0.0.0.0:5180，不暴露公网（演示完即关）
"""
import logging
import threading
import socket
from typing import Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.services.auth_service import AuthService, AuthError
from src.services.attendance_service import AttendanceService
from src.config import Config
from src.utils.crypto import verify_password
from src.dao.user_dao import UserDao
from src.db import session_scope

log = logging.getLogger(__name__)


def _get_lan_ip() -> str:
    """探测本机局域网 IP（用于二维码 URL）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def build_signin_app(task_id: int, token: str, expires_at) -> FastAPI:
    """构造 FastAPI app，路由 handler 用闭包捕获 task_id/token。"""
    app = FastAPI(title="签到服务", docs_url=None, redoc_url=None)
    # templates 路径：src/ui/web_templates/
    templates = Jinja2Templates(directory=str(
        Path(__file__).resolve().parent.parent / "ui" / "web_templates"
    ))

    @app.get("/signin/{tid}/{tok}", response_class=HTMLResponse)
    async def signin_page(tid: int, tok: str, request: Request):
        if tid != task_id or tok != token:
            return HTMLResponse("<h1>签到码无效</h1>", status_code=400)
        return templates.TemplateResponse("signin.html", {
            "request":  request,
            "task_id":  task_id,
            "token":    token,
        })

    @app.post("/api/signin")
    async def api_signin(payload: dict):
        student_id = payload.get("student_id", "").strip()
        password   = payload.get("password", "")
        tid        = payload.get("task_id")
        tok        = payload.get("token", "")
        if not (student_id and password and tid == task_id and tok == token):
            raise HTTPException(400, "BAD_REQUEST")
        # 1) 验证 token 在 DB 中仍有效（DAO 层）
        # 2) auth_service.login(student_id, password) — 复用
        # 3) attendance_service.sign_in_by_qr(tid, user.id, tok) — 复用
        # 4) 返回 {ok, status, student_name}
        ...

    @app.get("/api/signin/status")
    async def api_status(task: int, since: Optional[str] = None):
        # 查 AttendanceRecord WHERE task_id=task AND sign_in_time > since
        # 返回 new_records
        ...

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    return app


class SigninWebServer:
    """在 QThread 内跑 uvicorn.Server 的封装。"""

    def __init__(self, task_id: int, token: str, expires_at,
                 host: str = "0.0.0.0",
                 port: Optional[int] = None):
        self.task_id   = task_id
        self.token     = token
        self.host      = host
        self.port      = port or Config.SIGNIN_WEB_PORT  # 默认 5180
        self._server   = self._build_server()
        self._thread   = None
        self.lan_ip    = _get_lan_ip()

    @property
    def url(self) -> str:
        return f"http://{self.lan_ip}:{self.port}/signin/{self.task_id}/{self.token}"

    def _build_server(self) -> uvicorn.Server:
        app = build_signin_app(self.task_id, self.token, None)
        cfg = uvicorn.Config(
            app, host=self.host, port=self.port,
            log_level="warning",   # 静音 uvicorn 默认 access log
            access_log=False,
        )
        return uvicorn.Server(cfg)

    def start(self):
        def run():
            try:
                self._server.run()
            except OSError as e:
                # 端口冲突 → +1 重试 1 次
                log.warning("端口 %s 冲突，尝试 %s", self.port, self.port + 1)
                self.port += 1
                self._server = self._build_server()
                self._server.run()
        self._thread = threading.Thread(target=run, daemon=True, name="signin-web")
        self._thread.start()

    def stop(self):
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=3)
```

#### `src/ui/web_templates/signin.html`（新，~100 行）
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>签到 - 智能考勤系统</title>
  <style>
    /* 简洁卡片式，移动端友好 */
    body { font-family: -apple-system, sans-serif; background: #F1F5F9;
           margin: 0; padding: 16px; min-height: 100vh;
           display: flex; align-items: center; justify-content: center; }
    .card { background: white; border-radius: 12px; padding: 24px;
            max-width: 360px; width: 100%; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    h1 { font-size: 18px; margin: 0 0 4px; color: #1E293B; }
    .sub { color: #64748B; font-size: 13px; margin-bottom: 20px; }
    input { width: 100%; padding: 12px; border: 1px solid #CBD5E1;
            border-radius: 8px; font-size: 16px; box-sizing: border-box;
            margin-bottom: 12px; }
    button { width: 100%; padding: 14px; background: #2563EB; color: white;
             border: 0; border-radius: 8px; font-size: 16px; font-weight: 600; }
    button:disabled { background: #94A3B8; }
    .result { margin-top: 16px; padding: 12px; border-radius: 8px;
              text-align: center; font-size: 15px; }
    .ok  { background: #DCFCE7; color: #166534; }
    .err { background: #FEE2E2; color: #991B1B; }
  </style>
</head>
<body>
  <div class="card">
    <h1>📚 智能考勤签到</h1>
    <div class="sub">任务 #{{ task_id }} - 请输入学号和密码</div>
    <form id="f">
      <input name="student_id" placeholder="学号" autocomplete="username" required>
      <input name="password"   type="password" placeholder="密码"
             autocomplete="current-password" required>
      <button type="submit">立即签到</button>
    </form>
    <div id="result"></div>
  </div>
  <script>
    const f = document.getElementById('f');
    const result = document.getElementById('result');
    f.onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(f);
      const btn = f.querySelector('button');
      btn.disabled = true;
      btn.textContent = '签到中…';
      try {
        const r = await fetch('/api/signin', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            task_id:    {{ task_id }},
            token:      '{{ token }}',
            student_id: fd.get('student_id'),
            password:   fd.get('password'),
          }),
        });
        const data = await r.json();
        if (data.ok) {
          result.className = 'result ok';
          result.textContent = '✓ ' + data.student_name + ' 签到成功';
        } else {
          result.className = 'result err';
          result.textContent = '✗ ' + (data.msg || '签到失败');
          btn.disabled = false;
          btn.textContent = '立即签到';
        }
      } catch (err) {
        result.className = 'result err';
        result.textContent = '✗ 网络异常，请重试';
        btn.disabled = false;
        btn.textContent = '立即签到';
      }
    };
  </script>
</body>
</html>
```

#### `src/utils/network.py`（新，~30 行）
```python
"""
utils/network.py — 网络工具（W14 新增）
- 探测本机局域网 IP（给二维码 URL 用）
- 探测端口是否被占用
"""
import socket


def get_lan_ip() -> str:
    """探测本机局域网 IP（启发式：连 8.8.8.8 不实际发包）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def is_port_free(port: int, host: str = "0.0.0.0") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()
```

#### `scripts/smoke_signin_web.py`（新，~120 行）
- smoke 测试：起 SigninWebServer → curl GET 签到页 → curl POST 签到 → 验 DB 有记录 → stop
- 集成到 pytest: `tests/test_signin_web.py::test_smoke_signin_web_round_trip`

### 5.2 修改（4 个文件）

#### `src/ui/widgets/signin_code_dialog.py`（改 ~50 行）

```python
# 改动 1: 构造签名加 web_server 参数（teacher_window 在 _on_open_signin_dialog 里建）
class SigninCodeDialog(QDialog):
    def __init__(self, parent, task_id: int, code_type: str,
                 teacher_window=None, web_server=None):
        ...
        self.web_server = web_server  # 由 teacher_window 传入

    def _render_code(self):
        ...
        else:  # qr
            if self.web_server is not None:
                # 新版：二维码内容 = URL
                display_value = self.web_server.url
            else:
                # 兜底：裸 token（防御性，向后兼容）
                display_value = self._code_value
            qr_img = qrcode.make(display_value).resize((250, 250))
            ...

    def closeEvent(self, event):
        """W14: 关弹窗时同步停 web server。"""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        # 新增
        if self.web_server is not None:
            try:
                self.web_server.stop()
                log.info("SigninWebServer 已停止")
            except Exception as e:
                log.exception("停 SigninWebServer 失败: %s", e)
        super().closeEvent(event)
```

#### `src/ui/teacher_window.py`（改 ~30 行）

```python
def _on_open_signin_dialog(self, code_type: str):
    task_id = self._get_open_task_id() or self._selected_task_id()
    if task_id is None:
        QMessageBox.warning(...)
        return

    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    from src.services.signin_web import SigninWebServer  # 新增

    # 仅 qr 类型启 web server（digit 不需要）
    web_server = None
    if code_type == "qr":
        # 先生成 token
        attendance = AttendanceService()
        result = attendance.generate_signin_code(task_id, "qr")
        if result is None:
            QMessageBox.warning(self, "生成失败", "请确认任务状态为 open")
            return
        # 起本地 HTTP 服务（端口冲突自动 +1）
        web_server = SigninWebServer(
            task_id=task_id,
            token=result["code"],
            expires_at=result["expires_at"],
        )
        web_server.start()
        # 设短轮询 timer 拉新签到
        self._poll_signin_status(task_id, web_server)

    self.signin_code_win = SigninCodeDialog(
        parent=self, task_id=task_id, code_type=code_type,
        teacher_window=self, web_server=web_server,
    )
    self.signin_code_win.exec_()

def _poll_signin_status(self, task_id: int, web_server):
    """每 2 秒轮询新签到，更新弹窗顶部「实时签到列表」。"""
    import requests  # 局部 import，FastAPI 同源
    timer = QTimer(self)
    timer.setInterval(2000)
    last_ts = None
    def tick():
        nonlocal last_ts
        try:
            r = requests.get(f"http://127.0.0.1:{web_server.port}/api/signin/status",
                             params={"task": task_id, "since": last_ts}, timeout=1)
            data = r.json()
            for rec in data.get("new_records", []):
                # 通知 signin_code_dialog 追加显示
                if self.signin_code_win:
                    self.signin_code_win.append_signin_record(rec)
                last_ts = rec["sign_in_time"]
        except Exception as e:
            log.debug("轮询失败（可能弹窗已关）: %s", e)
    timer.timeout.connect(tick)
    timer.start()
    # 关弹窗时停 timer（teacher_window 在 signin_code_win close 后清理）
```

**等等**：上面 teacher_window 改完了，**但弹窗本身已经关了**——timer 怎么停？

修正：**轮询 timer 挂在 `self.signin_code_win` 上**（dialog 关闭时 dialog 的 closeEvent 同步 stop timer）。重写一下：

```python
# 简化：把轮询逻辑塞进 signin_code_dialog.py
# 弹窗内 self._poll_timer = QTimer(self)
# self._poll_timer.timeout → 拉 → 追加到自己的 QListWidget
# 弹窗 closeEvent → stop timer + stop web_server
```

#### `src/config.py`（改 ~10 行）

```python
class Config:
    ...
    # W14: 二维码签到本地 HTTP 服务
    SIGNIN_WEB_PORT = int(os.getenv("SIGNIN_WEB_PORT", "5180"))
    SIGNIN_SECRET_KEY = os.getenv("SIGNIN_SECRET_KEY", "auto-generated-on-first-run")
```

#### `requirements.txt`（改 +3 行）
```
# --- W14: 多端登录签到 ---
fastapi==0.115.0
uvicorn[standard]==0.32.0
jinja2==3.1.4
httpx==0.27.2     # 测试用客户端
```

#### `build.spec`（改 hiddenimports +12 行）
```python
hiddenimports += [
    # W14: FastAPI 嵌入
    'fastapi',
    'fastapi.routing',
    'fastapi.applications',
    'fastapi.dependencies',
    'fastapi.templating',
    'fastapi.staticfiles',
    'uvicorn',
    'uvicorn.server',
    'uvicorn.config',
    'uvicorn.loops',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'starlette',
    'starlette.applications',
    'starlette.routing',
    'starlette.responses',
    'jinja2',
    'jinja2.ext',
]
```

### 5.3 配置 `.env` / `.env.template`（+2 行）
```
# W14: 多端登录签到 HTTP 服务
SIGNIN_WEB_PORT=5180
# SIGNIN_SECRET_KEY= 留空则首次启动自动生成（写入 .env）
```

### 5.4 测试 `tests/test_signin_web.py`（新，~80 行）
- `test_signin_web_serves_html` — GET /signin/<id>/<token> 返回 200 HTML
- `test_signin_web_post_signin_success` — POST /api/signin 正确 → DB 有 record
- `test_signin_web_post_signin_invalid_token` — 错误 token → 400
- `test_signin_web_post_signin_wrong_password` — 密码错 → 401
- `test_signin_web_status_polling` — 签到后 GET /api/signin/status 拿到新记录
- `test_signin_web_server_start_stop` — start + stop 不挂、不漏端口

---

## 6. 复用度统计

| 现有组件 | 是否复用 | 改动量 |
|---|---|---|
| `attendance_service.generate_signin_code(task, 'qr')` | ✅ 直接调 | 0 |
| `attendance_service.sign_in_by_qr(task, user, token)` | ✅ 直接调 | 0 |
| `auth_service.login(username, password)` | ✅ 直接调 | 0 |
| `user_dao.find_by_username` / `find_by_student_id` | ✅ 直接调 | 0 |
| `crypto.verify_password` (bcrypt) | ✅ 直接调 | 0 |
| `task_signin_code` 表（22 字符 token + TTL） | ✅ 不用改 schema | 0 |
| `attendance_record.signin_method='qr'` 字段 | ✅ 已存在 | 0 |
| 整体业务核 | **0 改动** | **0** |

**新增代码 ~430 行**：180 (signin_web) + 100 (html) + 30 (network util) + 120 (smoke) + 80 (test) + ~50 (dialog 改) + ~30 (teacher_window 改) - 重叠 ≈ 430

---

## 7. 关键设计决策（拍板点）

| # | 决策 | 倾向 | 备选 |
|---|---|---|---|
| 1 | **H5 身份识别** | 学生输学号+密码 | (a) 靠 IP/User-Agent ❌ 不安全；(b) 一次性短信码 ❌ 需要短信网关 |
| 2 | **Token 防伪** | URL 里 token + 60s TTL（DB 校验） | HMAC 签名 + 防重放 — 收益小，复杂度高 |
| 3 | **端口** | 5180（避常用）冲突自动 +1 | 80/443 ❌ 要管理员权限；8080 ❌ 易冲突 |
| 4 | **绑定地址** | `0.0.0.0`（局域网可达） | 127.0.0.1 ❌ 手机无法访问 |
| 5 | **教师端实时反馈** | 2 秒 HTTP polling | (a) SSE 收益小；(b) WebSocket 复杂 |
| 6 | **服务生命周期** | 弹窗 show → start；close → stop | 长驻后台 ❌ 资源浪费 |
| 7 | **退化机制** | qr 弹窗保留「🔄 刷新」按钮 | 数字码同步支持（H5 退化方案已经在 #1 内禀） |
| 8 | **打包体积影响** | +10 MB（fastapi+uvicorn+jinja2） | 接受（onedir 已 385 MB） |

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| **手机和教师电脑不在同一 Wi-Fi** | 演示翻车 | 启动时检测 `_get_lan_ip()` 是否有效，无效时弹窗顶部「⚠️ 当前未连局域网，手机无法访问」红字 |
| **端口被占用** | 服务起不来 | 5180 + 1 自动重试；最坏情况教师手动改 `.env` |
| **Windows 防火墙弹窗** | 学生连不上 | 首次启动提示「允许 Python 通过防火墙」；演示前手动加白名单 |
| **手机没浏览器** | 极少数 | 链接兼容微信内置浏览器（用户可复制到 Safari/Chrome） |
| **多人同时扫码** | 期望行为 | FastAPI 本来就并发，已通过 `attendance_record` UNIQUE 约束防重复签到 |
| **打包后 uvicorn 找不到** | exe 启动时 ModuleNotFoundError | build.spec hiddenimports 补齐（同 W14 修 qrcode 那次的做法） |
| **教师中途断网** | 服务挂 | QThread 内 try/except + 重连 + 日志 |
| **第二次点「二维码签到」端口未释放** | OSError | uvicorn.Server.should_exit=True → join(timeout=3) → 强制 |

---

## 9. 工期排期（剩 4 天到 6/20）

| Day | 工作 | 验收 |
|---|---|---|
| **Day 1（6/16-17）** | `signin_web.py` + `network.py` + `config.py` + `.env` + `requirements.txt` | `pytest tests/test_signin_web.py -v` 全过；`curl POST /api/signin` 成功 |
| **Day 2（6/17-18）** | `signin.html` + `signin_code_dialog.py` 改造 + `teacher_window.py` 改造 | 教师端点「二维码签到」→ 起服务 → 弹二维码 → 手机扫码 → 端到端通 |
| **Day 3（6/18-19）** | `build.spec` hiddenimports 补全 + 重打 exe + 端到端 smoke + `smoke_signin_web.py` | 重打后 exe 启动 OK；smoke 16/16 PASS；`smoke_qrcode_build.py` 类比新增 `smoke_signin_web_build.py` |
| **Day 4（6/19-20）** | 答辩 PPT + 演示视频 + 提交物 .zip | 课程交付物就绪 |

---

## 10. 待你拍板的 5 件事

1. **方案 A 整体** ✅/❌/微调？
2. **学号+密码** 是否要求**仅学号**（手机输学号麻烦，但更准确）？我倾向**支持学号或用户名**（`find_by_username` + `find_by_student_id` 都查一次）
3. **端口 5180** 默认 OK？还是要换（你机器是否常驻 5180）
4. **演示视频** 是否要单独录一段「手机真扫码」？（10 分钟够）
5. **是否加 SSE/推送**？（我建议不加，polling 够用）

确认后我开 Day 1。

---

## 附录 A：当前依赖矩阵

| 组件 | 现状 | W14 后 |
|---|---|---|
| PyQt5 | 5.15.11 | 不变 |
| FastAPI | ❌ 未装 | +0.115.0 |
| uvicorn | ❌ 未装 | +0.32.0 |
| jinja2 | ❌ 未装 | +3.1.4 |
| httpx (test) | ❌ 未装 | +0.27.2 |
| qrcode | 7.4.2（已修 hiddenimports） | 不变 |
| 打包体积 | 385 MB | ~395 MB |

## 附录 B：CLAUDE.md 改动建议

W14 完成后追加：
- `dependencies`: + fastapi/uvicorn/jinja2
- `running FastAPI in-process`: uvloop 禁用（Windows 兼容性）、uvicorn log_level='warning'
- `port conflict resolution`: 5180 + 1 自动重试
