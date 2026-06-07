"""
scripts/cleanup_test_users.py — 清掉 user 表里 pytest 反复跑留下的测试用户 (W12)

背景: 之前 pytest 跑 test_auth_service.py 用 UUID 用户名 (u_xxx / s_xxx / locked_xxx
      / reset_xxx / unlock_xxx) 反复建用户, 累计留 152 条垃圾, 管理员 Tab 列表
      又长又丑.

用法:
    .venv\Scripts\python.exe scripts\cleanup_test_users.py
    # 会先 print 干跑结果, 你确认要删再调 --apply
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db import session_scope
from src.models.face import FaceEncoding
from src.models.user import User

# 测试用户名特征前缀 (跟 test_auth_service.py 里 _uni() 对齐)
TEST_PREFIXES = ("u_", "s_", "locked_", "reset_", "unlock_", "smk_")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true",
        help="真删 (默认是 dry-run, 只 print 不删)",
    )
    args = parser.parse_args()

    with session_scope() as s:
        all_users = s.query(User).all()
        real = [u for u in all_users if not u.username.startswith(TEST_PREFIXES)]
        junk = [u for u in all_users if u.username.startswith(TEST_PREFIXES)]

        print(f"=== user 表当前共 {len(all_users)} 条 ===")
        print(f"  真实用户 ({len(real)}):")
        for u in real:
            print(f"    #{u.id:>3} {u.username:20} ({u.real_name}) role={u.role}")
        print(f"  测试残留 ({len(junk)}):")
        for p in TEST_PREFIXES:
            n = sum(1 for u in junk if u.username.startswith(p))
            if n:
                print(f"    {p}*: {n} 个")
        if not junk:
            print("✅ 没有测试残留, 不用清理")
            return 0

        # 数这些用户占用的 face_encoding (也清掉)
        junk_ids = [u.id for u in junk]
        n_enc = s.query(FaceEncoding).filter(
            FaceEncoding.user_id.in_(junk_ids)
        ).count()
        print(f"\n  这些用户关联的 face_encoding: {n_enc} 条")

    if not args.apply:
        print("\n[dry-run] 没真删。加 --apply 才会真删:")
        print(f"  .venv\\Scripts\\python.exe scripts\\cleanup_test_users.py --apply")
        return 0

    # 真删
    with session_scope() as s:
        n1 = s.query(FaceEncoding).filter(
            FaceEncoding.user_id.in_(junk_ids)
        ).delete(synchronize_session=False)
        n2 = s.query(User).filter(User.id.in_(junk_ids)).delete(synchronize_session=False)
        print(f"\n✅ 已删 {n2} 个测试用户 + {n1} 条关联 face_encoding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
