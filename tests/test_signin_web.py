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
    """URL 里 task_id/token 与预期不符 → 400 (而非 500)."""
    resp = client.get("/signin/999999/not-the-real-token")
    assert resp.status_code == 400
    assert "签到码" in resp.text or "失效" in resp.text


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
