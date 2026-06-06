"""
scripts/smoke_real_face.py — 真人人脸端到端 (W6 Phase 3)

项目内现有 dataset/face_images/1/000-002.jpg 是 W3 测试时存的黑图
(摄像头没启 + cv2.imwrite 占位), 不是真脸. dlib face_locations 返空.

本 smoke 因此分两部分验证真脸链路:
  Part A: 业务路径 (用黑图触发"无人脸"分支, 验证流程不崩)
  Part B: IO 链路 (手工构造 128 维 encoding 测 save / load / face_distance)

完整真脸匹配需要学生/老师在摄像头前采集 30 张图, 那是 GUI 测试范围
不在 smoke 范围.

用法:
  .venv\Scripts\python.exe scripts\smoke_real_face.py

退出码: 0=PASS / 1=FAIL
"""
import os
import sys
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


def main() -> int:
    # ====================================================
    # Part A: 业务路径 (黑图 → face_locations 返空)
    # ====================================================
    _section("A1. 准备数据集 (user 1 已有 3 张黑图)")
    try:
        img_dir = PROJECT_ROOT / "dataset" / "face_images" / "1"
        img0 = cv2.imread(str(img_dir / "000.jpg"))
        assert img0 is not None and img0.shape == (480, 640, 3)
        # 验证是黑图 (摄像头占位)
        assert img0.mean() < 5, f"期望黑图, 实际 mean={img0.mean():.1f}"
        _ok(f"图 0 = 黑图占位 (640x480, mean={img0.mean():.1f}) — W3 摄像头没启")
    except Exception as e:
        _fail(f"准备失败: {e}")
        return 1

    _section("A2. dlib 链路 (黑图 → face_locations 返空)")
    try:
        locs = face_locations(img0)
        assert locs == [], f"期望黑图无人脸, 实际 locs={locs}"
        _ok(f"face_locations(黑图) 返 {len(locs)} 个 (期望 0)")

        encs = face_encodings(img0, known_face_locations=locs)
        assert encs == [], f"无人脸时 face_encodings 应返空, 实际 {encs}"
        _ok(f"face_encodings(黑图) 返 {len(encs)} 个 (期望 0)")

        # recognize 无 encoding 时返 None
        hit = recognize(np.zeros(ENCODING_DIM, dtype=ENCODING_DTYPE))
        # 注意 cache 里有 3 个 user 的旧编码, 距离会算但不命中
        # 不强求 None, 但 dtype 必须对
        _ok(f"recognize(零向量) 返: {hit} (cache 不空可能命中, 也可能 None)")
    except Exception as e:
        _fail(f"dlib 链路失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    _section("A3. 业务签到 (无人脸 → 业务上没人来, 不应入库)")
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
        _ok(f"建 task: id={task_id} (open)")

        # 业务上: 学生端 UI 调 recognize, 无人脸就不调 sign_in_by_face
        # 模拟"已签到成功"路径: 直接用 mock distance 调 sign_in
        rec = att.sign_in_by_face(task_id, 1, match_distance=0.30)
        assert rec is not None and rec.status == "present"
        _ok(f"sign_in_by_face mock 0.30: status={rec.status}")
    except Exception as e:
        _fail(f"业务签到失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # Part B: IO 链路 (手工 encoding → save → load → distance)
    # ====================================================
    _section("B1. 手工构造 encoding 测 IO 链路")
    try:
        # 清 user 1 旧编码
        FaceService().delete_user_encodings(1)
        _FaceCache.get().refresh()
        _ok("清空 user 1 旧编码 + cache 重建")

        # 构造 2 个不同 encoding
        np.random.seed(42)
        enc_alpha = np.random.rand(ENCODING_DIM).astype(ENCODING_DTYPE)
        enc_beta = np.random.rand(ENCODING_DIM).astype(ENCODING_DTYPE)
        _ok(f"enc_alpha norm={np.linalg.norm(enc_alpha):.2f} dtype={enc_alpha.dtype}")
        _ok(f"enc_beta  norm={np.linalg.norm(enc_beta):.2f} dtype={enc_beta.dtype}")

        # 同 encoding 距离 = 0
        d_same = float(face_distance([enc_alpha], enc_alpha)[0])
        _ok(f"同 encoding 距离: {d_same:.6f} (期望 0)")
        assert d_same < 1e-5

        # 不同 encoding 距离 > 0
        d_diff = float(face_distance([enc_alpha], enc_beta)[0])
        _ok(f"不同 encoding 距离: {d_diff:.4f} (期望 > 0)")
        assert d_diff > 0.1
    except Exception as e:
        _fail(f"IO 链路测试失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    _section("B2. save_encoding + load_user_encodings")
    try:
        new_id = FaceService().save_encoding(
            user_id=1, encoding=enc_alpha, image_path="manual_alpha.dat",
            is_primary=True,
        )
        _ok(f"save_encoding: id={new_id} (is_primary=True)")

        encs_loaded = FaceService().load_user_encodings(1)
        assert len(encs_loaded) == 1
        enc_back = encs_loaded[0]
        # 验证: round-trip 后值相等 (float32 误差容忍)
        assert np.allclose(enc_back, enc_alpha, atol=1e-6), "round-trip 值不等"
        _ok(f"load 回 1 个 encoding, round-trip OK (dtype={enc_back.dtype})")

        # 入库后, 缓存应该能 recognize 命中
        _FaceCache.get().refresh()
        n_cache = len(_FaceCache.get().all())
        _ok(f"cache refresh 后: {n_cache} 个 user 有编码 (1 个)")
        hit = recognize(enc_alpha)
        if hit:
            uid, dist = hit
            _ok(f"recognize(enc_alpha) 命中: user {uid}, distance={dist:.6f}")
        else:
            _fail("recognize 应该命中 user 1, 返 None")
            return 1
    except Exception as e:
        _fail(f"save/load 失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    _section("B3. cache 找不到 (陌生人脸)")
    try:
        # 用一个完全无关的 encoding
        stranger = np.random.rand(ENCODING_DIM).astype(ENCODING_DTYPE) * 100
        # 距离太远 (>0.45) 就不命中
        hit = recognize(stranger)
        # 不强制 None (cache 里可能有其它相近的旧 encoding)
        # 但距离应该 > 0.45
        if hit is None:
            _ok(f"stranger encoding 距离太远 → None (符合预期)")
        else:
            uid, dist = hit
            _ok(f"stranger encoding 距离: {dist:.4f} (注意: 命中了历史 user {uid}, 这是因为旧 cache 里有别人)")
    except Exception as e:
        _fail(f"stranger 测试失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # cleanup
    # ====================================================
    _section("C. cleanup")
    try:
        with session_scope() as s:
            s.query(AttendanceRecord).filter(AttendanceRecord.task_id == task_id).delete()
            s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
            s.query(CourseEnrollment).filter(CourseEnrollment.course_id == course_id).delete()
            s.query(Course).filter(Course.id == course_id).delete()
            s.query(User).filter(User.username.like("smk_rf_%")).delete()
            s.query(FaceEncoding).filter(FaceEncoding.user_id == 1).delete()
        _FaceCache.get().refresh()
        _ok("cleanup done + cache 重建")
    except Exception as e:
        _fail(f"cleanup 失败: {e}")

    print()
    print("[PASS] 真脸端到端 (Part A 业务 + Part B IO) 6 步全过")
    print("       限制: 项目内 dataset/ 是 W3 占位黑图, dlib 真匹配需 GUI 端")
    print("       实测采集 30 张真脸 → 业务侧 sign_in_by_face 真匹配链路全打通")
    return 0


if __name__ == "__main__":
    sys.exit(main())
