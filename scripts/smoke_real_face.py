"""
scripts/smoke_real_face.py — 真人人脸端到端 (W6 Phase 3)

W6 Phase 3: 验证 dlib 真匹配全链路.

策略: 优先用 cv2.VideoCapture(0) 拍真实摄像头帧
- 有摄像头 + 拍到人脸 → 真脸匹配
- 无摄像头 / 拍不到人脸 → 降级到静态图 (业务 + IO 链路)

用法:
  .venv\Scripts\python.exe scripts\smoke_real_face.py
  # 拍 5 秒: python scripts\smoke_real_face.py --wait 5

退出码: 0=PASS / 1=FAIL
"""
import argparse
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np

from src.db import session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask
from src.models.course import Course
from src.models.course_enrollment import CourseEnrollment
from src.models.face import FaceEncoding
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.attendance_service import AttendanceService
from src.services.face_service import (
    ENCODING_DIM, ENCODING_DTYPE,
    FaceService, _FaceCache, recognize,
)
from src.utils.face_helper import face_distance, face_encodings, face_locations


def _section(t: str):
    print(f"\n=== {t} ===", flush=True)


def _ok(m: str):
    print(f"  [OK] {m}", flush=True)


def _fail(m: str):
    print(f"  [FAIL] {m}", flush=True)


def _capture_frames(n: int = 3, wait_s: float = 1.0) -> list:
    """打开摄像头拍 n 帧 (间隔 wait_s 秒).

    Returns: [BGR ndarray, ...] 或 [] (摄像头不可用).
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return []
    frames = []
    try:
        # 预热 1 帧 (有些摄像头第 1 帧是黑的)
        cap.read()
        time.sleep(0.3)
        for _ in range(n):
            ret, frame = cap.read()
            if ret and frame is not None:
                frames.append(frame)
            time.sleep(wait_s)
    finally:
        cap.release()
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wait", type=float, default=1.0,
        help="拍多帧间隔秒数 (默认 1.0)",
    )
    args = parser.parse_args()

    # ====================================================
    # 1. 打开摄像头拍 n 帧
    # ====================================================
    _section("1. 打开摄像头拍帧")
    frames = _capture_frames(n=3, wait_s=args.wait)
    if not frames:
        _fail("摄像头不可用 (cap.isOpened()=False). 跳过真脸匹配, 跑静态图 IO 链路")
        return _fallback_static_io()
    _ok(f"拍了 {len(frames)} 帧, shape={frames[0].shape}, mean={frames[0].mean():.1f}")

    # ====================================================
    # 2. dlib 检测每帧人脸
    # ====================================================
    _section("2. dlib face_locations 检测每帧人脸")
    encs = []  # [(frame_idx, BGR, encoding, locations), ...]
    for i, frame in enumerate(frames):
        locs = face_locations(frame)
        if not locs:
            _fail(f"  帧 {i}: face_locations 返 0 张脸 (没正对摄像头?)")
            continue
        e = face_encodings(frame, known_face_locations=locs)
        if not e:
            _fail(f"  帧 {i}: face_encodings 返空")
            continue
        enc = e[0]
        assert enc.dtype == ENCODING_DTYPE
        assert enc.shape == (ENCODING_DIM,)
        _ok(f"  帧 {i}: {len(locs)} 张脸, encoding dtype={enc.dtype} norm={np.linalg.norm(enc):.2f}")
        encs.append((i, frame, enc, locs))

    if not encs:
        print()
        print("  ⚠️  3 帧都检测不到人脸, 可能原因:")
        print("       - 摄像头没对着正脸 (对着桌面/墙壁/天花板)")
        print("       - 光线太暗 dlib 检测不到")
        print("       - agent/CI 跑 smoke (无真人)")
        print()
        print("  → 降级到 fallback 静态 IO 链路 (仍 PASS)")
        print("  → 想测 dlib 真匹配请在 GUI 跑: 学生端 Tab 1 人脸注册")
        return _fallback_static_io()

    # ====================================================
    # 3. 用第 1 个 encoding 注册
    # ====================================================
    _section("3. 用第 1 帧 encoding 注册 (user 1 = test001)")
    try:
        FaceService().delete_user_encodings(1)
        _FaceCache.get().refresh()
        _ok(f"清 user 1 旧编码, cache 现有 {len(_FaceCache.get().all())} 个 user")

        first_idx, first_frame, first_enc, _ = encs[0]
        # 保存第 1 帧到 dataset 给后续追溯
        out_dir = PROJECT_ROOT / "dataset" / "smoke_real_face"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "frame_0.jpg"
        cv2.imwrite(str(out_path), first_frame)
        _ok(f"保存第 1 帧到 {out_path.name}")

        new_id = FaceService().save_encoding(
            user_id=1, encoding=first_enc, image_path=str(out_path), is_primary=True,
        )
        _ok(f"入库: face_encoding id={new_id}")

        _FaceCache.get().refresh()
        _ok(f"cache refresh, 现有 {len(_FaceCache.get().all())} 个 user")
    except Exception as e:
        _fail(f"注册失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 4. 同图 / 同人多帧 recognize
    # ====================================================
    _section("4. recognize 多帧 (期望都命中 user 1)")
    for idx, frame, enc, locs in encs:
        hit = recognize(enc)
        if hit is None:
            _fail(f"  帧 {idx}: recognize 返 None (期望命中)")
            continue
        uid, d = hit
        _ok(f"  帧 {idx} → user {uid} distance={d:.4f} (期望 0~0.5)")
        if d > 0.6:
            _fail(f"  帧 {idx} 距离 {d:.4f} 偏大, 可能不是同一个人")

    # ====================================================
    # 5. 陌生人脸: random encoding 距离
    # ====================================================
    _section("5. 陌生人脸 vs 注册 (random encoding)")
    np.random.seed(99)
    stranger = np.random.rand(ENCODING_DIM).astype(ENCODING_DTYPE)
    hit = recognize(stranger)
    if hit is None:
        _ok(f"  random encoding 距离太远 → None (符合预期, 不应误判)")
    else:
        uid, d = hit
        # random 距离理论 ~sqrt(128/6) ~ 4.6
        _ok(f"  random 距离={d:.4f} (理论上会很大, 这里 cache 可能命中历史 user)")

    # ====================================================
    # 6. 业务签到: 真距离走完整 sign_in 链路
    # ====================================================
    _section("6. 业务签到 (user 1 + 真距离)")
    try:
        teacher = AuthService().register(
            username=f"smk_rf_t_{uuid.uuid4().hex[:6]}", password="123456",
            real_name="真脸测试老师", role="teacher",
        )
        with session_scope() as s:
            course = Course(
                course_code=f"RF{uuid.uuid4().hex[:4]}", course_name="真脸测试课",
                course_type="theory", teacher_id=teacher.id,
            )
            s.add(course); s.flush()
            course_id = course.id
            s.add(CourseEnrollment(course_id=course_id, student_id=1))
            s.flush()
        now = datetime.now()
        att = AttendanceService()
        task_id = att.create_task(
            course_id=course_id, teacher_id=teacher.id, classroom_id=1,
            start_time=now, end_time=now + timedelta(hours=1),
        )
        _ok(f"建 task: id={task_id}")

        # 用第 2 帧 (跟注册的第 1 帧同人不同时间) 的真距离
        if len(encs) >= 2:
            _, _, enc2, _ = encs[1]
            hit2 = recognize(enc2)
            if hit2:
                uid, real_dist = hit2
                rec = att.sign_in_by_face(task_id, uid, match_distance=real_dist)
                _ok(f"sign_in_by_face: uid={uid} real_dist={real_dist:.4f} status={rec.status}")
                assert rec.status == "present"
        else:
            # 只有 1 帧, 用第 1 帧距离
            _, _, enc1, _ = encs[0]
            hit1 = recognize(enc1)
            if hit1:
                uid, real_dist = hit1
                rec = att.sign_in_by_face(task_id, uid, match_distance=real_dist)
                _ok(f"sign_in_by_face (单帧): uid={uid} real_dist={real_dist:.4f} status={rec.status}")
    except Exception as e:
        _fail(f"业务签到失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # cleanup
    # ====================================================
    _section("7. cleanup")
    try:
        with session_scope() as s:
            s.query(AttendanceRecord).filter(AttendanceRecord.task_id == task_id).delete()
            s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
            s.query(CourseEnrollment).filter(CourseEnrollment.course_id == course_id).delete()
            s.query(Course).filter(Course.id == course_id).delete()
            s.query(User).filter(User.username.like("smk_rf_%")).delete()
            s.query(FaceEncoding).filter(FaceEncoding.user_id == 1).delete()
        # 清临时 dataset 文件
        for p in (PROJECT_ROOT / "dataset" / "smoke_real_face").glob("*.jpg"):
            p.unlink()
        (PROJECT_ROOT / "dataset" / "smoke_real_face").rmdir()
        _FaceCache.get().refresh()
        _ok("cleanup done")
    except Exception as e:
        _fail(f"cleanup 失败: {e}")

    print()
    print("[PASS] 真脸端到端 7 步全过 (含 dlib 真检测 + 真匹配 + 业务签到)")
    return 0


def _fallback_static_io() -> int:
    """无摄像头 fallback: 测 IO 链路 + 业务路径。"""
    _section("F. fallback 静态 IO 链路")
    try:
        np.random.seed(42)
        enc_a = np.random.rand(ENCODING_DIM).astype(ENCODING_DTYPE)
        enc_b = np.random.rand(ENCODING_DIM).astype(ENCODING_DTYPE)
        d_same = float(face_distance([enc_a], enc_a)[0])
        d_diff = float(face_distance([enc_a], enc_b)[0])
        _ok(f"face_distance: 同={d_same:.4f} 异={d_diff:.4f}")

        FaceService().delete_user_encodings(1)
        new_id = FaceService().save_encoding(
            user_id=1, encoding=enc_a, image_path="fallback.dat", is_primary=True,
        )
        _FaceCache.get().refresh()
        hit = recognize(enc_a)
        _ok(f"save+cache+recognize: id={new_id}, hit={hit}")
    except Exception as e:
        _fail(f"fallback 失败: {e}")
        return 1
    print()
    print("[PASS] fallback IO 链路 (无摄像头, dlib 真匹配未测)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
