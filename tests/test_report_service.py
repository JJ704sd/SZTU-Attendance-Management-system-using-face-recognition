"""
tests/test_report_service.py — ReportService 4 个方法单测

W4 Phase 3d 验收: 4 个方法各 1-2 个测试
- attendance_rate_per_student
- attendance_trend_per_course
- lab_usage_rate
- absent_warning_list

注意:
- attendance_record 有 (task_id, student_id) UNIQUE 约束 → 每个 (task, student)
  只能 1 条 record。要测试"多种状态"必须用多个 task。
- fixture teardown 顺序：先删依赖（record/task/course/enrollment）再删 user，
  否则 FK 反向阻止删 user。
"""
import uuid
from datetime import datetime, timedelta

import pytest

from src.dao.attendance_dao import AttendanceRecordDao, AttendanceTaskDao
from src.dao.lab_access_log_dao import LabAccessLogDao
from src.dao.lab_dao import LabDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask
from src.models.course import Course, Laboratory
from src.models.lab import LabAccessLog
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.report_service import ReportService


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def course_and_students():
    """建一个课程 + 3 个学生，测试后清理（先删依赖再删 user）。"""
    teacher = AuthService().register(
        username=_uni("t"), password="123456", real_name="报表测试老师",
        role="teacher",
    )
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"),
            course_name="报表测试课",
            course_type="theory",
            teacher_id=teacher.id,
        )
        s.add(course)
        s.flush()
        course_id = course.id

    students = []
    for i in range(3):
        stu = AuthService().register(
            username=_uni("s"), password="123456",
            real_name=f"报表学生{i}",
            role="student", student_id=_uni("sid"),
        )
        students.append(stu)

    yield course_id, students, teacher

    # 清理顺序：先删 record/task → course → user
    student_ids = [stu.id for stu in students]
    with session_scope() as s:
        s.query(AttendanceRecord).filter(
            AttendanceRecord.student_id.in_(student_ids)
        ).delete(synchronize_session=False)
        s.query(AttendanceTask).filter(AttendanceTask.course_id == course_id).delete()
        s.query(Course).filter(Course.id == course_id).delete()
        s.query(User).filter(User.id.in_(student_ids + [teacher.id])).delete()


def _create_task(s, course_id, teacher_id, start_offset_days=-2):
    """建一个 task（默认 2 天前开始）"""
    now = datetime.now()
    task = AttendanceTask(
        course_id=course_id,
        teacher_id=teacher_id,
        classroom_id=1,
        start_time=now + timedelta(days=start_offset_days),
        end_time=now + timedelta(days=start_offset_days, hours=1),
        status="closed",
    )
    s.add(task)
    s.flush()
    return task.id


def _create_record(s, task_id, student_id, status, sign_in_time=None):
    """建一条 record（每个 task+student 唯一）"""
    record = AttendanceRecord(
        task_id=task_id,
        student_id=student_id,
        sign_in_time=sign_in_time,
        status=status,
    )
    s.add(record)
    s.flush()
    return record.id


def test_attendance_rate_per_student_no_data_returns_empty():
    """空数据 → []"""
    result = ReportService().attendance_rate_per_student(course_id=99999999)
    assert result == []


def test_attendance_rate_per_student_computes_correctly(course_and_students):
    """3 个学生跨 3 个 task 的混合状态:
    - s1: 3/3 present → 100%
    - s2: 1 present + 2 absent → 33%
    - s3: 1 absent → 0%
    排序按 rate DESC
    """
    course_id, (s1, s2, s3), teacher = course_and_students
    with session_scope() as s:
        # 3 个 task
        t1 = _create_task(s, course_id, teacher.id, -3)
        t2 = _create_task(s, course_id, teacher.id, -2)
        t3 = _create_task(s, course_id, teacher.id, -1)
        # s1: 3 present
        _create_record(s, t1, s1.id, "present", sign_in_time=datetime.now() - timedelta(days=3))
        _create_record(s, t2, s1.id, "present", sign_in_time=datetime.now() - timedelta(days=2))
        _create_record(s, t3, s1.id, "present", sign_in_time=datetime.now() - timedelta(days=1))
        # s2: 1 present + 2 absent
        _create_record(s, t1, s2.id, "present", sign_in_time=datetime.now() - timedelta(days=3))
        _create_record(s, t2, s2.id, "absent")
        _create_record(s, t3, s2.id, "absent")
        # s3: 1 absent
        _create_record(s, t1, s3.id, "absent")

    result = ReportService().attendance_rate_per_student(course_id=course_id)
    # 排序按 rate DESC: s1 (1.0), s2 (0.333), s3 (0.0)
    assert len(result) == 3
    assert result[0].student_id == s1.id
    assert result[0].rate == 1.0
    assert result[1].student_id == s2.id
    assert abs(result[1].rate - 1/3) < 1e-6
    assert result[2].student_id == s3.id
    assert result[2].rate == 0.0


def test_attendance_trend_per_course_groups_by_day(course_and_students):
    """跨多天的 record 按日聚合出勤率"""
    course_id, (s1, s2, _s3), teacher = course_and_students
    with session_scope() as s:
        # 第 1 天: 1 present, 1 absent → 0.5
        t1 = _create_task(s, course_id, teacher.id, -2)
        _create_record(s, t1, s1.id, "present",
                       sign_in_time=datetime.now() - timedelta(days=2))
        _create_record(s, t1, s2.id, "absent")
        # 第 2 天: 2 present → 1.0
        t2 = _create_task(s, course_id, teacher.id, -1)
        _create_record(s, t2, s1.id, "present",
                       sign_in_time=datetime.now() - timedelta(days=1))
        _create_record(s, t2, s2.id, "present",
                       sign_in_time=datetime.now() - timedelta(days=1))

    result = ReportService().attendance_trend_per_course(course_id, days=30)
    assert len(result) == 2
    # 按时间升序
    assert abs(result[0].rate - 0.5) < 1e-6
    assert abs(result[1].rate - 1.0) < 1e-6


def test_lab_usage_rate_groups_by_hour():
    """准入日志按 (date, hour) 聚合，只算放行"""
    service = ReportService()
    student = AuthService().register(
        username=_uni("s"), password="123456", real_name="准入测试",
        role="student", student_id=_uni("sid"),
    )
    with session_scope() as s:
        lab = Laboratory(name=_uni("L"), safety_level=2, required_training="设备")
        s.add(lab)
        s.flush()
        lab_id = lab.id

    try:
        # 用 raw SQL 控 access_time（DAO log_attempt 不支持 access_time 入参）
        now = datetime.now()
        with session_scope() as s:
            from sqlalchemy import text
            hour1 = now.hour
            hour2 = (now.hour - 2) % 24
            # 3 条放行（同小时 2 条 + 异小时 1 条）+ 1 条拒绝
            for t in [(now.replace(hour=hour1, minute=0, second=0, microsecond=0), 1),
                      (now.replace(hour=hour1, minute=0, second=0, microsecond=0), 1),
                      (now.replace(hour=hour2, minute=0, second=0, microsecond=0), 1),
                      (now.replace(hour=hour1, minute=0, second=0, microsecond=0), 0)]:
                t_time, granted = t
                s.execute(text(
                    "INSERT INTO lab_access_log (student_id, lab_id, access_time, granted, reason) "
                    "VALUES (:sid, :lid, :t, :g, 'test')"
                ), {"sid": student.id, "lid": lab_id, "t": t_time, "g": granted})

        result = service.lab_usage_rate(lab_id, days=1)
        # 3 条放行：hour1 = 2 次, hour2 = 1 次
        assert sum(p.count for p in result) == 3
        hours = {p.hour: p.count for p in result}
        assert hours[hour1] == 2
        assert hours[hour2] == 1
    finally:
        with session_scope() as s:
            s.query(LabAccessLog).filter(LabAccessLog.lab_id == lab_id).delete()
            s.query(Laboratory).filter(Laboratory.id == lab_id).delete()
            s.query(User).filter(User.id == student.id).delete()


def test_absent_warning_list_filters_by_threshold(course_and_students):
    """threshold=0.8 时，出勤率<80% 的学生被预警"""
    course_id, (s1, s2, s3), teacher = course_and_students
    with session_scope() as s:
        # s1: 100% 出勤（3 present）
        t1 = _create_task(s, course_id, teacher.id, -3)
        t2 = _create_task(s, course_id, teacher.id, -2)
        t3 = _create_task(s, course_id, teacher.id, -1)
        _create_record(s, t1, s1.id, "present", sign_in_time=datetime.now() - timedelta(days=3))
        _create_record(s, t2, s1.id, "present", sign_in_time=datetime.now() - timedelta(days=2))
        _create_record(s, t3, s1.id, "present", sign_in_time=datetime.now() - timedelta(days=1))
        # s2: 1 present + 2 absent = 33%
        _create_record(s, t1, s2.id, "present", sign_in_time=datetime.now() - timedelta(days=3))
        _create_record(s, t2, s2.id, "absent")
        _create_record(s, t3, s2.id, "absent")
        # s3: 1 absent = 0%
        _create_record(s, t1, s3.id, "absent")

    warnings = ReportService().absent_warning_list(threshold=0.8)
    student_ids = {w.student_id for w in warnings}
    assert s1.id not in student_ids
    assert s2.id in student_ids
    assert s3.id in student_ids
    # 排序按 rate 升序（最差排前）
    assert warnings[0].student_id == s3.id
    assert warnings[1].student_id == s2.id
    assert all(w.course_name == "（全部课程）" for w in warnings)
