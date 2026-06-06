"""
scripts/smoke_face.py — W3 Phase 6 端到端烟测

自动跑通「注册 demo_student → 采集 1 张人脸编码 → 识别回 demo_student」
最小闭环，验证 face_service 全链路在生产代码（不是 test 路径）上能用。

跑：
    python scripts/smoke_face.py
    echo $?    # 预期 0

设计要点：
- 注册/复用 demo_student：find_by_username 查，存在则用、不存在则 register。
- collect_for_user 时 patch face_locations + face_encodings 注入假数据
  （dlib 在纯 numpy 帧上检不出真脸；用 patch 走"假帧+真编码"路径是当前
  smoke 唯一能跑通端到端的方式，与 test_collect_for_user_writes_encodings
  的模式一致）。
- recognize 验证：传与采集完全相同的 FAKE_ENCODING，期望距离 0、命中
  demo_student.id。
- 幂等：清空 demo_student 旧编码后再采，保证 smoke 多次跑结果一致。
- 退出码：0 = 全过；非 0 = 任一步失败。
"""
import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

# 把项目根加进 sys.path（不依赖 PYTHONPATH）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.services.auth_service import AuthService
from src.services.face_service import (
    ENCODING_DIM,
    FaceService,
    _FaceCache,
    recognize,
)

# demo 账号固定用户名/密码/学号，方便反复跑
DEMO_USERNAME = "demo_student"
DEMO_PASSWORD = "123456"
DEMO_STUDENT_ID = "demo_2024_001"
DEMO_REAL_NAME = "演示学生"

# 固定 seed 让假编码可复现
RNG = np.random.RandomState(20240606)
FAKE_ENCODING = RNG.randn(ENCODING_DIM).astype(np.float32)
FAKE_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)
FAKE_FACE_LOC = (50, 200, 150, 100)  # (top, right, bottom, left)


def get_or_create_demo_student(auth: AuthService):
    """找 demo_student；找不到就注册。返回 (User, is_newly_registered)。"""
    with session_scope() as s:
        existing = UserDao(s).find_by_username(DEMO_USERNAME)
    if existing:
        print(f"[OK] demo_student 已存在: id={existing.id}, student_id={existing.student_id}")
        return existing, False
    user = auth.register(
        username=DEMO_USERNAME,
        password=DEMO_PASSWORD,
        real_name=DEMO_REAL_NAME,
        role="student",
        student_id=DEMO_STUDENT_ID,
    )
    print(f"[OK] demo_student 已注册: id={user.id}, student_id={user.student_id}")
    return user, True


def main() -> int:
    # 静音 SQLAlchemy 警告，保持输出干净
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    auth = AuthService()
    face_service = FaceService()

    # 1. 注册/复用 demo_student
    print("\n=== Step 1: 注册/复用 demo_student ===")
    user, _is_new = get_or_create_demo_student(auth)

    # 2. 清空旧编码（让 smoke 幂等）
    print("\n=== Step 2: 清空 demo_student 旧编码 ===")
    n_cleared = face_service.delete_user_encodings(user.id)
    print(f"[OK] 删除旧编码: {n_cleared} 行")

    # 3. 端到端：collect_for_user（patch face_locations/encodings 注入假数据）
    print("\n=== Step 3: collect_for_user 端到端 ===")
    mock_camera = MagicMock()
    mock_camera.is_running.return_value = True
    mock_camera.capture_one_frame.return_value = FAKE_FRAME

    cache = _FaceCache.get()
    with patch("src.services.face_service.face_locations",
               return_value=[FAKE_FACE_LOC]), \
         patch("src.services.face_service.face_encodings",
               return_value=[FAKE_ENCODING]):
        result = face_service.collect_for_user(
            user.id, mock_camera,
            n_samples=1,
            cache=cache,
        )

    if not result["ok"]:
        print(f"[FAIL] collect_for_user 失败: {result['error']}")
        return 1
    if result["saved"] != 1:
        print(f"[FAIL] 期望 saved=1, 实际 {result['saved']}")
        return 1
    if result["captured"] != 1:
        print(f"[FAIL] 期望 captured=1, 实际 {result['captured']}")
        return 1
    print(f"[OK] collect_for_user: captured={result['captured']}, saved={result['saved']}")

    # 4. 验证 DB 真的有 1 行
    print("\n=== Step 4: 验证 DB 持久化 ===")
    loaded = face_service.load_user_encodings(user.id)
    if len(loaded) != 1:
        print(f"[FAIL] 期望 DB 有 1 张编码, 实际 {len(loaded)}")
        return 1
    if not np.allclose(loaded[0], FAKE_ENCODING, atol=1e-5):
        print("[FAIL] 读回的编码与原始不一致（float32 序列化/反序列化有损？）")
        return 1
    print(f"[OK] DB 持久化 1 张编码，内容一致（shape={loaded[0].shape}, "
          f"dtype={loaded[0].dtype}）")

    # 5. 端到端：recognize() 验证能识别回 demo_student
    print("\n=== Step 5: recognize() 端到端 ===")
    # cache 已经被 collect_for_user 增量更新过；recognize 默认走单例 cache
    result = recognize(FAKE_ENCODING)
    if result is None:
        print("[FAIL] recognize 返回 None（cache 应有 demo_student 编码）")
        return 1
    recognized_id, distance = result
    if recognized_id != user.id:
        print(f"[FAIL] 期望命中 user_id={user.id}, 实际 {recognized_id}")
        return 1
    if distance > 1e-5:
        print(f"[FAIL] 距离过大（期望 ~0，实际 {distance}）")
        return 1
    print(f"[OK] recognize 命中 demo_student: id={recognized_id}, distance={distance:.2e}")

    # 6. 清理 dataset 下的 jpg（避免 demo 反复跑累积）
    print("\n=== Step 6: 清理 dataset/ 下的 jpg ===")
    user_dir = Config.DATASET_DIR / str(user.id)
    jpg_files = list(user_dir.glob("*.jpg")) if user_dir.exists() else []
    for f in jpg_files:
        f.unlink()
    if user_dir.exists():
        try:
            user_dir.rmdir()
        except OSError:
            pass  # 目录非空就不删
    print(f"[OK] 清理 jpg: {len(jpg_files)} 个")

    print("\n" + "=" * 60)
    print("✅ W3 Phase 6 端到端烟测全过")
    print("=" * 60)
    print(f"  - demo_student (id={user.id}, student_id={user.student_id}) 已就绪")
    print(f"  - 登录密码: {DEMO_PASSWORD}")
    print(f"  - face_encoding 表有 1 张假编码（用于演示识别链路）")
    print()
    print("下一步：")
    print("  - 跑 pytest tests/ -v  （29/29 全过即 Phase 6 完整验收）")
    print("  - 真起 GUI 走 docs/MANUAL_E2E.md 的 5 步手动验收")
    return 0


if __name__ == "__main__":
    sys.exit(main())
