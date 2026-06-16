"""
scripts/cleanup_test_classrooms.py — 清掉 classroom 表里测试残留 (W14+)

背景: tests/test_signin_web.py:138 创建测试教室 `测试教室{suf}` (suf 是 uuid hex),
      但 pytest 跑完没清理, 累计 321 条垃圾. 教师端「发起考勤」教室下拉列表
      又长又丑.

策略: classroom.name LIKE '测试教室%' 即认定为测试残留.

外键检查 (W14+ 已 audit 过):
  - 只有 attendance_task 表的 classroom_id 引用 classroom.id
  - 测试教室被 attendance_task 引用的条数: 0 (W14+ 验证)
  - 所以删除教室不会触发级联, 安全.

用法:
    .venv\\Scripts\\python.exe scripts\\cleanup_test_classrooms.py        # dry-run
    .venv\\Scripts\\python.exe scripts\\cleanup_test_classrooms.py --apply  # 真删
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from src.db import session_scope
from src.models.course import Classroom

TEST_PREFIX = "测试教室"


def main() -> int:
    parser = argparse.ArgumentParser(description="清掉 classroom 表里 pytest 反复跑留下的测试教室")
    parser.add_argument(
        "--apply", action="store_true",
        help="真删 (默认是 dry-run, 只 print 不删)",
    )
    args = parser.parse_args()

    with session_scope() as s:
        all_rooms = s.query(Classroom).order_by(Classroom.id).all()
        real = [r for r in all_rooms if not r.name.startswith(TEST_PREFIX)]
        junk = [r for r in all_rooms if r.name.startswith(TEST_PREFIX)]

        print(f"=== classroom 表当前共 {len(all_rooms)} 条 ===")
        print(f"  正式 ({len(real)}):")
        for r in real:
            print(f"    #{r.id:>3} {r.name} ({r.location or '-'}) cap={r.capacity}")

        print(f"  测试残留 ({len(junk)}):")
        if junk:
            print(f"    前 8 条:")
            for r in junk[:8]:
                print(f"      #{r.id:>3} {r.name}")
            print(f"    ... 还有 {len(junk) - 8} 条")
        if not junk:
            print("✅ 没有测试残留, 不用清理")
            return 0

        # 安全检查: 这些教室被 attendance_task 引用的条数
        ref_count = s.execute(text("""
            SELECT COUNT(*) FROM attendance_task at
            JOIN classroom rm ON at.classroom_id = rm.id
            WHERE rm.name LIKE :prefix
        """), {"prefix": f"{TEST_PREFIX}%"}).scalar()
        print(f"\n  这些教室关联的 attendance_task: {ref_count} 条")

    if not args.apply:
        print("\n[dry-run] 没真删。加 --apply 才会真删:")
        print(f"  .venv\\Scripts\\python.exe scripts\\cleanup_test_classrooms.py --apply")
        return 0

    # 真删
    with session_scope() as s:
        n = s.query(Classroom).filter(
            Classroom.name.like(f"{TEST_PREFIX}%")
        ).delete(synchronize_session=False)
        print(f"\n✅ 已删 {n} 个测试教室")
    return 0


if __name__ == "__main__":
    sys.exit(main())
