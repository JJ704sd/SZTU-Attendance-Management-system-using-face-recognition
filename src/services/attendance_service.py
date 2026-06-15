"""
services/attendance_service.py — 考勤任务与签到服务

W13+ 改造：抽公共核 `_create_record`，把三种签到方式（刷脸 / 数字码 / 二维码）
的业务规则（迟到判定 + 重复拦截 + 角色校验 + 记录写入）合并到一处。

- sign_in_by_face(task_id, user_id, match_distance)  —— 刷脸
- sign_in_by_digit(task_id, user_id, code_value)     —— 数字码
- sign_in_by_qr(task_id, user_id, qr_token)           —— 二维码 token

公共校验（边界检查）:
  - task 必须存在 + status='open'
  - user 必须存在 + role='student'（避免 FK 1452 抛出）
  - 同任务同学生 UNIQUE 拦截，返回 None（不抛异常，由 UI 解释）

教师端:
  - generate_signin_code(task_id, code_type, ttl_seconds=60)
    失效旧码 + 写新码，返回 dict {code, expires_at}
"""
from datetime import datetime, timedelta
import random
import secrets
from typing import Optional

from sqlalchemy import and_

from src.db import session_scope
from src.models.attendance import AttendanceTask, AttendanceRecord, LeaveRequest
from src.models.task_signin_code import TaskSigninCode
from src.models.user import User

# 迟到判定：开始时间后 10 分钟
LATE_THRESHOLD_MINUTES = 10

# 签到码默认 TTL：60 秒（够学生看码 → 敲 4 位 / 扫码 → 提交）
DEFAULT_CODE_TTL_SECONDS = 60

# 签到码最长 TTL：10 分钟（超过这个值「教师忘了刷新」风险大）
MAX_CODE_TTL_SECONDS = 600


class AttendanceService:
    def __init__(self):
        pass  # 每个方法内部用 session_scope

    # -----------------------------------------------------
    # 教师创建考勤任务
    # -----------------------------------------------------
    def create_task(self, course_id: int, teacher_id: int, classroom_id: int,
                    start_time: datetime, end_time: datetime) -> int:
        """返回新任务 id"""
        if end_time <= start_time:
            raise ValueError("结束时间必须晚于开始时间")
        if start_time < datetime.now() - timedelta(minutes=5):
            raise ValueError("开始时间不能早于当前 5 分钟以前")

        with session_scope() as s:
            task = AttendanceTask(
                course_id=course_id,
                teacher_id=teacher_id,
                classroom_id=classroom_id,
                start_time=start_time,
                end_time=end_time,
                status="open",
            )
            s.add(task)
            s.flush()
            return task.id

    # -----------------------------------------------------
    # 公共核：所有签到方式最终都走这里
    # -----------------------------------------------------
    def _create_record(self, task_id: int, user_id: int,
                       signin_method: str,
                       match_score: Optional[float] = None) -> Optional[AttendanceRecord]:
        """统一的「写一条考勤记录」入口。

        边界校验（在这里集中维护，三种签到方式都过这一关）：
          1) task 存在 + status='open'          —— 否则返 None
          2) user 存在 + role='student'         —— 否则返 None（防御 FK 1452）
          3) 已签到（同 task + student）        —— 返 None
          4) 迟到判定：present/late

        入参：
          signin_method: 'face' / 'digit' / 'qr'
          match_score: 仅 'face' 有效；数字码 / 二维码传 None
        """
        if signin_method not in ("face", "digit", "qr"):
            raise ValueError(f"signin_method 必须是 face/digit/qr，收到 {signin_method!r}")

        with session_scope() as s:
            task = s.get(AttendanceTask, task_id)
            if not task or task.status != "open":
                return None

            from src.dao.user_dao import UserDao
            user = UserDao(s).get(user_id)
            if not user or user.role != "student":
                return None

            existed = s.query(AttendanceRecord).filter(
                and_(AttendanceRecord.task_id == task_id,
                     AttendanceRecord.student_id == user_id)
            ).first()
            if existed:
                return None

            now = datetime.now()
            late_cutoff = task.start_time + timedelta(minutes=LATE_THRESHOLD_MINUTES)
            status = "present" if now <= late_cutoff else "late"

            record = AttendanceRecord(
                task_id=task_id,
                student_id=user_id,
                sign_in_time=now,
                status=status,
                match_score=match_score,
                signin_method=signin_method,
            )
            s.add(record)
            s.flush()
            s.refresh(record)
            s.expunge(record)
            return record

    # -----------------------------------------------------
    # 刷脸签到（W2 已有，保持向后兼容）
    # -----------------------------------------------------
    def sign_in_by_face(self, task_id: int, user_id: int,
                        match_distance: float) -> Optional[AttendanceRecord]:
        return self._create_record(task_id, user_id, "face", match_distance)

    # -----------------------------------------------------
    # 数字码签到（W13+）
    # -----------------------------------------------------
    def sign_in_by_digit(self, task_id: int, user_id: int,
                         code_value: str) -> Optional[AttendanceRecord]:
        """学生端提交 4 位数字码。

        边界校验：
          1) code_value 必须是 4 位纯数字         —— 否则返 None（不抛，UI 提示「码格式错」）
          2) 在 DAO 层校验 is_active=1 + 未过期 + 一致 —— 不满足返 None（UI 提示「码无效或已过期」）
          3) 写记录走 _create_record 公共核
        """
        if not isinstance(code_value, str) or len(code_value) != 4 or not code_value.isdigit():
            return None

        with session_scope() as s:
            from src.dao.task_signin_code_dao import TaskSigninCodeDao
            code = TaskSigninCodeDao(s).find_active_by_value(task_id, "digit", code_value)
            if not code:
                return None
            # 走到这里说明码有效；_create_record 会另开 session（独立事务），
            # 但我们要在同一个 session 内完成「校验 + 写记录」原子性，所以这里
            # 直接走简化的内部路径：
            return self._create_record_in_session(
                s, task_id, user_id, "digit", match_score=None,
            )

    # -----------------------------------------------------
    # 二维码签到（W13+）
    # -----------------------------------------------------
    def sign_in_by_qr(self, task_id: int, user_id: int,
                      qr_token: str) -> Optional[AttendanceRecord]:
        """学生端提交二维码 token（22 字符 base64）。

        边界校验：
          1) qr_token 必须是非空字符串且长度合理（防垃圾输入）
          2) DAO 层校验有效性
          3) 写记录走 _create_record 公共核（同 session 原子性）
        """
        if not isinstance(qr_token, str) or not (8 <= len(qr_token) <= 64):
            return None

        with session_scope() as s:
            from src.dao.task_signin_code_dao import TaskSigninCodeDao
            code = TaskSigninCodeDao(s).find_active_by_value(task_id, "qr", qr_token)
            if not code:
                return None
            return self._create_record_in_session(
                s, task_id, user_id, "qr", match_score=None,
            )

    # -----------------------------------------------------
    # 同 session 内的「写记录」版本（给数字码/二维码走，原子性更稳）
    # -----------------------------------------------------
    def _create_record_in_session(self, s, task_id: int, user_id: int,
                                  signin_method: str,
                                  match_score: Optional[float]) -> Optional[AttendanceRecord]:
        """_create_record 的「复用外层 session」变体。

        数字码 / 二维码签到要保证「码校验 + 写记录」原子性——
        否则可能发生「码校验通过 + 但被另一个事务抢签」导致重复记录。
        由于 attendance_record 有 UNIQUE KEY (task_id, student_id) 兜底，
        即使极端 race 也只会有一条记录 + 一次返 None，但日志会困惑。
        所以这里走单事务路径。
        """
        task = s.get(AttendanceTask, task_id)
        if not task or task.status != "open":
            return None

        from src.dao.user_dao import UserDao
        user = UserDao(s).get(user_id)
        if not user or user.role != "student":
            return None

        existed = s.query(AttendanceRecord).filter(
            and_(AttendanceRecord.task_id == task_id,
                 AttendanceRecord.student_id == user_id)
        ).first()
        if existed:
            return None

        now = datetime.now()
        late_cutoff = task.start_time + timedelta(minutes=LATE_THRESHOLD_MINUTES)
        status = "present" if now <= late_cutoff else "late"

        record = AttendanceRecord(
            task_id=task_id,
            student_id=user_id,
            sign_in_time=now,
            status=status,
            match_score=match_score,
            signin_method=signin_method,
        )
        s.add(record)
        s.flush()
        s.refresh(record)
        s.expunge(record)
        return record

    # -----------------------------------------------------
    # 教师生成签到码（W13+，对分易式「手动触发」语义）
    # -----------------------------------------------------
    def generate_signin_code(self, task_id: int, code_type: str,
                             ttl_seconds: int = DEFAULT_CODE_TTL_SECONDS
                             ) -> Optional[dict]:
        """教师手动触发生成签到码：
          - 先把同任务同类型的所有未过期有效码失效（is_active=0）
          - 写一条新码
          - 返回 dict {code, code_type, expires_at}

        边界校验：
          1) task 存在 + status='open'           —— 否则返 None
          2) code_type ∈ {'digit','qr'}          —— 否则抛 ValueError
          3) ttl_seconds ∈ [1, MAX_CODE_TTL_SECONDS] —— 否则抛 ValueError

        设计理由（对分易观察）：
          - 教师「手动触发」而非定时刷新，避免「课前刷码 → 全班秒签」。
          - 旧码全部失效，新码唯一生效，防止学生拿到截图迟到 30 秒后还有效。
        """
        if code_type not in ("digit", "qr"):
            raise ValueError(f"code_type 必须是 digit/qr，收到 {code_type!r}")
        if not (1 <= ttl_seconds <= MAX_CODE_TTL_SECONDS):
            raise ValueError(
                f"ttl_seconds 必须在 1..{MAX_CODE_TTL_SECONDS}，收到 {ttl_seconds!r}"
            )

        with session_scope() as s:
            task = s.get(AttendanceTask, task_id)
            if not task or task.status != "open":
                return None

            from src.dao.task_signin_code_dao import TaskSigninCodeDao
            dao = TaskSigninCodeDao(s)

            # 1) 失效同任务同类型的所有未过期有效码（覆盖式刷新）
            dao.deactivate_active_for_task_type(task_id, code_type)

            # 2) 生成新码
            if code_type == "digit":
                # {0:04d} 补前导零，确保「0123」≠「123」
                code_value = f"{random.randint(0, 9999):04d}"
            else:  # qr
                # 22 字符 base64，碰撞概率 < 2^-96
                code_value = secrets.token_urlsafe(16)

            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            new_code = dao.insert_new(
                task_id=task_id,
                code_type=code_type,
                code_value=code_value,
                expires_at=expires_at,
            )
            return {
                "code": new_code.code_value,
                "code_type": code_type,
                "expires_at": expires_at,
            }

    # -----------------------------------------------------
    # 任务结束：自动标记缺勤
    # -----------------------------------------------------
    def close_task_and_mark_absent(self, task_id: int):
        """end_time 到达后调用，遍历课程学生名单补齐缺勤。

        W4 Phase 3b: 改用 course_enrollment 选课名单代替"role=student 全部"。
        防御性降级: 如果该课程无任何选课记录（旧数据 / 演示场景），fallback 到
        role='student'，保持旧行为不挂。
        """
        with session_scope() as s:
            task = s.get(AttendanceTask, task_id)
            if not task:
                return
            task.status = "closed"

            # 1. 查 course_enrollment 该课程的学生
            from src.dao.course_enrollment_dao import CourseEnrollmentDao
            enrollments = CourseEnrollmentDao(s).find_by_course(task.course_id)

            if enrollments:
                student_ids = {e.student_id for e in enrollments}
                students = s.query(User).filter(User.id.in_(student_ids)).all()
            else:
                # 防御性降级: 无 enrollment → fallback 到所有 student
                students = s.query(User).filter(User.role == "student").all()

            for stu in students:
                existed = s.query(AttendanceRecord).filter(
                    and_(AttendanceRecord.task_id == task_id,
                         AttendanceRecord.student_id == stu.id)
                ).first()
                if existed:
                    continue

                leave = s.query(LeaveRequest).filter(
                    and_(LeaveRequest.task_id == task_id,
                         LeaveRequest.student_id == stu.id,
                         LeaveRequest.status == "approved")
                ).first()
                status = "leave" if leave else "absent"

                s.add(AttendanceRecord(
                    task_id=task_id,
                    student_id=stu.id,
                    sign_in_time=None,
                    status=status,
                    signin_method="face",  # 默认值；缺勤记录无具体签到方式
                ))

    # -----------------------------------------------------
    # 统计辅助
    # -----------------------------------------------------
    def task_summary(self, task_id: int) -> dict:
        """返回某个任务的统计：present/late/absent/leave 各多少人"""
        with session_scope() as s:
            from src.dao.attendance_dao import AttendanceRecordDao
            counter = AttendanceRecordDao(s).count_by_status(task_id)
            return {
                "present": counter.get("present", 0),
                "late": counter.get("late", 0),
                "absent": counter.get("absent", 0),
                "leave": counter.get("leave", 0),
                "total": sum(counter.values()),
            }
