"""
scripts/import_schedule.py — 从学生个人课表 xls 导入老师/教室/课程/选课 (W14+ 演示模式)

配套: db/migration_w14.sql + src/models/course_teacher.py + src/dao/course_teacher_dao.py

设计决策 (用户已审核):
    Q1=B: username = 'tch_教师姓名' (如 tch_李贵叶)
    Q2=A: 默认密码 '123456' (bcrypt 哈希)
    Q3=B: 多老师课程 (信号与系统/数据库原理/医用电子技术) 写入 course_teacher 关联表,
          第一个老师作主讲进 Course.teacher_id
    Q4=C: 教室 name 改成只留楼栋编号 (A-2-415 而不是 A-2-415智能医学传感教学实验?2)

幂等性:
    user.username / course.course_code / classroom.name / course_teacher(course_id, teacher_id)
    都用 SELECT-then-INSERT 模式, 已存在则跳过并提示 (不会重复插入, 不会修改已有数据)

用法:
    .venv\\Scripts\\python.exe scripts\\import_schedule.py --xls <xls_path>
    # 默认 dry-run: 只 print 待插入清单 + 跳过已存在, 不写库
    .venv\\Scripts\\python.exe scripts\\import_schedule.py --xls <xls_path> --apply
    # 真插入
"""
import argparse
import re
import sys
from pathlib import Path
from collections import OrderedDict

import xlrd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db import session_scope
from src.models.user import User
from src.models.course import Course, Classroom
from src.models.course_enrollment import CourseEnrollment
from src.models.course_teacher import CourseTeacher
from src.utils.crypto import hash_password

WEEKDAY_NAMES = ["", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
DEFAULT_STUDENT_ID = "202400502133"
DEFAULT_PASSWORD = "123456"


# =============================================================================
# 1. 解析 xls
# =============================================================================
def parse_cell(raw: str):
    """灵活解析一个 cell: 每节课 4~5 行 (课程 / 班级 / 教师 / 周次 / 教室)."""
    if not raw or not raw.strip():
        return []
    blocks = re.split(r"\n\s*\n", raw.strip())
    courses = []
    for blk in blocks:
        lines = [ln.strip() for ln in blk.split("\n") if ln.strip()]
        if not lines:
            continue
        course = lines[0]
        classroom = ""
        weeks = ""
        teacher = ""
        class_info = ""
        if len(lines) == 1:
            courses.append({"course": course, "class_info": "", "teacher": "", "weeks": "", "classroom": ""})
            continue
        rm_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if re.match(r"^[A-F]-\d", lines[i]) or re.match(r"^教学", lines[i]):
                rm_idx = i
                break
        if rm_idx >= 0:
            classroom = lines[rm_idx]
            tail = lines[:rm_idx]
        else:
            tail = lines[:]
        wk_idx = -1
        for i in range(len(tail) - 1, -1, -1):
            if "[周]" in tail[i] or "周)" in tail[i] or "周次" in tail[i]:
                wk_idx = i
                break
        if wk_idx >= 0:
            weeks = tail[wk_idx]
            before = tail[:wk_idx]
        else:
            before = tail
        rest = before[1:]
        if len(rest) == 1:
            teacher = rest[0]
        elif len(rest) >= 2:
            class_info = rest[0]
            teacher = rest[1]
        courses.append({
            "course": course,
            "class_info": class_info,
            "teacher": teacher,
            "weeks": weeks,
            "classroom": classroom,
        })
    return courses


def parse_xls(xls_path: str):
    book = xlrd.open_workbook(xls_path)
    sh = book.sheet_by_index(0)
    entries = []
    for r in range(3, 12):
        for c in range(1, 8):
            cell_val = sh.cell_value(r, c)
            if not cell_val or not str(cell_val).strip():
                continue
            for ent in parse_cell(str(cell_val)):
                ent["weekday"] = WEEKDAY_NAMES[c]
                entries.append(ent)
    return entries


# =============================================================================
# 2. 汇总 unique 实体
# =============================================================================
def collect_entities(entries):
    teachers = OrderedDict()  # name -> count
    courses = OrderedDict()   # name -> dict
    classrooms = OrderedDict()

    for e in entries:
        t = e["teacher"]
        if t and not re.search(r"\d|周|节|\[", t):
            teachers[t] = teachers.get(t, 0) + 1
        cn = e["course"]
        if cn:
            if cn not in courses:
                courses[cn] = {"teachers": [], "classrooms": [], "weeks": []}
            if t and not re.search(r"\d|周|节|\[", t):
                if t not in courses[cn]["teachers"]:
                    courses[cn]["teachers"].append(t)
            if e["classroom"] and e["classroom"] not in courses[cn]["classrooms"]:
                courses[cn]["classrooms"].append(e["classroom"])
            if e["weeks"] and e["weeks"] not in courses[cn]["weeks"]:
                courses[cn]["weeks"].append(e["weeks"])
        rm = e["classroom"]
        if rm:
            classrooms[rm] = classrooms.get(rm, 0) + 1
    return teachers, courses, classrooms


# =============================================================================
# Q4=C: 教室名只留楼栋编号 (A-2-415 而不是 A-2-415智能医学传感教学实验?2)
# =============================================================================
def normalize_classroom_name(raw: str) -> str:
    """从 'A-2-415智能医学传感教学实验?2' 提取 'A-2-415'. 没匹配到就保留原文."""
    m = re.match(r"^([A-Z]-\d+-\d+)", raw)
    if m:
        return m.group(1)
    return raw


# =============================================================================
# Q1=B: username = 'tch_教师姓名'
# =============================================================================
def teacher_username(name: str) -> str:
    """tch_教师姓名, 限长 50 字符 (user.username VARCHAR(50) 限制)."""
    base = f"tch_{name}"
    return base[:50]


# =============================================================================
# 3. dry-run 报告
# =============================================================================
def dry_run_report(xls_path: str):
    print(f"=== 课表导入 dry-run 报告 (Q1=B Q2=A Q3=B Q4=C) ===")
    print(f"xls 文件: {xls_path}")
    print()

    entries = parse_xls(xls_path)
    teachers, courses, classrooms = collect_entities(entries)

    print(f"解析得到 {len(entries)} 条课程块")
    print()

    # --- 教师 ---
    print(f"### 教师 (将新建 {len(teachers)} 个 user[role=teacher])")
    print(f"{'序号':<6} {'username':<18} {'real_name':<10} {'出现次数':<6} {'备注'}")
    new_teachers = []
    with session_scope() as s:
        for i, name in enumerate(teachers.keys(), 1):
            uname = teacher_username(name)
            existing = s.query(User).filter(User.username == uname).first()
            status = "[已存在, 跳过]" if existing else "[新建]"
            print(f"{i:<6} {uname:<18} {name:<10} {teachers[name]:<6} {status}")
            if not existing:
                new_teachers.append((uname, name))
    print()

    # --- 教室 ---
    print(f"### 教室 (Q4=C: 只留楼栋编号; 将新建 {len(classrooms)} 个 classroom)")
    print(f"{'序号':<6} {'原 name':<40} {'→ 归一化 name':<14} {'次数':<6} {'备注'}")
    new_rooms = []
    with session_scope() as s:
        for i, raw_name in enumerate(classrooms.keys(), 1):
            nname = normalize_classroom_name(raw_name)
            existing = s.query(Classroom).filter(Classroom.name == nname).first()
            status = "[已存在, 跳过]" if existing else "[新建]"
            note = ""
            if nname != raw_name:
                note = f"[Q4 归一化: 去后缀]"
            print(f"{i:<6} {raw_name[:38]:<40} {nname:<14} {classrooms[raw_name]:<6} {status} {note}")
            if not existing:
                new_rooms.append(nname)
    print()

    # --- 课程 (Q3=B: 多老师入 course_teacher 关联表) ---
    print(f"### 课程 (Q3=B: 多老师入 course_teacher; 将新建 {len(courses)} 个 course)")
    print(f"{'序号':<6} {'course_code':<14} {'course_name':<22} {'主讲教师':<14} {'其他教师':<20}")
    new_courses = []
    teacher_username_map = {}
    with session_scope() as s:
        for i, (name, info) in enumerate(courses.items(), 1):
            code = f"COURSE_{i:03d}"
            existing = s.query(Course).filter(Course.course_code == code).first()
            status = "[已存在, 跳过]" if existing else "[新建]"
            first_teacher_name = info["teachers"][0] if info["teachers"] else ""
            main_uname = teacher_username(first_teacher_name) if first_teacher_name else ""
            other = info["teachers"][1:]
            other_unames = [teacher_username(t) for t in other]
            note = f" {status}"
            if other:
                note += f" [⚠ Q3=B 关联表将写 {len(info['teachers'])} 个老师]"
            short_name = name[:20]
            print(f"{i:<6} {code:<14} {short_name:<22} {first_teacher_name or '?':<14} {', '.join(other)[:18]:<20} {note}")
            if not existing:
                new_courses.append((code, name, info["teachers"]))
    print()

    # --- 学生 + 选课 ---
    print(f"### 选课 (把学生 demo_student 加到 {len(courses)} 门课)")
    with session_scope() as s:
        student = s.query(User).filter(User.student_id == DEFAULT_STUDENT_ID).first()
        if not student:
            print(f"  [❌ 学生学号 {DEFAULT_STUDENT_ID} 不存在, 无法 enroll]")
        else:
            print(f"  学生: id={student.id} username={student.username} name={student.real_name}")
            for i, name in enumerate(courses.keys(), 1):
                code = f"COURSE_{i:03d}"
                course = s.query(Course).filter(Course.course_code == code).first()
                if not course:
                    print(f"  [{i:>3}] {name}: [假定 apply 后会建 + 新增选课]")
                    continue
                existing = s.query(CourseEnrollment).filter(
                    CourseEnrollment.student_id == student.id,
                    CourseEnrollment.course_id == course.id,
                ).first()
                status = "[已选, 跳过]" if existing else "[新增选课]"
                print(f"  [{i:>3}] {name}: {status}")
    print()

    print("=== 总结 ===")
    print(f"  将新建 teacher: {len(new_teachers)} 个 (Q1=B username=tch_姓名)")
    print(f"  将新建 classroom: {len(new_rooms)} 个 (Q4=C name 只留楼栋编号)")
    print(f"  将新建 course: {len(new_courses)} 门 (Q3=B 多老师入 course_teacher)")
    print()
    print("apply 前请先跑 init_db.py 一把梭建 14 张表 (含 course_teacher):")
    print(f"  .venv\\Scripts\\python.exe scripts\\init_db.py")
    print()
    print("加 --apply 才会真插入 (默认 dry-run, 不写库):")
    print(f"  .venv\\Scripts\\python.exe scripts\\import_schedule.py --xls \"{xls_path}\" --apply")


# =============================================================================
# 4. apply 实际插入
# =============================================================================
def apply_import(xls_path: str):
    entries = parse_xls(xls_path)
    teachers, courses, classrooms = collect_entities(entries)

    password_hash = hash_password(DEFAULT_PASSWORD)
    n_t = n_c = n_co = n_e = n_ct = 0

    with session_scope() as s:
        # 教师 (Q1=B: username = tch_教师姓名)
        teacher_id_map = {}
        for name in teachers.keys():
            uname = teacher_username(name)
            existing = s.query(User).filter(User.username == uname).first()
            if existing:
                teacher_id_map[name] = existing.id
                print(f"  [skip teacher] {uname} {name} 已存在 id={existing.id}")
                continue
            u = User(
                username=uname,
                password_hash=password_hash,
                real_name=name,
                role="teacher",
                is_active=1,
            )
            s.add(u)
            s.flush()
            teacher_id_map[name] = u.id
            n_t += 1
            print(f"  [+] teacher {uname} {name} id={u.id}")
        print()

        # 教室 (Q4=C: name 只留楼栋编号)
        for raw_name in classrooms.keys():
            nname = normalize_classroom_name(raw_name)
            existing = s.query(Classroom).filter(Classroom.name == nname).first()
            if existing:
                print(f"  [skip classroom] {nname} 已存在 id={existing.id}")
                continue
            r = Classroom(name=nname, capacity=60, has_camera=1)
            s.add(r)
            s.flush()
            n_c += 1
            print(f"  [+] classroom {nname} (原: {raw_name}) id={r.id}")
        print()

        # 课程 (Q3=B: 多老师入 course_teacher 关联表)
        course_id_map = {}
        for i, (name, info) in enumerate(courses.items(), 1):
            code = f"COURSE_{i:03d}"
            existing = s.query(Course).filter(Course.course_code == code).first()
            if existing:
                course_id_map[name] = existing.id
                print(f"  [skip course] {code} {name} 已存在 id={existing.id}")
                continue
            # 第一个老师作主讲, 进 Course.teacher_id (保留兼容)
            first_teacher_name = info["teachers"][0] if info["teachers"] else None
            teacher_id = teacher_id_map.get(first_teacher_name) if first_teacher_name else None
            c = Course(
                course_code=code,
                course_name=name,
                teacher_id=teacher_id,
                credit=2.0,
                semester="2025-2026-2",
            )
            s.add(c)
            s.flush()
            course_id_map[name] = c.id
            n_co += 1
            note = f" teacher={first_teacher_name}(id={teacher_id})" if teacher_id else " [⚠ 无教师]"
            print(f"  [+] course {code} {name} id={c.id}{note}")

            # Q3=B: 所有老师入 course_teacher 关联表
            for idx, tname in enumerate(info["teachers"]):
                tid = teacher_id_map.get(tname)
                if not tid:
                    print(f"      [⚠ 教师 {tname} 未建, 跳过 course_teacher]")
                    continue
                role = "main" if idx == 0 else "assistant"
                existing_ct = s.query(CourseTeacher).filter(
                    CourseTeacher.course_id == c.id,
                    CourseTeacher.teacher_id == tid,
                ).first()
                if existing_ct:
                    print(f"      [skip course_teacher] {tname}({tid}) role={role} 已存在")
                    continue
                ct = CourseTeacher(course_id=c.id, teacher_id=tid, role=role)
                s.add(ct)
                s.flush()
                n_ct += 1
                print(f"      [+] course_teacher {tname}({tid}) role={role}")
        print()

        # 选课
        student = s.query(User).filter(User.student_id == DEFAULT_STUDENT_ID).first()
        if not student:
            print(f"  [❌ 学生学号 {DEFAULT_STUDENT_ID} 不存在, 跳过 enroll]")
        else:
            for name, cid in course_id_map.items():
                existing = s.query(CourseEnrollment).filter(
                    CourseEnrollment.student_id == student.id,
                    CourseEnrollment.course_id == cid,
                ).first()
                if existing:
                    print(f"  [skip enroll] {name} 已选")
                    continue
                e = CourseEnrollment(student_id=student.id, course_id=cid)
                s.add(e)
                s.flush()
                n_e += 1
                print(f"  [+] enroll {student.real_name} -> {name}")

    print()
    print(f"=== 完成: 新增 teacher={n_t}, classroom={n_c}, course={n_co}, course_teacher={n_ct}, enrollment={n_e} ===")


# =============================================================================
# main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="从 xls 课表导入老师/教室/课程/选课 (W14+)")
    parser.add_argument("--xls", required=True, help="xls 课表路径")
    parser.add_argument("--apply", action="store_true", help="真插入 (默认 dry-run)")
    args = parser.parse_args()

    if not Path(args.xls).exists():
        print(f"[❌] xls 文件不存在: {args.xls}", file=sys.stderr)
        return 1

    if args.apply:
        print(f"=== [APPLY] 真插入, xls={args.xls} ===\n")
        apply_import(args.xls)
    else:
        dry_run_report(args.xls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
