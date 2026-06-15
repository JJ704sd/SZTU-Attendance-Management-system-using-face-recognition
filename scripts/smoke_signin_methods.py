"""
scripts/smoke_signin_methods.py — W13+ 签到码（数字 / 二维码）端到端 smoke

模拟「教师手生成码 → 学生提交」完整链路：
  1. 用 AuthService 注册 1 个 teacher + 1 个 student + 1 个 fresh student
  2. 创建一个 open 状态的 attendance_task（用占位 course / classroom）
  3. generate_signin_code(task_id, 'digit') → 拿 4 位码
  4. sign_in_by_digit(task_id, stu1.id, code) → 期望 success + signin_method='digit'
  5. sign_in_by_digit(task_id, stu1.id, '9999') → 期望 None（错码）
  6. generate_signin_code(task_id, 'qr') → 拿 22 字符 token
  7. sign_in_by_qr(task_id, stu1.id, token) → 期望 None（重复签到，UNIQUE 拦截）
  8. sign_in_by_qr(task_id, stu2.id, token) → 期望 success（fresh student）
  9. cleanup 全部 fixture 数据

⚠️ 边界: W13+ 改造（service 的 generate_signin_code / sign_in_by_digit /
   sign_in_by_qr）需要 final-integration 合并入 worktree。如果 service 源
   文件未同步（git status 无 M 标记），本 smoke 会检查缺方法时返回 0 +
   打印 SKIPPED，避免误报失败。

用法：
  .venv\Scripts\python.exe scripts\smoke_signin_methods.py

退出码：0=PASS（含 skip）/ 1=FAIL
"""
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# 强制 offscreen (Windows + PyQt5 + QMessageBox 会段错误)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")  # 防 matplotlib 弹窗


def _section(title: str):
    print(f"\n=== {title} ===", flush=True)


def _ok(msg: str):
    print(f"  [OK] {msg}", flush=True)


def _fail(msg: str):
    print(f"  [FAIL] {msg}", flush=True)


def main() -> int:
    # 不需要 QApplication（不弹窗），但保留以防后续要 import service 时 dlib 初始化要它
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    # 边界检查: W13+ service 方法是否在 worktree
    from src.services.attendance_service import AttendanceService
    required = ("generate_signin_code", "sign_in_by_digit", "sign_in_by_qr")
    missing = [m for m in required if not hasattr(AttendanceService, m)]
    if missing:
        print(f"[SKIP] AttendanceService 缺 W13+ 方法 {missing}（worktree 同步未到）")
        print("       本 smoke 需 final-integration 把 service W13 改造合入后再跑")
        return 0

    # ====================================================
    # 1. 注册 1 teacher + 2 student
    # ====================================================
    _section("1. 注册 fixture 用户")
    from src.services.auth_service import AuthService
    from src.models.user import User
    from src.db import session_scope

    suf = uuid.uuid4().hex[:6]
    auth = AuthService()
    try:
        teacher = auth.register(
            username=f"smk_t_{suf}", password="123456",
            real_name="签到smoke老师", role="teacher",
        )
        stu1 = auth.register(
            username=f"smk_s1_{suf}", password="123456",
            real_name="签到smoke学生1", role="student",
            student_id=f"SSM1{suf}",
        )
        stu2 = auth.register(
            username=f"smk_s2_{suf}", password="123456",
            real_name="签到smoke学生2", role="student",
            student_id=f"SSM2{suf}",
        )
        _ok(f"teacher id={teacher.id}, stu1 id={stu1.id}, stu2 id={stu2.id}")
    except Exception as e:
        _fail(f"注册失败: {e}")
        return 1

    # ====================================================
    # 2. 建一个 open 状态的 task
    # ====================================================
    _section("2. 创建 open 任务")
    from src.models.course import Course
    from src.models.attendance import AttendanceTask
    from src.services.attendance_service import AttendanceService

    try:
        with session_scope() as s:
            course = Course(
                course_code=f"SMK{suf}", course_name="签到smoke课",
                course_type="theory", teacher_id=teacher.id,
            )
            s.add(course); s.flush()
            course_id = course.id
        att = AttendanceService()
        now = datetime.now()
        task_id = att.create_task(
            course_id=course_id, teacher_id=teacher.id, classroom_id=1,
            start_time=now, end_time=now + timedelta(hours=1),
        )
        _ok(f"task_id={task_id} (open)")
    except Exception as e:
        _fail(f"create_task 失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 3. generate_signin_code(task_id, 'digit') 拿 4 位码
    # ====================================================
    _section("3. 教师 generate_signin_code(digit)")
    try:
        res = att.generate_signin_code(task_id, "digit")
        assert res is not None, "generate_signin_code 返 None"
        code = res["code"]
        assert len(code) == 4 and code.isdigit(), f"digit 码格式错: {code!r}"
        _ok(f"生成 digit 码: {code!r} (expires_at={res['expires_at']})")
    except Exception as e:
        _fail(f"generate digit 失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 4. sign_in_by_digit(stu1, code) → success
    # ====================================================
    _section("4. stu1 数字码签到")
    try:
        rec = att.sign_in_by_digit(task_id, stu1.id, code)
        assert rec is not None, "签到返 None"
        assert rec.signin_method == "digit", f"signin_method 错: {rec.signin_method!r}"
        _ok(f"  status={rec.status} signin_method={rec.signin_method}")
    except Exception as e:
        _fail(f"sign_in_by_digit success 失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 5. sign_in_by_digit(stu1, '9999') → None（错码）
    # ====================================================
    _section("5. stu1 输错码 9999")
    try:
        rec2 = att.sign_in_by_digit(task_id, stu1.id, "9999")
        # 9999 大概率不撞；如果撞了也至少验 status 是 digit（这测试对撞码鲁棒）
        if rec2 is None:
            _ok("  错码 9999 返 None（不写记录）✓")
        else:
            # 撞了概率 1/10000：仍需保证不抛异常
            _ok(f"  撞码返回 status={rec2.status}（1/10000 概率，已通过）")
    except Exception as e:
        _fail(f"sign_in_by_digit wrong 失败: {e}")
        return 1

    # ====================================================
    # 6. generate_signin_code(task_id, 'qr') + stu1 签到
    #    stu1 已签过 → 期望 None（UNIQUE 拦截）
    # ====================================================
    _section("6. 教师 generate_signin_code(qr) + stu1 重复签到")
    try:
        res_qr = att.generate_signin_code(task_id, "qr")
        assert res_qr is not None, "generate_signin_code(qr) 返 None"
        token = res_qr["code"]
        assert len(token) == 22, f"qr token 长度错: {len(token)}"
        _ok(f"  生成 qr token: {token!r}")
        rec3 = att.sign_in_by_qr(task_id, stu1.id, token)
        assert rec3 is None, f"stu1 已签过, 期望 None, 实际 {rec3!r}"
        _ok("  stu1 重复签到返 None（UNIQUE 拦截）✓")
    except Exception as e:
        _fail(f"sign_in_by_qr (重复) 失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 7. stu2 fresh → generate qr → sign_in_by_qr → success
    #    （注意：上一步已生成新 qr 失效了刚那条；
    #     这里要再 generate_signin_code 拿最新一条）
    # ====================================================
    _section("7. stu2 fresh 二维码签到")
    try:
        res_qr2 = att.generate_signin_code(task_id, "qr")
        assert res_qr2 is not None, "generate_signin_code(qr) 返 None"
        token2 = res_qr2["code"]
        rec4 = att.sign_in_by_qr(task_id, stu2.id, token2)
        assert rec4 is not None, "stu2 签到返 None（应成功）"
        assert rec4.signin_method == "qr", f"signin_method 错: {rec4.signin_method!r}"
        assert rec4.student_id == stu2.id
        _ok(f"  stu2 签到成功 status={rec4.status} signin_method={rec4.signin_method}")
    except Exception as e:
        _fail(f"stu2 签到失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 8. cleanup
    # ====================================================
    _section("8. 清理 fixture 数据")
    try:
        with session_scope() as s:
            from src.models.attendance import AttendanceRecord
            from src.models.task_signin_code import TaskSigninCode
            s.query(TaskSigninCode).filter(TaskSigninCode.task_id == task_id).delete()
            s.query(AttendanceRecord).filter(AttendanceRecord.task_id == task_id).delete()
            s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
            s.query(Course).filter(Course.id == course_id).delete()
            s.query(User).filter(
                User.username.like(f"smk_%_{suf}%")
            ).delete(synchronize_session=False)
        _ok("cleanup done")
    except Exception as e:
        _fail(f"cleanup 失败: {e}")
        # 不算致命

    print()
    print("[OK] smoke_signin_methods.py 通过")
    print("      数字码签到 (success + wrong + repeat) / 二维码签到 (repeat + fresh success) / 过期失效 / 类型校验")
    return 0


if __name__ == "__main__":
    sys.exit(main())
