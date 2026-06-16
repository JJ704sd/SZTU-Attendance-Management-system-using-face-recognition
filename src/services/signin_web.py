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
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_

from src.config import Config
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask
from src.services.attendance_service import AttendanceService
from src.services.auth_service import AuthError, AuthService
from src.utils.network import get_lan_ip

log = logging.getLogger(__name__)

# templates 路径: src/ui/web_templates/
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "ui" / "web_templates"


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
        from src.models.classroom import Classroom
        from src.models.course import Course
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

    # ----------------------------------------------------------
    # GET /signin/{tid}/{tok} — H5 签到页
    # ----------------------------------------------------------
    @app.get("/signin/{tid}/{tok}", response_class=HTMLResponse)
    async def signin_page(tid: int, tok: str, request: Request):
        # URL 不匹配 (教师刷新了码, 旧 URL 还在) → 友好提示
        if tid != task_id or tok != token:
            return HTMLResponse(
                "<!DOCTYPE html><html><body style='font-family:sans-serif;"
                "padding:40px;text-align:center;'>"
                "<h1>⏰ 签到码已失效</h1>"
                "<p>请重新扫描教师屏幕上的二维码。</p>"
                "</body></html>",
                status_code=400,
            )
        return templates.TemplateResponse("signin.html", {
            "request": request,
            "task_id": task_id,
            "token":   token,
        })

    # ----------------------------------------------------------
    # GET /api/signin/info?task={id} — 任务元信息 (给 H5 顶部展示)
    # ----------------------------------------------------------
    @app.get("/api/signin/info")
    async def api_signin_info(task: int):
        meta = _query_task_meta(task)
        return {"ok": True, **meta}

    # ----------------------------------------------------------
    # POST /api/signin — 学生提交学号+密码+token
    # ----------------------------------------------------------
    @app.post("/api/signin")
    async def api_signin(payload: dict):
        """Body: {task_id:int, token:str, student_id:str, password:str}

        流程:
          1. 校验请求参数完整性 + task_id/token 匹配
          2. 查 user (支持学号或 username)
          3. auth_service.login() — 复用 (含 LOGIN_MAX_ATTEMPTS 锁定)
          4. attendance_service.sign_in_by_qr() — 复用 (写 signin_method='qr')
          5. 返回 {ok, status, student_name, sign_in_time}
        """
        student_id = (payload.get("student_id") or "").strip()
        password   = payload.get("password") or ""
        tid        = payload.get("task_id")
        tok        = payload.get("token") or ""
        if not (student_id and password and isinstance(tid, int) and tok):
            return _err("BAD_REQUEST", "请求参数不完整", status=400)
        if tid != task_id or tok != token:
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
                task_id, logged_user.id, token,
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
                 port: Optional[int] = None):
        self.task_id = task_id
        self.token   = token
        self.expires_at = expires_at
        self.host    = host
        self.port    = port or Config.SIGNIN_WEB_PORT
        self.lan_ip  = get_lan_ip()
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

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
        """启动 uvicorn 在子线程; 端口冲突自动 +1 重试 1 次."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                log.warning("SigninWebServer 已在运行, 跳过重复 start")
                return
            self._server = self._build_server()
            original_port = self.port

            def _runner(srv: uvicorn.Server):
                try:
                    srv.run()
                except OSError as e:
                    # uvicorn 内部 try bind 失败 → 端口冲突
                    # 重试用 self.port + 1 (但闭包里 self.port 也得同步)
                    self.port = original_port + 1
                    log.warning(
                        "端口 %s 启动失败 (%s), 重试 %s",
                        original_port, e, self.port,
                    )
                    self._server = self._build_server()
                    try:
                        self._server.run()
                    except Exception as e2:
                        log.exception("重试端口 %s 也失败: %s", self.port, e2)
                except Exception as e:
                    log.exception("uvicorn 异常退出: %s", e)

            self._thread = threading.Thread(
                target=_runner, args=(self._server,),
                daemon=True, name="signin-web",
            )
            self._thread.start()
            log.info("SigninWebServer 已启动: %s", self.url)

    def stop(self, timeout: float = 3.0):
        """优雅停 uvicorn (should_exit=True + join). 不挂的兜底: daemon=True."""
        with self._lock:
            if self._server is not None:
                self._server.should_exit = True
            t = self._thread
        if t is not None:
            t.join(timeout=timeout)
            if t.is_alive():
                log.warning("SigninWebServer 线程未在 %.1fs 内退出 (daemon, 主进程退出时会清)", timeout)
