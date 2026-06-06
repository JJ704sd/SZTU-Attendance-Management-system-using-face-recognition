"""
tests/test_leave_service.py — LeaveService 单测
W6 Phase 1: 请假流程 3 路径覆盖
- student_apply 成功 + 失败 (空 reason / 非学生 / 任务已结束 / 重复 pending)
- teacher_review 成功 (approved → record 改 leave; rejected → 状态改)
- teacher_review 失败 (非 teacher/admin / 已处理)
"""
import uuid
from datetime import datetime, timedelta

import pytest

from src.dao.attendance_dao import AttendanceRecordDao
from src.dao.leave_request_dao import LeaveRequestDao
from src.db import session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask, LeaveRequest
from src.models.course import Course
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.leave_service import LeaveError, LeaveService


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def course_teacher_students():
    teacher = AuthService().register(
        username=_uni("t"), password="123456",
        real_name="请假测试老师", role="teacher",
    )
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"), course_name="请假测试课",
            course_type="theory", teacher_id=teacher.id,
        )
        s.add(course); s.flush()
        course_id = course.id

    s1 = AuthService().register(
        username=_uni("s"), password="123456",
        real_name="请假学生1", role="student", student_id=_uni("sid"),
    )
    s2 = AuthService().register(
        username=_uni("s"), password="123456",
        real_name="请假学生2", role="student", student_id=_uni("sid"),
    )
    yield course_id, teacher, [s1, s2]

    student_ids = [s1.id, s2.id]
    with session_scope() as s:
        s.query(LeaveRequest).filter(
            LeaveRequest.student_id.in_(student_ids)
        ).delete(synchronize_session=False)
        s.query(AttendanceRecord).filter(
            AttendanceRecord.student_id.in_(student_ids)
        ).delete(synchronize_session=False)
        s.query(AttendanceTask).filter(
            AttendanceTask.course_id == course_id
        ).delete()
        s.query(Course).filter(Course.id == course_id).delete()
        s.query(User).filter(User.id.in_(student_ids + [teacher.id])).delete()


def _create_open_task(s, course_id, teacher_id):
    now = datetime.now()
    task = AttendanceTask(
        course_id=course_id, teacher_id=teacher_id, classroom_id=1,
        start_time=now, end_time=now + timedelta(hours=1),
        status="open",
    )
    s.add(task); s.flush()
    return task.id


def test_student_apply_success_creates_pending(course_teacher_students):
    course_id, teacher, (s1, _) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)

    req = LeaveService().student_apply(s1.id, task_id, "医院看病")
    assert req.id is not None
    assert req.status == "pending"
    assert req.reason == "医院看病"
    assert req.student_id == s1.id


def test_student_apply_empty_reason_raises(course_teacher_students):
    course_id, teacher, (s1, _) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)
    with pytest.raises(LeaveError, match="不能为空"):
        LeaveService().student_apply(s1.id, task_id, "  ")


def test_student_apply_non_student_raises(course_teacher_students):
    course_id, teacher, _ = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)
    with pytest.raises(LeaveError, match="不是学生"):
        LeaveService().student_apply(teacher.id, task_id, "老师不能请假")


def test_student_apply_closed_task_raises(course_teacher_students):
    course_id, teacher, (s1, _) = course_teacher_students
    with session_scope() as s:
        now = datetime.now()
        task = AttendanceTask(
            course_id=course_id, teacher_id=teacher.id, classroom_id=1,
            start_time=now, end_time=now + timedelta(hours=1),
            status="closed",
        )
        s.add(task); s.flush()
        task_id = task.id
    with pytest.raises(LeaveError, match="已结束"):
        LeaveService().student_apply(s1.id, task_id, "补不了")


def test_student_apply_duplicate_pending_raises(course_teacher_students):
    course_id, teacher, (s1, _) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)
    LeaveService().student_apply(s1.id, task_id, "第一次")
    with pytest.raises(LeaveError, match="已有 pending"):
        LeaveService().student_apply(s1.id, task_id, "重复")


def test_teacher_review_approved_sets_record_to_leave(course_teacher_students):
    course_id, teacher, (s1, _) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)
        # 预先放一条 absent record (模拟 close_task 补的)
        rec = AttendanceRecord(
            task_id=task_id, student_id=s1.id,
            status="absent", sign_in_time=None,
        )
        s.add(rec); s.flush()

    req = LeaveService().student_apply(s1.id, task_id, "医院")
    LeaveService().teacher_review(req.id, teacher.id, approve=True, comment="OK")

    with session_scope() as s:
        rec2 = s.query(AttendanceRecord).filter(
            AttendanceRecord.task_id == task_id,
            AttendanceRecord.student_id == s1.id,
        ).first()
        assert rec2.status == "leave"
        req2 = s.get(LeaveRequest, req.id)
        assert req2.status == "approved"
        assert req2.approver_id == teacher.id
        assert req2.approve_time is not None


def test_teacher_review_rejected_no_record_change(course_teacher_students):
    course_id, teacher, (s1, _) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)
        rec = AttendanceRecord(
            task_id=task_id, student_id=s1.id,
            status="absent", sign_in_time=None,
        )
        s.add(rec); s.flush()

    req = LeaveService().student_apply(s1.id, task_id, "理由不充分")
    LeaveService().teacher_review(req.id, teacher.id, approve=False, comment="不支持")

    with session_scope() as s:
        rec2 = s.query(AttendanceRecord).filter(
            AttendanceRecord.task_id == task_id,
            AttendanceRecord.student_id == s1.id,
        ).first()
        assert rec2.status == "absent"  # 拒绝不改 record
        req2 = s.get(LeaveRequest, req.id)
        assert req2.status == "rejected"


def test_teacher_review_non_teacher_raises(course_teacher_students):
    course_id, teacher, (s1, s2) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)

    req = LeaveService().student_apply(s1.id, task_id, "test")
    # s2 是学生, 不能审批
    with pytest.raises(LeaveError, match="无权审批"):
        LeaveService().teacher_review(req.id, s2.id, approve=True)


def test_teacher_review_already_processed_raises(course_teacher_students):
    course_id, teacher, (s1, _) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)

    req = LeaveService().student_apply(s1.id, task_id, "test")
    LeaveService().teacher_review(req.id, teacher.id, approve=True)
    with pytest.raises(LeaveError, match="已处理"):
        LeaveService().teacher_review(req.id, teacher.id, approve=False)


def test_list_pending_for_task_returns_only_pending(course_teacher_students):
    course_id, teacher, (s1, s2) = course_teacher_students
    with session_scope() as s:
        task_id = _create_open_task(s, course_id, teacher.id)

    r1 = LeaveService().student_apply(s1.id, task_id, "s1 请假")
    r2 = LeaveService().student_apply(s2.id, task_id, "s2 请假")
    # 批准 r1
    LeaveService().teacher_review(r1.id, teacher.id, approve=True)

    pending = LeaveService().list_pending_for_task(task_id)
    assert len(pending) == 1
    assert pending[0].id == r2.id
