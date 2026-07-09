"""
services/signin_web.py — 教师端「二维码签到」本地 HTTP 服务 (W14 新增)

设计动机:
  教师点「📱 二维码签到」后, 学生用手机扫屏幕上的二维码 →
  手机浏览器打开 H5 签到页 → 输入学号+密码 → 签到成功, 教师端实时看到反馈。

核心原则:
  - 业务核零改动: 路由 handler 全部复用 auth_service.login + attendance_service.sign_in_by_qr
  - 生命周期: 与 SigninCodeDialog 绑定 (show → start, close → stop)
  - 端口: 从 .env 读 SIGNIN_WEB_PORT (默认 5180), 冲突时 +1 重试 1 次
  - 只 bind 0.0.0.0:<port>, 不暴露公网 (演示完即关)

API 总览:
  GET  /signin/{task_id}/{token}            H5 签到页 (HTML)
  GET  /api/signin/info?task={id}           任务元信息 (课程名 + 教师名)
  POST /api/signin                          学生提交 {student_id, password, task_id, token}
  GET  /api/signin/status?task={id}&since=  教师端轮询新签到
  GET  /api/health                          健康检查
"""
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import and_

from src.config import Config
from src.dao.user_dao import UserDao
from src.dao.task_signin_code_dao import TaskSigninCodeDao
from src.db import session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask
from src.models.task_signin_code import TaskSigninCode
from src.services.attendance_service import AttendanceService
from src.services.auth_service import AuthError, AuthService
from src.utils.network import get_lan_ip

log = logging.getLogger(__name__)

# templates 路径: src/ui/web_templates/
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "ui" / "web_templates"


# =====================================================
# R16 修复: Pydantic 输入校验模型
# =====================================================
# 之前 api_signin 用 `payload: dict`, student_id/password/token
# 长度完全无限制 (暴力灌入 1MB 字符串会触发 bcrypt 100ms 计算)。
# 现在改用 Pydantic BaseModel + Field 约束, FastAPI 自动校验,
# 422 会被 _validation_exception_handler 转成 400 BAD_REQUEST
# (与前端约定的错误 schema 保持一致)。
# =====================================================
class SigninPayload(BaseModel):
    """POST /api/signin 请求体校验.

    字段约束 (R16 新增):
      - student_id: 1-20 字符 (学号/username 实际长度上限 20)
      - password:   1-100 字符 (bcrypt 限制 72 字节, 但允许 100 兼容未来)
      - task_id:    正整数 (>=1)
      - token:      8-64 字符 (跟 attendance_service.sign_in_by_qr 上限对齐)
    """
    student_id: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=1, max_length=100)
    task_id: int = Field(..., ge=1)
    token: str = Field(..., min_length=8, max_length=64)


# =====================================================
# 内部辅助: 统一错误响应 / DB 查询
# =====================================================
def _err(error: str, msg: str, status: int = 400) -> JSONResponse:
    """统一错误响应包成 {ok:false, error, msg}; 与成功响应 schema 对齐."""
    return JSONResponse(
        status_code=status,
        content={"ok": False, "error": error, "msg": msg},
    )


def _lookup_user(student_id_or_username: str) -> tuple[Optional[object], str]:
    """支持学号或 username 两种方式查 user.

    Returns:
        (user_obj, error_msg). user 不为 None = 找到了, error_msg 为空.
    """
    with session_scope() as s:
        dao = UserDao(s)
        user = dao.find_by_student_id(student_id_or_username)
        if user is None:
            user = dao.find_by_username(student_id_or_username)
        if user is None:
            return None, "学号或用户名不存在"
        # expunge 让 session 关闭后仍可访问属性 (登出服务里就常这么干)
        s.expunge(user)
        return user, ""


def _query_task_meta(task_id: int) -> dict:
    """查任务的 course_name + teacher_name (H5 顶部展示)."""
    with session_scope() as s:
        from src.models.course import Classroom, Course
        from src.models.user import User
        task = s.get(AttendanceTask, task_id)
        if not task:
            return {"task_id": task_id, "course_name": None, "teacher_name": None,
                    "classroom_name": None}
        course = s.get(Course, task.course_id)
        teacher = s.get(User, task.teacher_id)
        classroom = s.get(Classroom, task.classroom_id)
        return {
            "task_id": task_id,
            "course_name": course.course_name if course else None,
            "teacher_name": teacher.real_name if teacher else None,
            "classroom_name": classroom.name if classroom else None,
        }


def _query_recent_records(task_id: int, since_iso: Optional[str]) -> list:
    """查 task 的签到记录 (since 之后). 教师端 2 秒轮询拉增量."""
    with session_scope() as s:
        from src.models.user import User
        q = s.query(AttendanceRecord).filter(
            AttendanceRecord.task_id == task_id,
            AttendanceRecord.sign_in_time.isnot(None),  # 排除缺勤占位
        )
        if since_iso:
            try:
                since_dt = datetime.fromisoformat(since_iso)
                q = q.filter(AttendanceRecord.sign_in_time > since_dt)
            except (ValueError, TypeError):
                # 非法 since 不致命: 返全量, 客户端可以 dedup
                log.debug("无法解析 since=%r, 按全量返", since_iso)
        rows = q.order_by(AttendanceRecord.sign_in_time.asc()).limit(200).all()
        result = []
        for r in rows:
            u = s.get(User, r.student_id)
            result.append({
                "student_name":  u.real_name if u else f"#{r.student_id}",
                "status":        r.status,
                "sign_in_time":  r.sign_in_time.isoformat(timespec="seconds") if r.sign_in_time else None,
                "signin_method": r.signin_method,
            })
        return result


def _classify_signin_failure(task_id: int, user_id: int) -> JSONResponse:
    """sign_in_by_qr 返 None 时细分错误 (404 / 400 / 409)."""
    with session_scope() as s:
        task = s.get(AttendanceTask, task_id)
        if not task:
            return _err("TASK_NOT_FOUND", "考勤任务不存在", status=404)
        if task.status != "open":
            return _err("TASK_CLOSED", "考勤任务已结束", status=400)
        existed = s.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.task_id == task_id,
                AttendanceRecord.student_id == user_id,
            )
        ).first()
        if existed:
            return _err("ALREADY_SIGNED", "已签到", status=409)
    return _err("CODE_INVALID", "签到码无效或已过期", status=400)


# =====================================================
# FastAPI app 构造
# =====================================================
def build_signin_app(task_id: int, token: str, expires_at) -> FastAPI:
    """构造 FastAPI app, 路由 handler 用闭包捕获 task_id/token.

    Args:
        task_id:   考勤任务 ID
        token:     22 字符 base64 token (来自 task_signin_code 表, TTL 内有效)
        expires_at: datetime | None, 暂未在 handler 里使用 (DAO 走 TTL 校验)
    """
    app = FastAPI(title="签到服务", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    # R16 修复: Pydantic 校验失败 (422) → 转 400 BAD_REQUEST
    # 原因: 前端 (H5 + 教师端) 统一用 {ok:false, error, msg} schema + 4xx 状态码
    #       判定错误。FastAPI 默认返 422 + 不一致 schema, 会让前端误判。
    # 同时也是安全加固: 不暴露 Pydantic 内部字段路径, 只说"参数不合法"。
    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(request: Request, exc: RequestValidationError):
        # 提取第一个错误信息 (避免泄露所有字段细节, 信息泄露面)
        first_err = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first_err.get("loc", []))
        msg = first_err.get("msg", "参数不合法")
        log.debug("Pydantic 校验失败: field=%s msg=%s", field, msg)
        return _err("BAD_REQUEST", f"参数不合法: {field} {msg}".strip(), status=400)

    # R16 修复: 全局兜底异常处理 — 不向客户端暴露 traceback / 内部堆栈
    # 原因: FastAPI 默认对未捕获异常返 500 + 默认错误体, 在生产环境会泄露
    #       代码路径、SQL 错误细节等。统一兜底返 INTERNAL + log.exception。
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        log.exception("未捕获异常: path=%s err=%s", request.url.path, exc)
        return _err("INTERNAL", "服务异常，请重试", status=500)

    # ----------------------------------------------------------
    # GET /signin/{tid}/{tok} — H5 签到页
    # ----------------------------------------------------------
    @app.get("/signin/{tid}/{tok}", response_class=HTMLResponse)
    async def signin_page(tid: int, tok: str, request: Request):
        # W15+ 修复: 删除 tok != token 检查!
        # 之前这里校验 URL 里的 tok == build_signin_app 闭包 token,
        # 但 web_server.token 是启时定死的, 跟 DB LIVE token 永远不一致
        # (dialog 启动时 _generate_code 又 generate 一次会 deactive 闭包里的 token,
        #  即使有 update_token 同步, 老 URL 缓存的 tok 还是会触发 400).
        # 正确做法: H5 入口只校验 task_id, 真实 token 校验让 H5 polling 拿
        # /api/signin/latest 自己处理 (见 api_signin 修法 A).
        if tid != task_id:
            return HTMLResponse(
                "<!DOCTYPE html><html><body style='font-family:sans-serif;"
                "padding:40px;text-align:center;'>"
                "<h1>签到任务不存在</h1>"
                "<p>该任务已结束或被删除, 请联系教师。</p>"
                "</body></html>",
                status_code=400,
            )
        # W15+: 传 expires_at ISO 字符串给前端, 让 H5 实时显示倒计时 + 到期禁用按钮
        # expires_at 来自 build_signin_app 闭包 (SigninWebServer 持有的同一对象)
        expires_iso = None
        if expires_at is not None:
            try:
                expires_iso = expires_at.isoformat()
            except AttributeError:
                expires_iso = str(expires_at)
        return templates.TemplateResponse(
            request, "signin.html", {
                "task_id":     task_id,
                "token":       token,
                "expires_iso": expires_iso,
            },
        )

    # ----------------------------------------------------------
    # GET /api/signin/info?task={id} — 任务元信息 (给 H5 顶部展示)
    # ----------------------------------------------------------
    @app.get("/api/signin/info")
    async def api_signin_info(task: int):
        meta = _query_task_meta(task)
        return {"ok": True, **meta}

    # ----------------------------------------------------------
    # GET /api/signin/latest?task={id} — 当前 task 的最新 LIVE token (W15+ 防缓存)
    # ----------------------------------------------------------
    @app.get("/api/signin/latest")
    async def api_signin_latest(task: int):
        """返当前 task 最新有效 (is_active=1 + 未过期) 的 qr token.

        W15+: H5 进入后每 3 秒 polling 一次, 始终用最新 token 提交,
              即使教师中途刷新了码 (老 URL 缓存也不会失效).
        返回字段: ok, task_id, token, expires_at, seconds_to_expire.
        无 LIVE token → 404 NO_LIVE_TOKEN.
        """
        from sqlalchemy import desc as _desc
        with session_scope() as s:
            code = s.query(TaskSigninCode).filter(
                TaskSigninCode.task_id == task,
                TaskSigninCode.code_type == "qr",
                TaskSigninCode.is_active == 1,
                TaskSigninCode.expires_at > datetime.now(),
            ).order_by(_desc(TaskSigninCode.created_at)).first()
            if not code:
                return _err("NO_LIVE_TOKEN", "该任务暂无有效签到码 (教师尚未发起或已过期)", status=404)
            seconds_left = int((code.expires_at - datetime.now()).total_seconds())
            return {
                "ok": True,
                "task_id": task,
                "token": code.code_value,
                "expires_at": code.expires_at.isoformat(),
                "seconds_to_expire": seconds_left,
            }

    # ----------------------------------------------------------
    # POST /api/signin — 学生提交学号+密码+token
    # ----------------------------------------------------------
    @app.post("/api/signin")
    async def api_signin(payload: SigninPayload):
        """Body: {task_id:int, token:str, student_id:str, password:str}

        R16 修复: payload 用 Pydantic SigninPayload 校验 (长度/类型),
                  缺字段或超长 → FastAPI 自动 422 → handler 转 400 BAD_REQUEST
                  (前端契约不变)。

        流程:
          1. 校验请求参数完整性 + task_id 匹配
          2. W15+ 修复: token 校验改成从 DB 查 task_signin_code 表
             (不再用闭包捕获的 token 对比, 否则教师刷新码后老 H5 URL 全失效)
          3. 查 user (支持学号或 username)
          4. auth_service.login() — 复用 (含 LOGIN_MAX_ATTEMPTS 锁定)
          5. attendance_service.sign_in_by_qr() — 复用 (写 signin_method='qr')
          6. 返回 {ok, status, student_name, sign_in_time}
        """
        student_id = payload.student_id.strip()
        password   = payload.password
        tid        = payload.task_id
        tok        = payload.token
        if not student_id:  # Pydantic 已要求 min_length=1, 此处只防纯空白
            return _err("BAD_REQUEST", "请求参数不完整", status=400)
        if tid != task_id:
            return _err("CODE_INVALID", "签到码无效或已过期", status=400)

        # W15+ 修复: token 校验从 DB 实时查 (task_signin_code 表 is_active=1 + 未过期)
        # 这样即使教师刷新了码, 老 H5 页面 (老 token) 提交时也能正确拒绝, 而不是误判.
        with session_scope() as s:
            dao = TaskSigninCodeDao(s)
            valid_code = dao.find_active_by_value(task_id, "qr", tok)
            if not valid_code:
                return _err("CODE_INVALID", "签到码无效或已过期", status=400)

        # 1) 查 user
        user, err = _lookup_user(student_id)
        if user is None:
            return _err("AUTH_FAILED", err, status=401)
        if user.role != "student":
            return _err("AUTH_FAILED", "该账号不是学生", status=401)

        # 2) auth_service.login (复用) — 验证密码 + 触发锁定
        try:
            logged_user = AuthService().login(user.username, password)
        except AuthError as e:
            msg = str(e)
            if "锁定" in msg:
                return _err("ACCOUNT_LOCKED", msg, status=403)
            return _err("AUTH_FAILED", "学号或密码错误", status=401)

        # 3) sign_in_by_qr (复用)
        try:
            record = AttendanceService().sign_in_by_qr(
                task_id, logged_user.id, tok,
            )
        except Exception as e:
            log.exception("sign_in_by_qr 异常: %s", e)
            return _err("INTERNAL", "服务异常，请重试", status=500)
        if record is None:
            return _classify_signin_failure(task_id, logged_user.id)

        return {
            "ok":            True,
            "status":        record.status,
            "student_name":  logged_user.real_name,
            "signin_method": record.signin_method,
            "sign_in_time":  record.sign_in_time.isoformat(timespec="seconds") if record.sign_in_time else None,
        }

    # ----------------------------------------------------------
    # GET /api/signin/status?task={id}&since={ts}
    # ----------------------------------------------------------
    @app.get("/api/signin/status")
    async def api_status(task: int, since: Optional[str] = None):
        records = _query_recent_records(task, since)
        return {"ok": True, "new_records": records}

    # ----------------------------------------------------------
    # GET /api/health — 心跳
    # ----------------------------------------------------------
    @app.get("/api/health")
    async def health():
        return {"ok": True}

    return app


# =====================================================
# 进程内 uvicorn 封装
# =====================================================
class SigninWebServer:
    """封装 uvicorn.Server 在 threading.Thread 内跑.

    UI 集成 (W14 Day 2) 会再包一层 QTimer 调度, 本类只负责"启停 + 端口自适应".

    端口冲突策略:
      启动时如果默认端口被占, 自动 +1 重试 1 次. 重试仍失败 → 静默退出, 由调用方
      (UI) 检测 url/running 状态决定是否提示教师.

    线程模型:
      threading.Thread(daemon=True) → 主进程退出时自动收尾, 不会泄漏进程.
      """

    def __init__(self, task_id: int, token: str, expires_at,
                 host: str = "0.0.0.0",
                 port: Optional[int] = None,
                 watchdog: bool = True):
        self.task_id = task_id
        self.token   = token
        self.expires_at = expires_at
        self.host    = host
        self.port    = port or Config.SIGNIN_WEB_PORT
        self.lan_ip  = get_lan_ip()
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        # W15+: watchdog (5s ping, 3 次失败自动重建)
        self._enable_watchdog = watchdog
        self._wd_stop: Optional[threading.Event] = None
        self._wd_thread: Optional[threading.Thread] = None

    # -----------------------------------------------------
    # 给 UI 用的两个属性
    # -----------------------------------------------------
    @property
    def url(self) -> str:
        """给 signin_code_dialog 用, 生成二维码内容 URL."""
        return f"http://{self.lan_ip}:{self.port}/signin/{self.task_id}/{self.token}"

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # -----------------------------------------------------
    # 内部
    # -----------------------------------------------------
    def _build_server(self) -> uvicorn.Server:
        app = build_signin_app(self.task_id, self.token, self.expires_at)
        cfg = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",   # 静音 uvicorn 默认 access log
            access_log=False,
            lifespan="on",
        )
        return uvicorn.Server(cfg)

    def start(self):
        """启动 uvicorn 在子线程; 端口冲突自动 +1 重试 5 次.

        W15+ 调整: 重试次数 1 → 5, 之前 1 次重试还失败就静默挂掉,
        教师以为"网络问题"但其实是端口全被占. 现在重试 5 次 (5180-5184),
        仍失败才放弃并 log error.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                log.warning("SigninWebServer 已在运行, 跳过重复 start")
                return
            self._server = self._build_server()
            original_port = self.port
            MAX_PORT_RETRY = 5  # W15+: 1 → 5

            def _runner(srv: uvicorn.Server):
                retry = 0
                current_srv = srv
                while retry <= MAX_PORT_RETRY:
                    try:
                        current_srv.run()
                        return  # 正常退出
                    except OSError as e:
                        # uvicorn 内部 try bind 失败 → 端口冲突
                        if retry >= MAX_PORT_RETRY:
                            log.error(
                                "端口 %s 连续 %s 次启动失败 (%s), 放弃. "
                                "请检查 5180-%s 端口占用, 或改 .env 的 SIGNIN_WEB_PORT",
                                original_port, MAX_PORT_RETRY + 1, e,
                                original_port + MAX_PORT_RETRY,
                            )
                            return
                        retry += 1
                        self.port = original_port + retry
                        log.warning(
                            "端口 %s 启动失败 (%s), 重试 %s/%s → 端口 %s",
                            original_port + retry - 1, e, retry, MAX_PORT_RETRY, self.port,
                        )
                        with self._lock:
                            self._server = self._build_server()
                        current_srv = self._server
                    except Exception as e:
                        log.exception("uvicorn 异常退出: %s", e)
                        return

            self._thread = threading.Thread(
                target=_runner, args=(self._server,),
                daemon=True, name="signin-web",
            )
            self._thread.start()
            log.info("SigninWebServer 已启动: %s", self.url)

        # W15+: 启 watchdog (在 self._lock 外启, 避免 watchdog 也持锁死锁)
        if self._enable_watchdog:
            self._start_watchdog()

    def stop(self, timeout: float = 3.0):
        """优雅停 uvicorn (should_exit=True + join). 不挂的兜底: daemon=True."""
        # W15+: 先停 watchdog 避免它在 server 死后还尝试 ping
        self._stop_watchdog()
        with self._lock:
            if self._server is not None:
                self._server.should_exit = True
            t = self._thread
        if t is not None:
            t.join(timeout=timeout)
            if t.is_alive():
                log.warning("SigninWebServer 线程未在 %.1fs 内退出 (daemon, 主进程退出时会清)", timeout)

    # -----------------------------------------------------
    # W15+: update_token (二维码内容跟随教师刷新)
    # -----------------------------------------------------
    def update_token(self, new_token: str):
        """同步 token, 重 build FastAPI app + restart uvicorn.

        背景 (W15+ 修复):
          教师点"刷新码" → DB 写新 token → 但 web_server FastAPI app 闭包里
          仍是旧 token, 二维码图片 (self.url) 也指向旧 URL, 学生扫码还是老 H5.
          现在 update_token 后 self.url 立刻反映新 token, _render_code 重新画
          出来的二维码就是新 URL.

        副作用:
          - restart 期间 (几百 ms) 学生提交会被 503. 教师刚点完刷新码的瞬间,
            不太可能有学生正好提交, 风险低.
          - 端口保持不变 (用 SO_REUSEADDR 等机制 uvicorn 一般能 bind 回去).

        Raises:
            RuntimeError: 重启失败时. 调用方应 try/except 后决定降级策略.
        """
        with self._lock:
            if new_token == self.token:
                log.debug("update_token: token 未变, 跳过")
                return
            log.info("SigninWebServer token 更新: %s -> %s", self.token[:8], new_token[:8])
            self.token = new_token

            # 1) 停老 server + 等老线程退出
            if self._server is not None:
                self._server.should_exit = True
            old_thread = self._thread
            self._server = None
            self._thread = None
        if old_thread is not None:
            old_thread.join(timeout=3.0)
            if old_thread.is_alive():
                log.warning("SigninWebServer 老线程未退出, 继续 restart (新闭包可能端口冲突)")

        # 2) 起新 server (新 _build_server 会用 self.token = new_token 捕获)
        with self._lock:
            try:
                self._server = self._build_server()
                self._thread = threading.Thread(
                    target=self._server.run,
                    daemon=True,
                    name="signin-web",
                )
                self._thread.start()
            except Exception as e:
                log.exception("update_token restart 失败: %s", e)
                raise RuntimeError(f"SigninWebServer.update_token 重启失败: {e}") from e
        log.info("SigninWebServer token 已更新: 新 url=%s", self.url)

    # -----------------------------------------------------
    # W15+: watchdog 自动重建
    # -----------------------------------------------------
    def _start_watchdog(self):
        """启 watchdog 线程: 每 5s ping /api/health, 3 次失败自动重建."""
        if self._wd_thread is not None and self._wd_thread.is_alive():
            return  # 已启
        self._wd_stop = threading.Event()
        self._wd_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="signin-web-watchdog",
        )
        self._wd_thread.start()
        log.info("SigninWebServer watchdog 已启动 (5s 间隔)")

    def _stop_watchdog(self):
        if self._wd_stop is not None:
            self._wd_stop.set()
        t = self._wd_thread
        if t is not None:
            t.join(timeout=2.0)
        self._wd_thread = None
        self._wd_stop = None

    def _watchdog_loop(self):
        """每 5s 用 httpx ping localhost, 6 次连续失败 (30s) → 重建 server.

        W15+ 调整: 阈值从 3 次提到 6 次 (3 → 30s 容错),
        避免网络抖动 / 临时 H5 提交阻塞误判, 不丢学生请求.

        httpx 是 fastapi 测试已有依赖 (requirements.txt), 不增加新包.
        """
        import httpx  # 延迟导入, 启动快
        fail_count = 0
        while not self._wd_stop.is_set():
            ok = False
            try:
                r = httpx.get(f"http://127.0.0.1:{self.port}/api/health", timeout=2.0)
                ok = r.status_code == 200
            except Exception:
                ok = False
            if ok:
                fail_count = 0
            else:
                fail_count += 1
                log.debug("watchdog: ping port=%s 失败 (count=%s)", self.port, fail_count)
            if fail_count >= 6:
                log.warning(
                    "watchdog: port=%s 连续 6 次 (30s) 失败, 重建 server "
                    "(可能是网络抖动或真有故障, 已尽量容错避免误判)",
                    self.port,
                )
                try:
                    # 重 build + restart (走类似 update_token 的逻辑, 但不动 token)
                    self._rebuild_server()
                    fail_count = 0
                except Exception as e:
                    log.exception("watchdog 重建失败: %s", e)
                    fail_count = 0  # 别无限重试, 等下一轮
            # 等 5 秒 (或被 stop 唤醒)
            if self._wd_stop.wait(5.0):
                break
        log.debug("SigninWebServer watchdog 退出")

    def _rebuild_server(self):
        """不停 token, 重建 server (watchdog 用). 与 update_token 共享大部分逻辑."""
        with self._lock:
            if self._server is not None:
                self._server.should_exit = True
            old_thread = self._thread
            self._server = None
            self._thread = None
        if old_thread is not None:
            old_thread.join(timeout=3.0)
        with self._lock:
            self._server = self._build_server()
            self._thread = threading.Thread(
                target=self._server.run,
                daemon=True,
                name="signin-web",
            )
            self._thread.start()
        log.info("watchdog: server 已重建, url=%s", self.url)
