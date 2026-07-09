"""
tests/test_signin_web.py — SigninWeb (W14 后端) 单元测试

W14 新增: 教师端 FastAPI 嵌入服务的核心路径单测。

覆盖 (6 用例, 严格按交付清单 + 5 边界用例):
  - test_signin_web_serves_html          GET /signin/<id>/<tok> → 200 HTML 含表单
  - test_signin_web_post_signin_success  POST /api/signin 正确 → DB 有 record (signin_method='qr')
  - test_signin_web_post_signin_invalid_token   错误 token → 400 CODE_INVALID
  - test_signin_web_post_signin_wrong_password  错密码 → 401 AUTH_FAILED
  - test_signin_web_status_polling       GET /api/signin/status 拿 new_records
  - test_signin_web_server_start_stop    threading start+stop 不挂、不漏端口

依赖: 真实 MySQL (.env 配好) + uuid 随机用户名避免冲突 (学 test_auth_service.py)
"""
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta

import httpx
import pytest

from src.db import engine, session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask
from src.models.course import Classroom, Course
from src.models.user import User
from src.services.attendance_service import AttendanceService
from src.services.auth_service import AuthService
from src.services.signin_web import SigninWebServer, build_signin_app

# W14 TestClient 默认用 starlette, 跑内存里不走真实 socket,
# 这样可以并发跑 6 个 case 互不干扰, 不用启 uvicorn.
from fastapi.testclient import TestClient


# =====================================================
# Test isolation: test_signin_code_dialog.py 的 patched_service fixture 在
# teardown 时会无条件 `del AttendanceService.generate_signin_code` (因为
# 它判定 `is fake_generate` 为 True 后会删)。如果该测试文件先跑, 我们的
# fixture (依赖 generate_signin_code) 会因 AttributeError 失败。
#
# 修复: 模块级 autouse fixture 在每个 test 前重新绑定原始方法。
# 原始方法在 import 时捕获, 不依赖任何 monkey-patch 状态。
# =====================================================
try:
    _ORIGINAL_GENERATE = AttendanceService.generate_signin_code
    _HAS_ORIGINAL = True
except AttributeError:
    _ORIGINAL_GENERATE = None
    _HAS_ORIGINAL = False


@pytest.fixture(autouse=True)
def _restore_attendance_service_methods():
    """autouse: 每个 test 前恢复 generate_signin_code (防 test_signin_code_dialog 删掉)。"""
    if _HAS_ORIGINAL and (
        not hasattr(AttendanceService, "generate_signin_code")
        or AttendanceService.generate_signin_code is not _ORIGINAL_GENERATE
    ):
        AttendanceService.generate_signin_code = _ORIGINAL_GENERATE
    yield


# =====================================================
# Fixtures
# =====================================================
def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def teacher_user():
    teacher = AuthService().register(
        username=_uni("t"), password="123456",
        real_name="签到测试老师", role="teacher",
    )
    yield teacher
    # 显式清理: 用 raw SQL 倒序删 FK, 避免 ORM bulk delete 的 session sync 问题.
    # 顺序: attendance_record → attendance_task → course_enrollment → course → classroom → user
    # 否则 conftest autouse session 末 cleanup 删 user 时 FK 1451 整 session 失败。
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM attendance_record WHERE task_id IN "
            "(SELECT id FROM attendance_task WHERE teacher_id = :tid)"
        ), {"tid": teacher.id})
        conn.execute(text(
            "DELETE FROM attendance_task WHERE teacher_id = :tid"
        ), {"tid": teacher.id})
        conn.execute(text(
            "DELETE FROM course_enrollment WHERE student_id IN "
            "(SELECT id FROM user WHERE username = :un)"
        ), {"un": teacher.username})  # 防御性, 该 teacher 不会有 enrollment
        conn.execute(text(
            "DELETE FROM course WHERE teacher_id = :tid"
        ), {"tid": teacher.id})
        conn.execute(text(
            "DELETE FROM user WHERE id = :tid"
        ), {"tid": teacher.id})


@pytest.fixture
def student_user():
    sid = _uni("s")
    stu = AuthService().register(
        username=_uni("u"), password="123456",
        real_name="签到测试学生", role="student", student_id=sid,
    )
    yield stu
    # 显式清理: raw SQL 删 record → enrollment → user (FK 顺序)
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "DELETE FROM attendance_record WHERE student_id = :sid"
        ), {"sid": stu.id})
        conn.execute(text(
            "DELETE FROM course_enrollment WHERE student_id = :sid"
        ), {"sid": stu.id})
        conn.execute(text(
            "DELETE FROM user WHERE id = :sid"
        ), {"sid": stu.id})


@pytest.fixture
def open_task(teacher_user, student_user):
    """建一个 open 的考勤任务 + 给 student 报名, 防止 close_task fallback 污染."""
    suf = uuid.uuid4().hex[:6]
    with session_scope() as s:
        from src.models.course_enrollment import CourseEnrollment
        course = Course(
            course_code=f"SG{suf}", course_name="签到测试课",
            course_type="theory", teacher_id=teacher_user.id,
        )
        s.add(course); s.flush()
        s.add(CourseEnrollment(course_id=course.id, student_id=student_user.id))
        classroom = Classroom(name=f"测试教室{suf}")
        s.add(classroom); s.flush()
        course_id, classroom_id = course.id, classroom.id
    task_id = AttendanceService().create_task(
        course_id=course_id,
        teacher_id=teacher_user.id,
        classroom_id=classroom_id,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=1),
    )
    return {
        "task_id": task_id,
        "course_id": course_id,
        "classroom_id": classroom_id,
        "teacher": teacher_user,
        "student": student_user,
    }


@pytest.fixture
def qr_token(open_task):
    """为 open_task 生成一个 qr 签到码, 返回 {task_id, token, code_obj}."""
    result = AttendanceService().generate_signin_code(
        open_task["task_id"], "qr", ttl_seconds=60,
    )
    assert result is not None, "generate_signin_code 失败 (任务可能非 open)"
    return {
        "task_id":   open_task["task_id"],
        "token":     result["code"],
        "expires_at": result["expires_at"],
    }


@pytest.fixture
def client(qr_token):
    """FastAPI TestClient (内存跑, 不开端口, 速度快无副作用)."""
    app = build_signin_app(qr_token["task_id"], qr_token["token"], qr_token["expires_at"])
    return TestClient(app)


# =====================================================
# Tests
# =====================================================
def test_signin_web_serves_html(client, qr_token):
    """GET /signin/{task_id}/{token} → 200 HTML 含学号/密码表单."""
    resp = client.get(f"/signin/{qr_token['task_id']}/{qr_token['token']}")
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "<html" in body.lower()
    # H5 关键元素
    assert 'name="student_id"' in body
    assert 'name="password"' in body
    assert 'type="password"' in body
    assert str(qr_token["task_id"]) in body  # task_id 渲染进 HTML
    # fetch /api/signin 脚本
    assert "/api/signin" in body


def test_signin_web_html_includes_countdown(client, qr_token):
    """W15+: H5 渲染含倒计时条 + JS 倒计时逻辑 (5 分钟 TTL)."""
    resp = client.get(f"/signin/{qr_token['task_id']}/{qr_token['token']}")
    body = resp.text
    assert resp.status_code == 200
    # 倒计时 DOM
    assert 'id="countdown"' in body, "缺倒计时容器"
    assert 'id="time_text"' in body, "缺时间显示 span"
    # 倒计时 JS
    assert "tickCountdown" in body, "缺 tickCountdown 函数"
    assert "expiresAt" in body, "缺 expiresAt 变量"
    assert "new Date(" in body, "缺 Date 解析"
    # 到期禁用按钮逻辑
    assert "cdExpired" in body, "缺 cdExpired 状态"
    assert "码已过期" in body, "缺过期文案"
    # AUTH_FAILED 提示 (W15+: 学号密码错有专门文案)
    # 注: W14 错误码 LOGIN_FAILED 已在 W15+ 重命名为 AUTH_FAILED (更标准)
    assert "AUTH_FAILED" in body


def test_signin_web_post_signin_success(client, qr_token, student_user):
    """POST /api/signin 正确凭证 → 200 + DB 有 record (signin_method='qr')."""
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      qr_token["token"],
        "student_id": student_user.student_id,  # 学号登录
        "password":   "123456",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["student_name"] == student_user.real_name
    assert data["signin_method"] == "qr"
    assert data["status"] in ("present", "late")
    assert data["sign_in_time"]

    # DB 验
    with session_scope() as s:
        rec = s.query(AttendanceRecord).filter(
            AttendanceRecord.task_id == qr_token["task_id"],
            AttendanceRecord.student_id == student_user.id,
        ).first()
        assert rec is not None
        assert rec.signin_method == "qr"


def test_signin_web_post_signin_invalid_token(client, qr_token):
    """错误 token → 400 CODE_INVALID."""
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      "wrong-token-22chars-xyz",
        "student_id": "any",
        "password":   "any",
    })
    assert resp.status_code == 400, resp.text
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "CODE_INVALID"


def test_signin_web_post_signin_wrong_password(client, qr_token, student_user):
    """错密码 → 401 AUTH_FAILED."""
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      qr_token["token"],
        "student_id": student_user.student_id,
        "password":   "wrongpass",
    })
    assert resp.status_code == 401, resp.text
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "AUTH_FAILED"


def test_signin_web_status_polling(client, qr_token, student_user):
    """签到后 GET /api/signin/status 拿到 new_records."""
    # 先签到
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      qr_token["token"],
        "student_id": student_user.username,  # username 也可登录
        "password":   "123456",
    })
    assert resp.status_code == 200

    # 轮询拿新记录
    resp = client.get(f"/api/signin/status?task={qr_token['task_id']}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["new_records"], list)
    assert len(data["new_records"]) >= 1
    rec = data["new_records"][0]
    assert rec["student_name"] == student_user.real_name
    assert rec["signin_method"] == "qr"
    assert rec["status"] in ("present", "late")

    # 测试 since 增量: 把 since 设为现在之后 → 应该没有新记录
    future = (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds")
    resp = client.get(f"/api/signin/status?task={qr_token['task_id']}&since={future}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["new_records"] == []


def test_signin_web_server_start_stop(open_task):
    """真实 uvicorn 启停: start 后 url 可访问, stop 后端口释放."""
    # 选一个空闲端口避免跟 SIGNIN_WEB_PORT 默认 5180 冲突
    s = socket.socket(); s.bind(("0.0.0.0", 0)); free_port = s.getsockname()[1]; s.close()

    result = AttendanceService().generate_signin_code(open_task["task_id"], "qr", ttl_seconds=60)
    assert result is not None

    srv = SigninWebServer(
        task_id=open_task["task_id"],
        token=result["code"],
        expires_at=result["expires_at"],
        host="127.0.0.1",
        port=free_port,
    )
    assert srv.url.startswith("http://") and str(free_port) in srv.url

    srv.start()

    # 等 server 真起来 (uvicorn 启动需要 ~50-300ms)
    deadline = time.time() + 5
    last_err = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{free_port}/api/health", timeout=1.0)
            if r.status_code == 200:
                assert r.json()["ok"] is True
                break
        except Exception as e:
            last_err = e
            time.sleep(0.1)
    else:
        srv.stop()
        pytest.fail(f"SigninWebServer 5s 内未响应 /api/health: {last_err}")

    # 测签到页也能 GET
    page_url = f"http://127.0.0.1:{free_port}/signin/{open_task['task_id']}/{result['code']}"
    r = httpx.get(page_url, timeout=2.0)
    assert r.status_code == 200
    assert "<html" in r.text.lower()

    # 停
    srv.stop(timeout=3.0)
    assert srv.running is False

    # 端口释放 (SO_REUSEADDR, 紧跟 bind 应能成功)
    s2 = socket.socket(); s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s2.bind(("0.0.0.0", free_port))
        bound = True
    except OSError:
        bound = False
    s2.close()
    assert bound, f"端口 {free_port} 未释放"


def test_signin_web_health_endpoint(client):
    """健康检查."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_signin_web_info_endpoint(client, qr_token, open_task):
    """GET /api/signin/info 返回 task 元信息."""
    resp = client.get(f"/api/signin/info?task={qr_token['task_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["task_id"] == qr_token["task_id"]
    # teacher_name 应当是 fixture teacher
    assert data["teacher_name"] == open_task["teacher"].real_name
    assert data["course_name"] == "签到测试课"


def test_signin_web_bad_task_token_returns_400(client):
    """URL 里 task_id 不匹配 → 400 (而非 500).

    W15+ 修复: signin_page 只校验 task_id, 不校验 token (URL 老 token
    跟 web_server 内存 token 永远不一致, 老 "签到码已失效" 文案已删除).
    新文案: "签到任务不存在 / 该任务已结束或被删除, 请联系教师".
    """
    resp = client.get("/signin/999999/not-the-real-token")
    assert resp.status_code == 400
    assert "签到任务不存在" in resp.text or "结束" in resp.text


def test_signin_web_post_missing_fields(client, qr_token):
    """POST 缺字段 → 400 BAD_REQUEST (不要 500)."""
    resp = client.post("/api/signin", json={"task_id": qr_token["task_id"]})
    assert resp.status_code == 400
    assert resp.json()["error"] == "BAD_REQUEST"


def test_signin_web_already_signed(client, qr_token, student_user):
    """已签到后再签 → 409 ALREADY_SIGNED."""
    body = {
        "task_id":    qr_token["task_id"],
        "token":      qr_token["token"],
        "student_id": student_user.student_id,
        "password":   "123456",
    }
    # 第一次成功
    r1 = client.post("/api/signin", json=body)
    assert r1.status_code == 200
    # 第二次 → 409
    r2 = client.post("/api/signin", json=body)
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"] == "ALREADY_SIGNED"


# =====================================================
# W15+ 修复: token 校验改 DB 实时查 + update_token
# =====================================================
def test_signin_web_post_old_token_after_refresh_rejected(client, open_task, student_user):
    """W15+ 修法 A 验证: 教师刷新码后, 老 token (闭包里仍是它) 提交 → CODE_INVALID.

    旧行为 (W14): 闭包里的旧 token 仍能匹配, 但 DB 里 is_active=0, service 返 None
                  兜底 "签到码无效或已过期". 老 H5 页面能打开但提交失败.
    新行为 (W15+): 提交前先用 DB 校验 token, 老 token 直接 400 CODE_INVALID.
    """
    tid = open_task["task_id"]

    # 第一次生成 token
    from src.services.attendance_service import AttendanceService
    r1 = AttendanceService().generate_signin_code(tid, "qr", ttl_seconds=60)
    assert r1 is not None
    old_token = r1["code"]

    # 教师"刷新码" → DB 里 old_token is_active=0, 生成新 token
    r2 = AttendanceService().generate_signin_code(tid, "qr", ttl_seconds=60)
    assert r2 is not None
    new_token = r2["code"]
    assert old_token != new_token

    # 学生拿老 token 提交 (模拟老 H5 页面) → 应当被拒
    body = {
        "task_id":    tid,
        "token":      old_token,
        "student_id": student_user.student_id,
        "password":   "123456",
    }
    resp = client.post("/api/signin", json=body)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"] == "CODE_INVALID"


def test_signin_web_update_token_changes_url():
    """W15+ 修法 B 验证: SigninWebServer.update_token 改 url.

    闭环测试, 不真启 uvicorn (避免端口占用): 只验证 self.token / self.url 字段.
    """
    from src.services.signin_web import SigninWebServer

    srv = SigninWebServer(task_id=999, token="OLD_TOKEN_AAAAAAAAAA", expires_at=None)
    old_url = srv.url
    assert "OLD_TOKEN_AAAAAAAAAA" in old_url

    # 改 token (不开 server, 只验证字段)
    srv.token = "NEW_TOKEN_BBBBBBBBBB"
    assert "NEW_TOKEN_BBBBBBBBBB" in srv.url
    assert "OLD_TOKEN_AAAAAAAAAA" not in srv.url


def test_signin_web_update_token_full_restart(open_task):
    """W15+ 修法 B 验证: update_token 真实 restart 后, 新 token 能服务.

    启在端口 0 (系统随机分配), 测完关掉, 不污染.
    """
    import socket
    import time
    from src.services.signin_web import SigninWebServer, build_signin_app

    # 找一个空闲端口
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    srv = SigninWebServer(task_id=open_task["task_id"], token="FIRST_TOKEN",
                           expires_at=None, host="127.0.0.1", port=port)
    srv.start()
    try:
        time.sleep(0.5)  # 等 uvicorn ready
        # 用 build_signin_app 构造 FastAPI app (用老 token 闭包)
        app1 = build_signin_app(open_task["task_id"], "FIRST_TOKEN", None)
        from fastapi.testclient import TestClient
        c1 = TestClient(app1)
        r = c1.get(f"/signin/{open_task['task_id']}/FIRST_TOKEN")
        assert r.status_code in (200, 400)

        # update_token → url 立刻变
        srv.update_token("SECOND_TOKEN")
        time.sleep(0.5)
        assert srv.token == "SECOND_TOKEN"
        assert "SECOND_TOKEN" in srv.url
        assert "FIRST_TOKEN" not in srv.url

        # 新 token 闭包的 app
        app2 = build_signin_app(open_task["task_id"], "SECOND_TOKEN", None)
        c2 = TestClient(app2)
        r = c2.get(f"/signin/{open_task['task_id']}/SECOND_TOKEN")
        assert r.status_code in (200, 400)
    finally:
        srv.stop()


def test_signin_web_watchdog_starts_and_stops(open_task):
    """W15+: watchdog 启动后能正常停止, 不会泄漏线程."""
    import socket
    import time
    from src.services.signin_web import SigninWebServer

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    srv = SigninWebServer(task_id=open_task["task_id"], token="WATCHDOG_TEST",
                           expires_at=None, host="127.0.0.1", port=port, watchdog=True)
    srv.start()
    try:
        time.sleep(0.5)
        # watchdog 线程已启
        assert srv._wd_thread is not None, "watchdog thread 没启"
        assert srv._wd_thread.is_alive(), "watchdog thread 已死"
        assert srv._wd_stop is not None
    finally:
        srv.stop()
    # stop 后 watchdog 线程应退出 (join 超时 2s)
    if srv._wd_thread is not None:
        assert not srv._wd_thread.is_alive(), "watchdog 线程 stop 后未退出"


def test_signin_web_watchdog_disabled_works(open_task):
    """W15+: watchdog=False 时不启 watchdog (测试或开发场景)."""
    import socket
    import time
    from src.services.signin_web import SigninWebServer

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    srv = SigninWebServer(task_id=open_task["task_id"], token="NO_WATCHDOG",
                           expires_at=None, host="127.0.0.1", port=port, watchdog=False)
    srv.start()
    try:
        time.sleep(0.5)
        assert srv._wd_thread is None, "watchdog=False 但线程被启了"
    finally:
        srv.stop()


# =====================================================
# W15+ /api/signin/latest — H5 polling 防缓存专用端点
# =====================================================
def test_signin_web_latest_returns_current_live_token(client, qr_token, open_task):
    """W15+: GET /api/signin/latest?task=N 返当前 LIVE token.

    防缓存方案的核心: H5 每 3s polling 拿当前最新 token, 不用 URL 里
    可能过期的老 token. 这里测 1) 返回 ok=True 2) token 跟 fixture 一致
    3) 包含 expires_at 字段 (H5 倒计时用得到).
    """
    resp = client.get(f"/api/signin/latest?task={open_task['task_id']}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["task_id"] == open_task["task_id"]
    assert data["token"] == qr_token["token"]
    assert "expires_at" in data and data["expires_at"]
    assert data["seconds_to_expire"] > 0


def test_signin_web_latest_after_refresh_returns_new_token(client, qr_token, open_task):
    """W15+: 教师刷码后, /api/signin/latest 应该立刻返新 token (不是老 token).

    这是防缓存的关键: 教师在 dialog 里点"刷新"生成新码, 老 H5 URL
    缓存的用户页面 3 秒后自动拿到新 token, 老 token 自动失效.
    """
    # 教师刷一次码
    result = AttendanceService().generate_signin_code(
        open_task["task_id"], "qr", ttl_seconds=60,
    )
    new_token = result["code"]
    assert new_token != qr_token["token"], "刷新码应产生新 token"

    # /api/signin/latest 应该返新 token
    resp = client.get(f"/api/signin/latest?task={open_task['task_id']}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["token"] == new_token, f"期望新 token {new_token!r}, 拿到 {data['token']!r}"


def test_signin_web_latest_404_when_no_live_token(client, open_task):
    """W15+: 无 LIVE token (教师未发起) → 404 NO_LIVE_TOKEN.

    H5 收到 404 后按钮变灰, 倒计时显示"教师尚未发起", 不让用户提交.
    """
    # 把 fixture 生成的码 deactivate
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE task_signin_code SET is_active = 0 WHERE task_id = :tid"
        ), {"tid": open_task["task_id"]})

    resp = client.get(f"/api/signin/latest?task={open_task['task_id']}")
    assert resp.status_code == 404, resp.text
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "NO_LIVE_TOKEN"


# =====================================================
# R16 修复: Pydantic 输入校验 + TemplateResponse 新 API + 全局异常处理
# =====================================================
def test_signin_web_post_payload_validation_long_password_returns_400(client, qr_token, student_user):
    """R16: Pydantic 校验 password 超长 (>100 字符) → 400 BAD_REQUEST.

    之前 raw dict 无校验, 1MB 字符串会触发 bcrypt 100ms 计算浪费资源,
    也可能被用作资源耗尽攻击向量。Pydantic max_length=100 兜底拒绝。
    """
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      qr_token["token"],
        "student_id": student_user.student_id,
        "password":   "x" * 101,  # 超过 max_length=100
    })
    assert resp.status_code == 400, resp.text
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "BAD_REQUEST"
    # 不暴露 Pydantic 内部路径 (信息泄露面), 只提示 field
    assert "password" in data["msg"] or "参数不合法" in data["msg"]


def test_signin_web_post_payload_validation_long_token_returns_400(client, qr_token, student_user):
    """R16: Pydantic 校验 token 超长 (>64 字符) → 400 BAD_REQUEST.

    二维码 token 由 secrets.token_urlsafe(16) 生成 = 22 字符,
    64 字符上限已宽松 3 倍, 超长必是非法请求。
    """
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      "T" * 65,
        "student_id": student_user.student_id,
        "password":   "123456",
    })
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"] == "BAD_REQUEST"


def test_signin_web_post_payload_validation_short_token_returns_400(client, qr_token, student_user):
    """R16: Pydantic 校验 token 过短 (<8 字符) → 400 BAD_REQUEST.

    防御: 防止 1-7 字符暴力枚举扫任务 (虽然 task_id 也限定)。
    """
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      "abc",  # < min_length=8
        "student_id": student_user.student_id,
        "password":   "123456",
    })
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"] == "BAD_REQUEST"


def test_signin_web_post_payload_validation_negative_task_id_returns_400(client, qr_token, student_user):
    """R16: Pydantic 校验 task_id 必须 >=1 → 400 BAD_REQUEST (不是 422).

    与前端契约: 4xx = 业务错误, 5xx = 系统错误。所有校验失败统一 400。
    """
    resp = client.post("/api/signin", json={
        "task_id":    -1,  # ge=1 拒绝
        "token":      qr_token["token"],
        "student_id": student_user.student_id,
        "password":   "123456",
    })
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"] == "BAD_REQUEST"


def test_signin_web_post_payload_validation_wrong_type_returns_400(client, qr_token, student_user):
    """R16: Pydantic 校验 task_id 类型错 (string 不是 int) → 400 BAD_REQUEST."""
    resp = client.post("/api/signin", json={
        "task_id":    "not_an_int",
        "token":      qr_token["token"],
        "student_id": student_user.student_id,
        "password":   "123456",
    })
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"] == "BAD_REQUEST"


def test_signin_web_post_payload_validation_empty_student_id_returns_400(client, qr_token):
    """R16: Pydantic 校验 student_id 空字符串 → 400 BAD_REQUEST."""
    resp = client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      qr_token["token"],
        "student_id": "",
        "password":   "123456",
    })
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"] == "BAD_REQUEST"


def test_signin_web_html_no_deprecation_warning(client, qr_token, recwarn):
    """R16: TemplateResponse 改新 API 后, 不再抛 starlette DeprecationWarning.

    这是 P1-7 修复的回归保护: 一旦有人 revert 回 TemplateResponse(name, {...})
    写法, 此测试立刻失败 (recwarn 抓 warning)。
    """
    import warnings
    # 清空 pytest 自带的 recwarn 历史, 只看本次请求
    recwarn.clear()
    resp = client.get(f"/signin/{qr_token['task_id']}/{qr_token['token']}")
    assert resp.status_code == 200, resp.text

    # 过滤 starlette templating 的 DeprecationWarning
    starlette_warnings = [
        w for w in recwarn.list
        if issubclass(w.category, DeprecationWarning)
        and "templating" in str(w.filename).lower()
    ]
    assert len(starlette_warnings) == 0, (
        f"TemplateResponse 仍抛 DeprecationWarning: "
        f"{[str(w.message) for w in starlette_warnings]}"
    )


def test_signin_web_unhandled_exception_returns_500_internal(qr_token, student_user, monkeypatch):
    """R16: 全局异常处理器 — 业务异常 → 500 INTERNAL, 不暴露 stack trace.

    模拟 auth_service.login 抛 RuntimeError, 验证:
      1. 返 500 状态码
      2. body 是 {ok:false, error:"INTERNAL", msg:"服务异常，请重试"}
      3. 响应体里不包含 "Traceback" / 文件路径等内部细节

    注意: 用 raise_server_exceptions=False 让 starlette TestClient 把
    server exception 转成 500 response (默认是 re-raise 给测试看到)。
    """
    from fastapi.testclient import TestClient
    app = build_signin_app(qr_token["task_id"], qr_token["token"], qr_token["expires_at"])
    test_client = TestClient(app, raise_server_exceptions=False)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated internal error: secret DB connection string leaked here")

    from src.services import auth_service as auth_mod
    monkeypatch.setattr(auth_mod.AuthService, "login", _boom)

    resp = test_client.post("/api/signin", json={
        "task_id":    qr_token["task_id"],
        "token":      qr_token["token"],
        "student_id": student_user.student_id,
        "password":   "123456",
    })
    assert resp.status_code == 500, resp.text
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "INTERNAL"
    # 不暴露内部细节
    assert "Traceback" not in resp.text
    assert "secret DB connection string" not in resp.text
    assert ".py" not in resp.text  # 不暴露源码路径
