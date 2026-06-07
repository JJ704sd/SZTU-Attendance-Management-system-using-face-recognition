"""
tests/conftest.py — pytest 公共 fixture
- 自动把项目根目录加进 sys.path
- 加载 .env
- session 结束后自动清理 UUID 风格测试用户（防止反复跑测试导致冗余数据堆积）
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env（在测试自己的临时 MySQL 之前生效）
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------------------------
# pytest 启动选项: --no-cleanup 跳过 session 结束后的 fixture 用户清理
# ---------------------------------------------------------------------------
def pytest_addoption(parser):
    parser.addoption(
        "--no-cleanup",
        action="store_true",
        help="跳过测试 session 结束后的 fixture 用户清理（调试用）",
    )


# ---------------------------------------------------------------------------
# session 级 autouse fixture: 跑完所有测试后清理 UUID 风格测试用户
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _auto_cleanup_test_users(request):
    """测试 session 结束后清理所有 UUID/placeholder 测试用户。

    动机:
    - tests/test_*.py 用 _uni("u") 风格注册用户避免冲突，但跑完不清理
    - 反复跑测试 → user 表越攒越多（之前 177 个里 171 个就是这么来的）
    - 手动跑 scripts/cleanup_test_users.py 治标不治本

    规则（保守 + 安全）:
    - 只匹配 fixture 风格 username: u_/s_/t_/sa_/sb_ + 8位hex
      以及 locked_/reset_/unlock_/nonexistent_/attempt_/last_/clear_ + 8位hex
    - 只匹配 8 种测试 placeholder real_name: A/测试用户/测脸/锁定测试/重置测试/解锁测试/准入测试/培训测试
    - 排除: 4 个基础测试账号 (20230101/20230102/teacher01/labadmin01) + 当前管理员 admin01 + demo_student
    - 排除: 任何 username 不在前缀名单里的用户（真实用户不会被误伤）

    FK 安全: face_encoding / course_enrollment 都有 ON DELETE CASCADE，
            自动连带清掉。其他外键表（attendance_record 等）依赖 student_id 命中
            —— 历史上已验证测试用户在这些表里命中为 0。
    """
    yield
    if request.config.getoption("--no-cleanup"):
        return

    try:
        from sqlalchemy import text
        from src.db import engine
    except Exception as exc:
        print(f"\n[conftest._auto_cleanup_test_users] 跳过清理: {exc}")
        return

    KEEP_USERS = ("20230101", "20230102", "teacher01", "labadmin01", "admin01", "demo_student")
    TEST_REAL_NAMES = (
        "A", "测试用户", "测脸",
        "锁定测试", "重置测试", "解锁测试",
        "准入测试", "培训测试",
    )
    # username 匹配: fixture 前缀 + 8位 hex
    TEST_USERNAME_RE = r"^(u|s|t|sa|sb|locked|reset|unlock|nonexistent|attempt|last|clear)_[0-9a-f]{8}$"

    # KEEP_USERS / TEST_REAL_NAMES 是 hardcoded 列表, 直接拼接避免 SQLAlchemy expanding 参数麻烦
    keep_in = ",".join(f"'{u}'" for u in KEEP_USERS)
    rns_in = ",".join(f"'{n}'" for n in TEST_REAL_NAMES)

    where_clause = (
        f"(username REGEXP :re OR real_name IN ({rns_in})) "
        f"AND username NOT IN ({keep_in})"
    )

    with engine.begin() as conn:
        try:
            cnt = conn.execute(
                text(f"SELECT COUNT(*) FROM user WHERE {where_clause}"),
                {"re": TEST_USERNAME_RE},
            ).scalar()
        except Exception as exc:
            print(f"\n[conftest._auto_cleanup_test_users] 统计失败: {exc}")
            return

        if cnt == 0:
            return  # 干净，静默通过

        result = conn.execute(
            text(f"DELETE FROM user WHERE {where_clause}"),
            {"re": TEST_USERNAME_RE},
        )
        print(f"\n[conftest] 🧹 auto-cleanup: 删除了 {result.rowcount} 个测试 fixture 用户（防止冗余积累）")
