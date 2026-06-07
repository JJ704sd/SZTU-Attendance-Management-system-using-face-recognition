"""
scripts/seed_demo_data.py — 一键 seed 演示数据 (W12)

P0 验收前用: 给 teacher01 建课程 + 考勤任务, 让学生 demo_student 能签到.
- 如果已经 seed 过, 会先清掉再重建 (幂等).
- 不影响其他用户 / 课程.

用法:
    .venv\Scripts\python.exe scripts\seed_demo_data.py
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db import session_scope
from src.models.user import User
from src.models.course import Course, Classroom
from src.models.attendance import AttendanceTask


def main() -> int:
    with session_scope() as s:
        teacher = s.query(User).filter(User.username == "teacher01").first()
        if not teacher:
            print("❌ teacher01 不存在, 请先在 GUI 注册窗建教师账号")
            return 1
        print(f"✅ 教师: {teacher.username} (id={teacher.id})")

        # 清掉这个教师之前 seed 的课程 + 任务 (幂等)
        old_courses = s.query(Course).filter(Course.teacher_id == teacher.id).all()
        for c in old_courses:
            s.query(AttendanceTask).filter(AttendanceTask.course_id == c.id).delete()
            s.delete(c)
        s.flush()
        print(f"清掉 {len(old_courses)} 个旧课程")

        # 建课程
        course = Course(
            course_code="BME201",
            course_name="生物医学工程导论",
            course_type="theory",
            teacher_id=teacher.id,
        )
        s.add(course)
        s.flush()
        print(f"✅ 课程: [{course.course_type}] {course.course_code} {course.course_name} (id={course.id})")

        # 拿 A101 教室 (没有就用 id=1)
        room = s.query(Classroom).filter(Classroom.name == "A101").first()
        if not room:
            room = s.query(Classroom).first()
        if not room:
            print("❌ classroom 表是空的, 请先 INSERT 教室")
            return 1
        print(f"✅ 教室: {room.name} ({room.location}) (id={room.id})")

        # 建任务: now - 5min ~ now + 30min (已开始, 但未结束 → open 状态)
        now = datetime.now()
        task = AttendanceTask(
            course_id=course.id,
            teacher_id=teacher.id,
            classroom_id=room.id,
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(minutes=30),
            status="open",
        )
        s.add(task)
        s.flush()
        print(f"✅ 考勤任务 #{task.id}: {task.start_time} ~ {task.end_time} (status={task.status})")
        print()
        print("=== 现在可以 ===")
        print("1. 登录 teacher01 → Tab 1 发起考勤: 看到刚建的课程可选")
        print("2. 登录 demo_student → Tab 2 刷脸签到: 任务下拉里看到这个任务")
        print("3. 学生刷脸 → 教师 Tab 2 历史考勤查看签到详情")
    return 0


if __name__ == "__main__":
    sys.exit(main())
