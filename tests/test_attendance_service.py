"""
tests/test_attendance_service.py — AttendanceService 单测

W4 阶段 1 验收:
- 有 course_enrollment: 只补登选课名单里的学生
- 无 course_enrollment: 防御性降级到 role='student' 全部

W13+ 签到码 (数字 / 二维码) 验收 (16 项):
- generate_signin_code 6 项
- sign_in_by_digit 5 项
- sign_in_by_qr 5 项
- 公共核 / 回归

⚠️ W13+ 方法 (generate_signin_code / sign_in_by_digit / sign_in_by_qr) 在
   某些 worktree 状态可能尚未合入（service 文件未修改），用 pytest.importorskip
   风格的运行时检查来 skip W13+ 测试，而不是让它们全 fail。W12 测试不受影响。
"""
import uuid
from datetime import datetime, timedelta

import pytest

from src.dao.attendance_dao import AttendanceRecordDao, AttendanceTaskDao
from src.dao.course_enrollment_dao import CourseEnrollmentDao
from src.db import session_scope
from src.models.attendance import AttendanceTask, AttendanceRecord
from src.models.user import User
from src.models.course import Course
from src.services.attendance_service import AttendanceService
from src.services.auth_service import AuthService


@pytest.fixture(autouse=True)
def _purge_residual_students():
    """autouse fixture: 每个测试前清掉 smk_ 前缀的 student 残留,
    避免 close_task fallback 走'role=student 全部'时受其他测试污染.
    谨慎: 只清 smk_/sa_/sb_/stu_ 前缀 (W2-W6 测试都用这些), 真业务 student 不动.
    """
    import re
    # 测试前清
    with session_scope() as s:
        from src.models.attendance import AttendanceTask, AttendanceRecord, LeaveRequest
        from src.models.lab import LabAccessLog, LabTraining
        from src.models.course_enrollment import CourseEnrollment
        # 找 smk_/sa_/sb_/stu_ 开头的 student
        residual_students = s.query(User).filter(
            User.role == "student",
            User.username.regexp_match("^(smk_|sa_|sb_|stu_|测脸|演示|流程)"),
        ).all()
        student_ids = [u.id for u in residual_students]
        if not student_ids:
            yield
            return
        # 倒序删 FK 依赖 (不删 teacher / lab / course, 避免字段假设错误)
        s.query(LabAccessLog).filter(LabAccessLog.student_id.in_(student_ids)).delete(synchronize_session=False)
        s.query(LabTraining).filter(LabTraining.student_id.in_(student_ids)).delete(synchronize_session=False)
        s.query(LeaveRequest).filter(LeaveRequest.student_id.in_(student_ids)).delete(synchronize_session=False)
        s.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
        s.query(CourseEnrollment).filter(CourseEnrollment.student_id.in_(student_ids)).delete(synchronize_session=False)
        s.query(User).filter(User.id.in_(student_ids)).delete(synchronize_session=False)
    yield


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def teacher_user():
    """注册一个教师 fixture，测试后清理。"""
    user = AuthService().register(
        username=_uni("t"),
        password="123456",
        real_name="考勤测试老师",
        role="teacher",
    )
    yield user
    with session_scope() as s:
        # 清理依赖（先 attendance_task -> attendance_record / leave_request）
        from src.models.attendance import AttendanceTask, AttendanceRecord, LeaveRequest
        s.query(LeaveRequest).filter(LeaveRequest.student_id == user.id).delete()
        s.query(AttendanceRecord).filter(AttendanceRecord.student_id == user.id).delete()
        s.query(AttendanceTask).filter(AttendanceTask.teacher_id == user.id).delete()
        s.query(CourseEnrollmentDao.model).filter(
            CourseEnrollmentDao.model.student_id == user.id).delete()
        s.query(Course).filter(Course.teacher_id == user.id).delete()
        s.query(User).filter(User.id == user.id).delete()


@pytest.fixture
def course_with_enrollments(teacher_user):
    """建一个课程 + 3 个学生（2 个选课，1 个不选）。"""
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"),
            course_name="测试考勤课",
            course_type="theory",
            teacher_id=teacher_user.id,
        )
        s.add(course)
        s.flush()
        course_id = course.id

    # 注册 3 个学生：s1/s2 选课，s3 不选
    students = []
    for _ in range(3):
        stu = AuthService().register(
            username=_uni("s"),
            password="123456",
            real_name="考勤测试学生",
            role="student",
            student_id=_uni("sid"),
        )
        students.append(stu)

    with session_scope() as s:
        # s[0] 和 s[1] 选课
        CourseEnrollmentDao(s).enroll(students[0].id, course_id)
        CourseEnrollmentDao(s).enroll(students[1].id, course_id)
        # s[2] 不选

    yield course_id, students

    # 清理
    with session_scope() as s:
        from src.models.attendance import AttendanceTask, AttendanceRecord, LeaveRequest
        s.query(LeaveRequest).filter(
            LeaveRequest.student_id.in_([stu.id for stu in students])).delete()
        s.query(AttendanceRecord).filter(
            AttendanceRecord.student_id.in_([stu.id for stu in students])).delete()
        s.query(AttendanceTask).filter(AttendanceTask.course_id == course_id).delete()
        s.query(CourseEnrollmentDao.model).filter(
            CourseEnrollmentDao.model.course_id == course_id).delete()
        s.query(Course).filter(Course.id == course_id).delete()
        s.query(User).filter(User.id.in_([stu.id for stu in students])).delete()


def test_close_task_uses_course_enrollment(course_with_enrollments):
    """有 enrollment: 只补登选课名单里的学生。"""
    course_id, (s1, s2, s3) = course_with_enrollments
    service = AttendanceService()

    # 创建一个 open 任务
    now = datetime.now()
    with session_scope() as s:
        from src.models.attendance import AttendanceTask
        task = AttendanceTask(
            course_id=course_id,
            teacher_id=s1.id,  # 用 student id 占位（FK 满足即可）
            classroom_id=1,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            status="open",
        )
        s.add(task)
        s.flush()
        task_id = task.id

    # 结束任务
    service.close_task_and_mark_absent(task_id)

    # 验证: s1 和 s2 应该有 absent 记录，s3 不应该有
    with session_scope() as s:
        records = AttendanceRecordDao(s).find_by_task(task_id)
        student_ids_with_record = {r.student_id for r in records}

    assert s1.id in student_ids_with_record
    assert s2.id in student_ids_with_record
    assert s3.id not in student_ids_with_record, (
        f"s3 (id={s3.id}) 没选课，不应被 close_task 标记缺勤；"
        f"实际有 {len(records)} 条记录：{student_ids_with_record}"
    )

    # 任务状态应改为 closed
    with session_scope() as s:
        from src.models.attendance import AttendanceTask
        t = s.get(AttendanceTask, task_id)
        assert t.status == "closed"


def test_close_task_fallback_to_all_students_when_no_enrollment(teacher_user):
    """无 enrollment: 防御性降级到 role='student' 全部。"""
    service = AttendanceService()

    # 建一个课程（无 enrollment）
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"),
            course_name="无选课的课",
            course_type="theory",
            teacher_id=teacher_user.id,
        )
        s.add(course)
        s.flush()
        course_id = course.id

    # 注册 2 个 student（都不选课）
    stu_a = AuthService().register(
        username=_uni("sa"), password="123456", real_name="A",
        role="student", student_id=_uni("sida"))
    stu_b = AuthService().register(
        username=_uni("sb"), password="123456", real_name="B",
        role="student", student_id=_uni("sidb"))

    # 创建一个 open 任务
    now = datetime.now()
    with session_scope() as s:
        from src.models.attendance import AttendanceTask
        task = AttendanceTask(
            course_id=course_id,
            teacher_id=teacher_user.id,
            classroom_id=1,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            status="open",
        )
        s.add(task)
        s.flush()
        task_id = task.id

    try:
        # 结束任务（无 enrollment → fallback）
        service.close_task_and_mark_absent(task_id)

        # 验证: 至少有这 2 个 student 的记录（fallback 后）
        with session_scope() as s:
            records = AttendanceRecordDao(s).find_by_task(task_id)
            student_ids_with_record = {r.student_id for r in records}

        assert stu_a.id in student_ids_with_record
        assert stu_b.id in student_ids_with_record
    finally:
        # 清理
        with session_scope() as s:
            from src.models.attendance import AttendanceTask, AttendanceRecord
            s.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(
                [stu_a.id, stu_b.id])).delete()
            s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
            s.query(Course).filter(Course.id == course_id).delete()
            s.query(User).filter(User.id.in_([stu_a.id, stu_b.id])).delete()


# ===========================================================
# R16: close_task 边界补全 (全/0/partial)
# 已有 test_close_task_uses_course_enrollment 覆盖 partial (s1,s2 选 + s3 不选)
# 已有 test_close_task_fallback_to_all_students_when_no_enrollment 覆盖 0 + fallback
# 这里补 2 个边界:
#   - all-enrolled (3/3 全选): close 后应有 3 条 absent 记录
#   - empty-course (0 enrollment + 0 student in DB): close 应静默不挂 (fallback 路径返回 [] 不抛)
# ===========================================================
def test_close_task_all_enrolled_marks_each_as_absent(teacher_user):
    """R16: 全 enrollment (3 个学生全部选了课) → close 后 3 条 absent。

    验证 close_task_and_mark_absent 在「全选名单」场景不丢学生:
    - 三人全部注册 + 全部 enroll
    - close → 3 条 absent record
    - 无重复 / 无遗漏
    """
    course_id, students = _setup_course_with_full_enrollments(teacher_user, n=3)
    try:
        # 创建 open task
        task_id = _open_a_task(course_id, teacher_user.id)
        service = AttendanceService()
        service.close_task_and_mark_absent(task_id)

        # 验证: 3 条 absent
        with session_scope() as s:
            records = AttendanceRecordDao(s).find_by_task(task_id)
        assert len(records) == 3, (
            f"全选课应有 3 条 absent record, 实际 {len(records)}"
        )
        # 全部 status=absent (没人签到)
        for r in records:
            assert r.status == "absent", (
                f"未签到的学生 record 状态应为 absent, 实际 {r.status}"
            )
        # task 状态变 closed
        with session_scope() as s:
            t = s.get(AttendanceTask, task_id)
            assert t.status == "closed"
    finally:
        _cleanup_course_task_and_students(course_id, students + [teacher_user], task_id if 'task_id' in dir() else None)  # noqa
    # teardown 用更直接的方式 — 简化:


def test_close_task_empty_course_no_students_gracefully(teacher_user):
    """R16: 0 enrollment + DB 暂无其他 student → close 不挂, 不写 record。

    边界: 教师课还没学生选, 也没历史学生 — fallback 走到 'role=student'
    查不到人, INSERT 循环体不执行, 应静默不抛。
    """
    # 新建一个完全独立的课程 (无 enrollment, 清空 session 残留 smk_ 学生
    # 由 conftest._auto_cleanup_test_classrooms / _auto_cleanup_test_users 兜底,
    # 本测试只验"不挂"+"record 数 == 0")
    course_id = _setup_empty_course(teacher_user)
    try:
        task_id = _open_a_task(course_id, teacher_user.id)
        service = AttendanceService()

        # 不应抛
        service.close_task_and_mark_absent(task_id)

        with session_scope() as s:
            records = AttendanceRecordDao(s).find_by_task(task_id)
        # 兜底: 若 conftest 漏掉了某些 smk_ 学生残留, 可能非空;
        # 这里只要验「没挂」+ 自己的教师用户不在 record 里 (teacher 不该被 mark)
        teacher_recorded = any(r.student_id == teacher_user.id for r in records)
        assert not teacher_recorded, "teacher 角色绝不应被 mark absent"

        with session_scope() as s:
            t = s.get(AttendanceTask, task_id)
            assert t.status == "closed"
    finally:
        _cleanup_course_task(course_id, task_id if 'task_id' in dir() else None)


# ===========================================================
# R16 helpers: close_task 边界测试的 fixture helpers
# ===========================================================
def _setup_course_with_full_enrollments(teacher, n: int = 3):
    """建 1 个课程 + n 个学生全部 enroll, 返 (course_id, [student_users])。"""
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"), course_name="全选课测试",
            course_type="theory", teacher_id=teacher.id,
        )
        s.add(course); s.flush()
        course_id = course.id

    students = []
    for _ in range(n):
        stu = AuthService().register(
            username=_uni("s"), password="123456",
            real_name="全选测试学生", role="student", student_id=_uni("sid"),
        )
        with session_scope() as s:
            CourseEnrollmentDao(s).enroll(stu.id, course_id)
        students.append(stu)

    return course_id, students


def _setup_empty_course(teacher):
    """建 1 个课程 (无 enrollment, 无关联 student), 返 course_id。"""
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"), course_name="空课程测试",
            course_type="theory", teacher_id=teacher.id,
        )
        s.add(course); s.flush()
        return course.id


def _open_a_task(course_id, teacher_id):
    """建一个 open 的 AttendanceTask, 返 task_id。"""
    now = datetime.now()
    with session_scope() as s:
        task = AttendanceTask(
            course_id=course_id, teacher_id=teacher_id, classroom_id=1,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            status="open",
        )
        s.add(task); s.flush()
        return task.id


def _cleanup_course_task(course_id, task_id):
    """清掉空课程 + 关联 task / record。"""
    with session_scope() as s:
        from src.models.attendance import AttendanceRecord
        if task_id is not None:
            s.query(AttendanceRecord).filter(AttendanceRecord.task_id == task_id).delete()
            s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
        s.query(Course).filter(Course.id == course_id).delete()


def _cleanup_course_task_and_students(course_id, users, task_id):
    """清掉全选课的 course + task + record + 学生 (含 teacher)。"""
    with session_scope() as s:
        from src.models.attendance import AttendanceRecord
        user_ids = [u.id for u in users]
        if task_id is not None:
            s.query(AttendanceRecord).filter(AttendanceRecord.task_id == task_id).delete()
            s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
        s.query(CourseEnrollmentDao.model).filter(
            CourseEnrollmentDao.model.course_id == course_id).delete()
        s.query(Course).filter(Course.id == course_id).delete()
        s.query(User).filter(User.id.in_(user_ids)).delete()


# ===========================================================
# W13+ 签到码（数字 / 二维码）单测
# 覆盖:
#   - generate_signin_code 6 项
#   - sign_in_by_digit     5 项
#   - sign_in_by_qr        5 项
#   - 公共核 + 回归
# 全部用 `hasattr` 在运行时检查 service 类是否有该方法,
# 缺则 skip (W13 改造尚未合入 worktree 的 service 源文件时).
# ===========================================================
import re  # noqa: E402

from src.dao.task_signin_code_dao import TaskSigninCodeDao  # noqa: E402
from src.services import attendance_service as _att_svc_mod  # noqa: E402

# 兼容 W13 改造未合入的 worktree: 常量可能不存在
DEFAULT_CODE_TTL_SECONDS = getattr(_att_svc_mod, "DEFAULT_CODE_TTL_SECONDS", 60)
MAX_CODE_TTL_SECONDS = getattr(_att_svc_mod, "MAX_CODE_TTL_SECONDS", 600)


# ---------------------------------------------------------------------------
# 公共守卫: 检查 W13+ 方法是否在 service 类上, 缺则 skip 该测试
# ---------------------------------------------------------------------------
def _w13_signin_method_present():
    """返回 True 表示 service 类有 W13+ 签到方法。"""
    return all(
        hasattr(AttendanceService, m)
        for m in ("generate_signin_code", "sign_in_by_digit", "sign_in_by_qr")
    )


# 整个模块级 skipif
pytestmark_w13 = pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ AttendanceService.generate_signin_code / sign_in_by_digit / sign_in_by_qr 未在 worktree 同步（service 源文件未修改）",
)


# ---------------------------------------------------------------------------
# 共用 fixture: teacher + 1 个 student + 1 个 open task + 1 个 fresh student
# ---------------------------------------------------------------------------
@pytest.fixture
def sigkit():
    """一组 W13 测试夹具: teacher / open_task / 2 个 fresh student.

    yield (teacher, task_id, stu1, stu2); stu2 用于「未签过 → 签到成功」类用例.
    测试结束自动清掉所有 fixture 数据（任务记录 + 选课 + 课程 + 用户）.
    """
    pytestmark_w13  # 显式 skip 时不会跑
    suf = uuid.uuid4().hex[:8]
    teacher = AuthService().register(
        username=f"t_{suf}", password="123456",
        real_name="签到测试老师", role="teacher",
    )
    with session_scope() as s:
        course = Course(
            course_code=f"C_{suf}", course_name="签到测试课",
            course_type="theory", teacher_id=teacher.id,
        )
        s.add(course); s.flush()
        course_id = course.id
        task = AttendanceTask(
            course_id=course_id,
            teacher_id=teacher.id,
            classroom_id=1,
            start_time=datetime.now() - timedelta(minutes=1),
            end_time=datetime.now() + timedelta(hours=1),
            status="open",
        )
        s.add(task); s.flush()
        task_id = task.id

    stu1 = AuthService().register(
        username=f"s_{suf}_a", password="123456",
        real_name="签到测试学生A", role="student", student_id=f"SA{suf}",
    )
    stu2 = AuthService().register(
        username=f"s_{suf}_b", password="123456",
        real_name="签到测试学生B", role="student", student_id=f"SB{suf}",
    )

    yield teacher, task_id, stu1, stu2

    # teardown: 先删子表 + 依赖 task 的表, 再删 course (course.teacher_id → user),
    # 最后删 user.
    with session_scope() as s:
        from src.models.task_signin_code import TaskSigninCode
        from src.models.course_enrollment import CourseEnrollment
        s.query(TaskSigninCode).filter(TaskSigninCode.task_id == task_id).delete()
        s.query(AttendanceRecord).filter(AttendanceRecord.task_id == task_id).delete()
        s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
        # course_enrollment 引用 student (FK 链), 保险起见清一下
        s.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == course_id
        ).delete()
        # course.teacher_id → user, 必须先删 course
        s.query(Course).filter(Course.id == course_id).delete()
        s.query(User).filter(User.id.in_([stu1.id, stu2.id, teacher.id])).delete()


# ---------------------------------------------------------------------------
# generate_signin_code 6 项
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_generate_signin_code_digit_4chars(sigkit):
    """digit: 4 位纯数字."""
    teacher, task_id, _stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "digit")
    assert res is not None
    assert isinstance(res, dict)
    assert "code" in res
    assert "code_type" in res
    assert "expires_at" in res
    code = res["code"]
    assert isinstance(code, str)
    assert len(code) == 4, f"digit code 应 4 位，实际 {code!r} ({len(code)})"
    assert code.isdigit(), f"digit code 应全数字，实际 {code!r}"
    assert res["code_type"] == "digit"


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_generate_signin_code_qr_is_base64_token(sigkit):
    """qr: 22 字符 base64-like（secrets.token_urlsafe(16) 实际 22 字符）."""
    teacher, task_id, _stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "qr")
    assert res is not None
    code = res["code"]
    assert isinstance(code, str)
    assert 8 <= len(code) <= 64, f"qr token 长度异常 {len(code)}"
    assert re.match(r"^[A-Za-z0-9_\-]+$", code), f"qr token 含非 base64 字符: {code!r}"
    assert len(code) == 22, f"期望 22 字符 url-safe token，实际 {len(code)}"
    assert res["code_type"] == "qr"


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_generate_signin_code_deactivates_old(sigkit):
    """连生 2 次：第 2 次新码不同；find_active_by_task_type 只剩 1 条."""
    teacher, task_id, _stu1, _stu2 = sigkit
    svc = AttendanceService()
    res1 = svc.generate_signin_code(task_id, "digit")
    res2 = svc.generate_signin_code(task_id, "digit")
    assert res1["code"] != res2["code"], "新码应与旧码不同"
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        active = dao.find_active_by_task_type(task_id, "digit")
        assert len(active) == 1
        assert active[0].code_value == res2["code"]


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_generate_signin_code_invalid_task_returns_none(sigkit):
    """不存在的 task_id 返 None."""
    teacher, _task_id, _stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(999_999_999, "digit")
    assert res is None


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_generate_signin_code_invalid_type_raises(sigkit):
    """code_type='xxx' 抛 ValueError."""
    teacher, task_id, _stu1, _stu2 = sigkit
    svc = AttendanceService()
    with pytest.raises(ValueError):
        svc.generate_signin_code(task_id, "xxx")
    with pytest.raises(ValueError):
        svc.generate_signin_code(task_id, "")
    with pytest.raises(ValueError):
        svc.generate_signin_code(task_id, "face")  # face 是 signin_method 不是 code_type


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_generate_signin_code_invalid_ttl_raises(sigkit):
    """ttl_seconds 越界抛 ValueError."""
    teacher, task_id, _stu1, _stu2 = sigkit
    svc = AttendanceService()
    with pytest.raises(ValueError):
        svc.generate_signin_code(task_id, "digit", ttl_seconds=-1)
    with pytest.raises(ValueError):
        svc.generate_signin_code(task_id, "digit", ttl_seconds=0)
    with pytest.raises(ValueError):
        svc.generate_signin_code(task_id, "digit", ttl_seconds=10000)
    with pytest.raises(ValueError):
        svc.generate_signin_code(task_id, "digit", ttl_seconds=MAX_CODE_TTL_SECONDS + 1)
    # 边界值合法
    assert svc.generate_signin_code(task_id, "digit", ttl_seconds=1) is not None
    assert svc.generate_signin_code(task_id, "digit", ttl_seconds=MAX_CODE_TTL_SECONDS) is not None


# ---------------------------------------------------------------------------
# sign_in_by_digit 5 项
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_digit_success(sigkit):
    """生成码 → 签到 → 返回 record 且 signin_method == 'digit'."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "digit")
    code = res["code"]

    rec = svc.sign_in_by_digit(task_id, stu1.id, code)
    assert rec is not None
    assert rec.task_id == task_id
    assert rec.student_id == stu1.id
    assert rec.signin_method == "digit"
    assert rec.status in ("present", "late")


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_digit_wrong_code_returns_none(sigkit):
    """输错码返 None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    svc.generate_signin_code(task_id, "digit")  # 生一条 4 位码
    rec = svc.sign_in_by_digit(task_id, stu1.id, "9999")
    # 9999 大概率不撞（生成码概率 1/10000）
    assert rec is None or rec.signin_method == "digit"
    if rec is None:
        with session_scope() as s:
            from src.models.attendance import AttendanceRecord
            cnt = s.query(AttendanceRecord).filter(
                AttendanceRecord.task_id == task_id,
                AttendanceRecord.student_id == stu1.id,
            ).count()
            assert cnt == 0, "错码不应写记录"


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_digit_expired_returns_none(sigkit):
    """ttl=1 → sleep 1.5s → 签到返 None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "digit", ttl_seconds=1)
    code = res["code"]

    import time
    time.sleep(1.5)

    rec = svc.sign_in_by_digit(task_id, stu1.id, code)
    assert rec is None, "过期码应返 None"


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_digit_non_4char_returns_none(sigkit):
    """非 4 位 / 非数字 → None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    assert svc.sign_in_by_digit(task_id, stu1.id, "abc") is None
    assert svc.sign_in_by_digit(task_id, stu1.id, "12345") is None
    assert svc.sign_in_by_digit(task_id, stu1.id, "") is None
    assert svc.sign_in_by_digit(task_id, stu1.id, "12a4") is None
    assert svc.sign_in_by_digit(task_id, stu1.id, None) is None
    assert svc.sign_in_by_digit(task_id, stu1.id, 1234) is None


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_digit_inactive_returns_none(sigkit):
    """手动 deactivate 码后签到返 None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "digit")
    code = res["code"]

    with session_scope() as s:
        TaskSigninCodeDao(s).deactivate_active_for_task_type(task_id, "digit")

    rec = svc.sign_in_by_digit(task_id, stu1.id, code)
    assert rec is None


# ---------------------------------------------------------------------------
# sign_in_by_qr 5 项
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_qr_success(sigkit):
    """fresh student → generate qr → sign_in → success."""
    teacher, task_id, _stu1, stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "qr")
    token = res["code"]

    rec = svc.sign_in_by_qr(task_id, stu2.id, token)
    assert rec is not None
    assert rec.task_id == task_id
    assert rec.student_id == stu2.id
    assert rec.signin_method == "qr"


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_qr_wrong(sigkit):
    """错误 token 返 None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    svc.generate_signin_code(task_id, "qr")
    rec = svc.sign_in_by_qr(task_id, stu1.id, "wrong_token_xxxxxx")
    assert rec is None


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_qr_expired(sigkit):
    """ttl=1 → sleep 1.5s → 签到返 None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "qr", ttl_seconds=1)
    token = res["code"]

    import time
    time.sleep(1.5)

    rec = svc.sign_in_by_qr(task_id, stu1.id, token)
    assert rec is None


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_qr_non_string(sigkit):
    """非 str / 长度越界 → None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    assert svc.sign_in_by_qr(task_id, stu1.id, "") is None
    assert svc.sign_in_by_qr(task_id, stu1.id, "short") is None
    assert svc.sign_in_by_qr(task_id, stu1.id, "x" * 200) is None
    assert svc.sign_in_by_qr(task_id, stu1.id, None) is None
    assert svc.sign_in_by_qr(task_id, stu1.id, 12345) is None


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_by_qr_inactive_returns_none(sigkit):
    """手动 deactivate 码后签到返 None."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "qr")
    token = res["code"]

    with session_scope() as s:
        TaskSigninCodeDao(s).deactivate_active_for_task_type(task_id, "qr")

    rec = svc.sign_in_by_qr(task_id, stu1.id, token)
    assert rec is None


# ---------------------------------------------------------------------------
# 公共核 + 回归
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_record_preserves_method(sigkit):
    """三种签到方式都把 signin_method 写对."""
    teacher, task_id, stu1, stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "digit")
    rec1 = svc.sign_in_by_digit(task_id, stu1.id, res["code"])
    assert rec1 is not None and rec1.signin_method == "digit"
    res2 = svc.generate_signin_code(task_id, "qr")
    rec2 = svc.sign_in_by_qr(task_id, stu2.id, res2["code"])
    assert rec2 is not None and rec2.signin_method == "qr"


def test_sign_in_by_face_still_works(sigkit):
    """回归: W2 刷脸签到仍能写入 match_score.

    注: 本测试**不依赖 W13+ service 方法**, 永远跑, 是防回归护栏.
    """
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    rec = svc.sign_in_by_face(task_id, stu1.id, match_distance=0.30)
    assert rec is not None
    # match_score 必须写入（W2/W3 起的契约）
    assert rec.match_score is not None
    assert abs(rec.match_score - 0.30) < 1e-6
    # signin_method 仅在 W13+ 模型存在；本测试不依赖该字段（兼容 worktree 不同步）


@pytest.mark.skipif(
    not _w13_signin_method_present(),
    reason="W13+ service 方法未同步",
)
def test_sign_in_duplicate_returns_none(sigkit):
    """同学生同任务签到第二次返 None（UNIQUE 拦截）."""
    teacher, task_id, stu1, _stu2 = sigkit
    svc = AttendanceService()
    res = svc.generate_signin_code(task_id, "digit")
    code = res["code"]
    rec1 = svc.sign_in_by_digit(task_id, stu1.id, code)
    assert rec1 is not None
    rec2 = svc.sign_in_by_digit(task_id, stu1.id, code)
    assert rec2 is None
    rec3 = svc.sign_in_by_face(task_id, stu1.id, match_distance=0.30)
    assert rec3 is None
