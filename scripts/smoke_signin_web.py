"""
scripts/smoke_signin_web.py — W14 多端登录签到 端到端烟测

模拟教师端「📱 二维码签到」全链路:
  1. 注册教师 + 学生 (UUID 后缀)
  2. 教师创建考勤任务 + 生成 qr 签到码
  3. 启动 SigninWebServer (内嵌 uvicorn + FastAPI)
  4. httpx GET 签到页 (URL 是 self.url = http://lan_ip:port/signin/<task>/<token>)
  5. httpx POST /api/signin 用 student_id + password
  6. 验 DB: attendance_record 有 signin_method='qr' 一条
  7. 验 GET /api/signin/status?task=... 拿到 new_records
  8. 停 server, 端口释放
  9. cleanup 测试数据

退出码: 0=PASS / 1=FAIL

用法:
    .venv\Scripts\python.exe scripts\smoke_signin_web.py
"""
import os
import sys
import socket
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# 路径: 必须从项目根 import src.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _section(title: str):
    print(f"\n=== {title} ===", flush=True)


def _ok(msg: str):
    print(f"  [OK] {msg}", flush=True)


def _fail(msg: str):
    print(f"  [FAIL] {msg}", flush=True)


def main() -> int:
    import httpx
    from src.db import session_scope, engine
    from src.models.attendance import AttendanceRecord, AttendanceTask
    from src.models.course import Classroom, Course
    from src.models.user import User
    from src.services.attendance_service import AttendanceService
    from src.services.auth_service import AuthService
    from src.services.signin_web import SigninWebServer
    from src.utils.network import is_port_free
    from sqlalchemy import text

    # ====================================================
    # 1. 注册教师 + 学生
    # ====================================================
    _section("1. 注册教师 + 学生")
    suf = uuid.uuid4().hex[:6]
    auth = AuthService()
    try:
        teacher = auth.register(
            username=f"smkweb_t_{suf}", password="123456",
            real_name="烟测教师", role="teacher",
        )
        _ok(f"teacher id={teacher.id}")
        student = auth.register(
            username=f"smkweb_s_{suf}", password="123456",
            real_name="烟测学生", role="student",
            student_id=f"SWEBS{suf}",
        )
        _ok(f"student id={student.id} student_id={student.student_id}")
    except Exception as e:
        _fail(f"注册失败: {e}")
        return 1

    # ====================================================
    # 2. 创建考勤任务 + 生成 qr 签到码
    # ====================================================
    _section("2. 创建 task + 生成 qr 签到码")
    try:
        with session_scope() as s:
            from src.models.course_enrollment import CourseEnrollment
            course = Course(
                course_code=f"SWEBS{suf}", course_name="W14烟测课",
                course_type="theory", teacher_id=teacher.id,
            )
            s.add(course); s.flush()
            s.add(CourseEnrollment(course_id=course.id, student_id=student.id))
            classroom = Classroom(name=f"烟测教室{suf}")
            s.add(classroom); s.flush()
            course_id, classroom_id = course.id, classroom.id
        att = AttendanceService()
        now = datetime.now()
        task_id = att.create_task(
            course_id=course_id, teacher_id=teacher.id,
            classroom_id=classroom_id,
            start_time=now, end_time=now + timedelta(hours=1),
        )
        _ok(f"task_id={task_id}")

        qr = att.generate_signin_code(task_id, "qr", ttl_seconds=60)
        assert qr is not None
        token = qr["code"]
        _ok(f"qr token={token[:10]}... (len={len(token)}) expires_at={qr['expires_at']}")
    except Exception as e:
        _fail(f"create_task / generate_signin_code 失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 3. 启动 SigninWebServer (选空闲端口避免跟默认 5180 冲突)
    # ====================================================
    _section("3. 启动 SigninWebServer")
    try:
        # 找空闲端口 (允许 reuse TIME_WAIT)
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        _ok(f"选择空闲端口: {port}")

        srv = SigninWebServer(
            task_id=task_id, token=token, expires_at=qr["expires_at"],
            host="127.0.0.1", port=port,
        )
        srv.start()
        _ok(f"server started, url={srv.url}")

        # 等 server 真起来
        deadline = time.time() + 5
        last_err = None
        while time.time() < deadline:
            try:
                r = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1.0)
                if r.status_code == 200:
                    _ok("/api/health 200 OK")
                    break
            except Exception as e:
                last_err = e
                time.sleep(0.1)
        else:
            srv.stop()
            _fail(f"server 5s 内未响应: {last_err}")
            return 1
    except Exception as e:
        _fail(f"SigninWebServer 启动失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 4. GET 签到页 HTML
    # ====================================================
    _section("4. GET 签到页")
    try:
        page_url = f"http://127.0.0.1:{port}/signin/{task_id}/{token}"
        r = httpx.get(page_url, timeout=2.0)
        assert r.status_code == 200, f"签到页 {r.status_code}: {r.text[:200]}"
        body = r.text
        assert "<html" in body.lower()
        assert 'name="student_id"' in body
        assert 'name="password"' in body
        assert str(task_id) in body
        _ok(f"签到页 200 OK, 含表单 + task_id={task_id}")
    except Exception as e:
        srv.stop()
        _fail(f"GET 签到页失败: {e}")
        return 1

    # ====================================================
    # 5. POST /api/signin (正确凭证)
    # ====================================================
    _section("5. POST /api/signin")
    try:
        r = httpx.post(f"http://127.0.0.1:{port}/api/signin", json={
            "task_id": task_id, "token": token,
            "student_id": student.student_id,
            "password": "123456",
        }, timeout=3.0)
        assert r.status_code == 200, f"签到 {r.status_code}: {r.text}"
        data = r.json()
        assert data["ok"] is True, data
        assert data["student_name"] == student.real_name
        assert data["signin_method"] == "qr"
        assert data["status"] in ("present", "late")
        _ok(f"签到成功: status={data['status']}, sign_in_time={data['sign_in_time']}")

        # 5b. 错误 token → 400
        r2 = httpx.post(f"http://127.0.0.1:{port}/api/signin", json={
            "task_id": task_id, "token": "wrong-token-22chars",
            "student_id": student.student_id, "password": "123456",
        }, timeout=3.0)
        assert r2.status_code == 400, r2.text
        assert r2.json()["error"] == "CODE_INVALID"
        _ok(f"错误 token → 400 CODE_INVALID ✓")

        # 5c. 错密码 → 401
        r3 = httpx.post(f"http://127.0.0.1:{port}/api/signin", json={
            "task_id": task_id, "token": token,
            "student_id": student.student_id, "password": "wrongpass",
        }, timeout=3.0)
        assert r3.status_code == 401, r3.text
        assert r3.json()["error"] == "AUTH_FAILED"
        _ok(f"错密码 → 401 AUTH_FAILED ✓")
    except Exception as e:
        srv.stop()
        _fail(f"POST /api/signin 失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 6. 验 DB 有 attendance_record (signin_method='qr')
    # ====================================================
    _section("6. 验 DB")
    try:
        with session_scope() as s:
            rec = s.query(AttendanceRecord).filter(
                AttendanceRecord.task_id == task_id,
                AttendanceRecord.student_id == student.id,
            ).first()
            assert rec is not None, "DB 里没有 record"
            assert rec.signin_method == "qr", f"signin_method={rec.signin_method}"
            _ok(f"DB record: id={rec.id}, status={rec.status}, signin_method={rec.signin_method}")
    except Exception as e:
        srv.stop()
        _fail(f"DB 验证失败: {e}")
        return 1

    # ====================================================
    # 7. GET /api/signin/status
    # ====================================================
    _section("7. GET /api/signin/status")
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/api/signin/status",
                      params={"task": task_id}, timeout=2.0)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert len(data["new_records"]) >= 1
        nr = data["new_records"][0]
        assert nr["student_name"] == student.real_name
        _ok(f"new_records={len(data['new_records'])}, first={nr['student_name']}")
    except Exception as e:
        srv.stop()
        _fail(f"GET /api/signin/status 失败: {e}")
        return 1

    # ====================================================
    # 8. 停 server + 端口释放
    # ====================================================
    _section("8. 停 server + 端口释放")
    try:
        srv.stop(timeout=3.0)
        assert srv.running is False
        _ok(f"server.stop() OK, running={srv.running}")

        # 端口应能立即 bind (SO_REUSEADDR)
        s2 = socket.socket()
        s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s2.bind(("127.0.0.1", port))
            bound_ok = True
        except OSError as e:
            bound_ok = False
            _fail(f"端口 {port} 未释放: {e}")
        s2.close()
        if bound_ok:
            _ok(f"端口 {port} 释放 OK")
    except Exception as e:
        _fail(f"server.stop 异常: {e}")
        return 1

    # ====================================================
    # 9. cleanup 测试数据
    # ====================================================
    _section("9. cleanup")
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM attendance_record WHERE task_id = :tid"
            ), {"tid": task_id})
            conn.execute(text(
                "DELETE FROM attendance_task WHERE id = :tid"
            ), {"tid": task_id})
            conn.execute(text(
                "DELETE FROM task_signin_code WHERE task_id = :tid"
            ), {"tid": task_id})
            conn.execute(text(
                "DELETE FROM course_enrollment WHERE course_id = :cid"
            ), {"cid": course_id})
            conn.execute(text(
                "DELETE FROM course WHERE id = :cid"
            ), {"cid": course_id})
            conn.execute(text(
                "DELETE FROM classroom WHERE id = :rid"
            ), {"rid": classroom_id})
            conn.execute(text(
                "DELETE FROM user WHERE username LIKE :pat"
            ), {"pat": f"smkweb_%_{suf}"})
        _ok("cleanup done")
    except Exception as e:
        _fail(f"cleanup 失败 (不致命): {e}")

    print()
    print("[PASS] W14 多端登录签到全链路 smoke 9 步全过")
    print("       注册 + task + qr码 + server启停 + 签到页 + POST签到")
    print("       + DB验证 + status轮询 + 端口释放 + cleanup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
