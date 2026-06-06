"""
tests/test_attendance_service.py — AttendanceService.close_task_and_mark_absent 单测

W4 Phase 3b 验收:
- 有 course_enrollment: 只补登选课名单里的学生
- 无 course_enrollment: 防御性降级到 role='student' 全部
"""
import uuid
from datetime import datetime, timedelta

import pytest

from src.dao.attendance_dao import AttendanceRecordDao, AttendanceTaskDao
from src.dao.course_enrollment_dao import CourseEnrollmentDao
from src.db import session_scope
from src.models.course import Course
from src.models.user import User
from src.services.attendance_service import AttendanceService
from src.services.auth_service import AuthService


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
        task = AttendanceTaskDao(s).find_by_teacher.__self__ if False else None
    # 直接插入一个 task
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
