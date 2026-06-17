"""全功能回归 smoke - 调每个 service/dao 公开方法, 异常就打印"""
import os, sys, traceback
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# W14 修复: 跨机适配 — 改成相对路径, 不再硬编码 D 盘
PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))
sys.path.insert(0, str(PROJ))

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion")

from src.db import session_scope
from src.services.auth_service import AuthService, AuthError
from src.services.attendance_service import AttendanceService
from src.services.lab_access_service import LabAccessService
from src.services.leave_service import LeaveService
from src.services.report_service import ReportService

from src.dao.user_dao import UserDao
from src.dao.course_dao import CourseDao
from src.dao.attendance_dao import AttendanceTaskDao, AttendanceRecordDao
from src.dao.leave_request_dao import LeaveRequestDao
from src.dao.lab_dao import LabDao
from src.dao.lab_training_dao import LabTrainingDao
from src.dao.lab_access_log_dao import LabAccessLogDao
from src.dao.task_signin_code_dao import TaskSigninCodeDao
from src.dao.face_dao import FaceEncodingDao
from src.dao.login_attempt_dao import LoginAttemptDao
from src.dao.course_enrollment_dao import CourseEnrollmentDao
from src.dao.classroom_dao import ClassroomDao
from src.models.user import User
from src.models.attendance import AttendanceTask, AttendanceRecord
from src.models.attendance import LeaveRequest

ok = fail = skip = 0
fails = []

def K(name, fn):
    global ok, fail
    try:
        r = fn()
        ok += 1
        if r is not None:
            print(f"  [OK]   {name}  -> {r}")
        else:
            print(f"  [OK]   {name}  -> None")
    except Exception as e:
        fail += 1
        fails.append((name, e, traceback.format_exc()))
        print(f"  [FAIL] {name}  -> {type(e).__name__}: {e}")

def S(name, why):
    global skip
    skip += 1
    print(f"  [SKIP] {name}  -> {why}")


# =============================================================
# 1. AuthService - 注册 / 登录 / 改密 / 错误路径
# =============================================================
print("\n=== 1. AuthService ===")
u = K("login(test001/123456)", lambda: AuthService().login("test001", "123456"))
# 错密码 / 不存在 都预期抛 AuthError (业务正确: 不泄露用户是否存在)
def login_wrong():
    try:
        AuthService().login("test001", "WRONG")
        return "UNEXPECTED: 没抛"
    except AuthError as e:
        return f"AuthError (预期): {e}"
def login_noexist():
    try:
        AuthService().login("nope_" + "x"*40, "x")
        return "UNEXPECTED: 没抛"
    except AuthError as e:
        return f"AuthError (预期): {e}"
K("login 错密码 (预期抛)", login_wrong)
K("login 不存在 (预期抛)", login_noexist)

# 改密
if u:
    K(f"change_password user {u.id}", lambda: AuthService().change_password(u.id, "123456", "123456") or "ok")
    K("change_password 错旧密", lambda: AuthService().change_password(u.id, "WRONG_OLD", "654321"))

# 注册新用户(随机后缀避免冲突)
import uuid
uname = f"smk_{uuid.uuid4().hex[:8]}"
new_u = K(f"register {uname}",
          lambda: AuthService().register(uname, "123456", "smoke全功能", role="student", student_id=uname))
# 重复 → 应抛 AuthError(不期望返 None)
def dup_should_fail():
    try:
        AuthService().register(uname, "123456", "x", role="student", student_id=uname)
        return "UNEXPECTED: 没抛"
    except AuthError as e:
        return f"AuthError: {e} (预期)"
K(f"register 重复 {uname} (预期抛)", dup_should_fail)
# 长字段校验
def long_should_fail():
    try:
        AuthService().register(f"smk_{uuid.uuid4().hex[:8]}", "123456", "a"*60, role="student", student_id="x")
        return "UNEXPECTED: 没抛"
    except AuthError as e:
        return f"AuthError: {e} (预期)"
K("register 超长 real_name (预期抛)", long_should_fail)

# 清理
if new_u:
    with session_scope() as s:
        UserDao(s).delete(new_u.id)


# =============================================================
# 2. AttendanceService - 3 种签到
# =============================================================
print("\n=== 2. AttendanceService ===")
with session_scope() as s:
    open_task = s.query(AttendanceTask).filter(AttendanceTask.status == "open").first()
    teacher_id = open_task.teacher_id if open_task else None
    task_id = open_task.id if open_task else None
    stu_pool = s.query(User).filter(User.role == "student", User.is_active == 1).limit(5).all()
    stu_ids = [u.id for u in stu_pool]

if not (task_id and stu_ids):
    S("AttendanceService 3种签到", "no open task or no student")
else:
    svc = AttendanceService()
    # generate digit
    r1 = K("generate_signin_code digit", lambda: svc.generate_signin_code(task_id, "digit", ttl_seconds=30))
    if r1:
        # stu1 digit 签到
        K("sign_in_by_digit", lambda: svc.sign_in_by_digit(task_id, stu_ids[0], r1["code"]))
        # 错码
        K("sign_in_by_digit 错码", lambda: svc.sign_in_by_digit(task_id, stu_ids[1], "0000") if r1["code"] != "0000" else "撞码跳过")
        # qr
        r2 = K("generate_signin_code qr", lambda: svc.generate_signin_code(task_id, "qr", ttl_seconds=30))
        if r2:
            K("sign_in_by_qr stu1 重复 (UNIQUE拦截)", lambda: svc.sign_in_by_qr(task_id, stu_ids[0], r2["code"]))
            K("sign_in_by_qr stu2 新", lambda: svc.sign_in_by_qr(task_id, stu_ids[2], r2["code"]))

    # sign_in_by_face (用不存在的 distance 测错误路径)
    K("sign_in_by_face 太远 (distance 0.9)", lambda: svc.sign_in_by_face(task_id, stu_ids[3], 0.9))


# =============================================================
# 3. LabAccessService - 7 分支
# =============================================================
print("\n=== 3. LabAccessService ===")
with session_scope() as s:
    lab = LabDao(s).get_all()
    lab_id = lab[0].id if lab else None
if lab_id:
    lab_svc = LabAccessService()
    with session_scope() as s:
        any_stu = s.query(User).filter(User.role == "student", User.is_active == 1).first()
        any_stu_id = any_stu.id if any_stu else None
    if any_stu_id:
        K("check_access (无培训应 deny)", lambda: lab_svc.check_access(any_stu_id, lab_id))


# =============================================================
# 4. LeaveService - 申请 / 审批
# =============================================================
print("\n=== 4. LeaveService ===")
if task_id and stu_ids:
    # student_apply 业务: 若该学生在该 task 已有 pending 假单应抛 LeaveError
    # 这是业务正确行为, 但 smoke 之前测试残留可能让它一直抛
    # 先把残留标成 rejected (schema 不支持 withdrawn)
    with session_scope() as s:
        from src.dao.leave_request_dao import LeaveRequestDao as LRDao
        pending = LRDao(s).find_pending_by_task(task_id)
        for p in pending:
            p.status = "rejected"
        LRDao(s).commit() if hasattr(LRDao(s), "commit") else None
    K("student_apply (清残留后)", lambda: LeaveService().student_apply(stu_ids[4], task_id, "smoke test leave"))


# =============================================================
# 5. ReportService - 4 方法
# =============================================================
print("\n=== 5. ReportService ===")
rs = ReportService()
with session_scope() as s:
    stu0 = s.query(User).filter(User.role == "student", User.is_active == 1).first()
    c0 = CourseDao(s).get_all()
    course_id = c0[0].id if c0 else None
if stu0 and course_id:
    K("attendance_rate_per_student", lambda: rs.attendance_rate_per_student(stu0.id))
    K("attendance_trend_per_course", lambda: rs.attendance_trend_per_course(course_id))
    # lab_usage_rate 要 lab_id
    with session_scope() as s:
        any_lab = LabDao(s).get_all()
        any_lab_id = any_lab[0].id if any_lab else None
    if any_lab_id:
        K("lab_usage_rate", lambda: rs.lab_usage_rate(any_lab_id))
    K("absent_warning_list", lambda: rs.absent_warning_list())


# =============================================================
# 6. DAO 一致性 (找 open task 后, 每 dao 至少 1 个查询)
# =============================================================
print("\n=== 6. DAO 查询 ===")
with session_scope() as s:
    K("UserDao.get_all", lambda: len(UserDao(s).get_all()))
    K("CourseDao.find_all", lambda: len(CourseDao(s).find_all()))
    K("ClassroomDao.find_all", lambda: len(ClassroomDao(s).find_all()))
    K("LabDao.find_all", lambda: len(LabDao(s).find_all()))
    K("CourseEnrollmentDao.find_by_student", lambda: len(CourseEnrollmentDao(s).find_by_student(stu_ids[0])) if stu_ids else [])
    K("LoginAttemptDao.count_recent_failures", lambda: LoginAttemptDao(s).count_recent_failures("test001", limit=5))
    K("LabAccessLogDao.get_all", lambda: len(LabAccessLogDao(s).get_all()))
    K("LabTrainingDao.find_all", lambda: len(LabTrainingDao(s).find_all()))
    K("AttendanceTaskDao.find_open_tasks", lambda: len(AttendanceTaskDao(s).find_open_tasks()))
    K("AttendanceTaskDao.find_by_teacher", lambda: len(AttendanceTaskDao(s).find_by_teacher(teacher_id)) if teacher_id else [])
    K("LeaveRequestDao.find_by_student", lambda: len(LeaveRequestDao(s).find_by_student(stu_ids[0])) if stu_ids else [])
    if task_id:
        K("LeaveRequestDao.find_pending_by_task", lambda: len(LeaveRequestDao(s).find_pending_by_task(task_id)))
        K("AttendanceRecordDao.find_by_task", lambda: len(AttendanceRecordDao(s).find_by_task(task_id)))
        K("TaskSigninCodeDao.find_active_by_task_type digit", lambda: len(TaskSigninCodeDao(s).find_active_by_task_type(task_id, "digit")))
    K("FaceEncodingDao.find_by_user", lambda: len(FaceEncodingDao(s).find_by_user(stu_ids[0])) if stu_ids else [])


# =============================================================
# 总结
# =============================================================
print(f"\n=== 总计: ok={ok}  fail={fail}  skip={skip} ===")
if fails:
    print(f"\n=== {len(fails)} 失败 ===")
    for n, e, tb in fails:
        print(f"\n--- {n} ---")
        print(f"  {type(e).__name__}: {e}")
        # 只打最后 5 行 traceback
        print("\n".join(tb.splitlines()[-5:]))
    sys.exit(1)
print("ALL OK")
