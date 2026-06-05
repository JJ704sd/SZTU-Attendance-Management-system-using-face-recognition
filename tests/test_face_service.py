"""
tests/test_face_service.py — FaceService 单元测试
- 需要 MySQL 可用 + .env 配置正确
- 每个测试用 UUID 用户名/student_id 避免冲突
"""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.config import Config
from src.services.auth_service import AuthService
from src.services.face_service import (
    FaceService,
    encode_to_bytes,
    decode_from_bytes,
    ENCODING_DIM,
)


@pytest.fixture
def auth() -> AuthService:
    return AuthService()


@pytest.fixture
def face() -> FaceService:
    return FaceService()


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_user(auth: AuthService, face: FaceService):
    """新建一个学生用户，测试结束后清理该用户的编码。"""
    user = auth.register(
        username=_uni("u"),
        password="123456",
        real_name="测脸",
        role="student",
        student_id=_uni("s"),
    )
    yield user
    # cleanup
    face.delete_user_encodings(user.id)


# -----------------------------------------------------
# 1. encode/decode 往返一致性
# -----------------------------------------------------
def test_encode_decode_roundtrip():
    arr = np.random.RandomState(42).randn(ENCODING_DIM).astype(np.float32)
    blob = encode_to_bytes(arr)
    assert len(blob) == ENCODING_DIM * 4  # float32 = 4 bytes
    decoded = decode_from_bytes(blob)
    assert decoded.dtype == np.float32
    assert decoded.shape == (ENCODING_DIM,)
    np.testing.assert_array_equal(arr, decoded)


def test_encode_rejects_wrong_shape():
    with pytest.raises(ValueError, match="expected shape"):
        encode_to_bytes(np.zeros(64, dtype=np.float32))


# -----------------------------------------------------
# 2. save + load
# -----------------------------------------------------
def test_save_load_encoding(face: FaceService, test_user):
    arr = np.random.RandomState(1).randn(ENCODING_DIM).astype(np.float32)
    face.save_encoding(test_user.id, arr, image_path="dataset/test/001.jpg")

    loaded = face.load_user_encodings(test_user.id)
    assert len(loaded) == 1
    np.testing.assert_array_equal(loaded[0], arr)


# -----------------------------------------------------
# 3. delete
# -----------------------------------------------------
def test_delete_user_encodings(face: FaceService, test_user):
    arr1 = np.random.RandomState(2).randn(ENCODING_DIM).astype(np.float32)
    arr2 = np.random.RandomState(3).randn(ENCODING_DIM).astype(np.float32)
    face.save_encoding(test_user.id, arr1, image_path="p1.jpg")
    face.save_encoding(test_user.id, arr2, image_path="p2.jpg")
    assert len(face.load_user_encodings(test_user.id)) == 2

    n = face.delete_user_encodings(test_user.id)
    assert n == 2
    assert face.load_user_encodings(test_user.id) == []


# -----------------------------------------------------
# 4. set_primary
# -----------------------------------------------------
def test_set_primary(face: FaceService, test_user, auth: AuthService):
    # 直接用 dao 设 set_primary（save_encoding 在 is_primary=True 时已内部调过，
    # 但单独测 dao 行为更稳）
    from src.db import session_scope
    from src.dao.face_dao import FaceEncodingDao

    a1 = np.random.RandomState(4).randn(ENCODING_DIM).astype(np.float32)
    a2 = np.random.RandomState(5).randn(ENCODING_DIM).astype(np.float32)
    id1 = face.save_encoding(test_user.id, a1, image_path="p1.jpg", is_primary=True)
    id2 = face.save_encoding(test_user.id, a2, image_path="p2.jpg", is_primary=False)
    # id1 应为主
    with session_scope() as s:
        rows = FaceEncodingDao(s).find_by_user(test_user.id)
        prim = [r for r in rows if r.is_primary == 1]
        assert len(prim) == 1
        assert prim[0].id == id1

    # 切换主图到 id2
    with session_scope() as s:
        FaceEncodingDao(s).set_primary(id2, test_user.id)
        rows = FaceEncodingDao(s).find_by_user(test_user.id)
        prim = [r for r in rows if r.is_primary == 1]
        assert len(prim) == 1
        assert prim[0].id == id2


# -----------------------------------------------------
# 5. collect_for_user — mock 摄像头 + face_helper，
#    验证 DB 行数、文件数、进度回调、返回值
# -----------------------------------------------------
def test_collect_for_user_writes_encodings(face: FaceService, test_user):
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    fake_frame[:] = (200, 100, 50)  # 任意 BGR

    mock_camera = MagicMock()
    mock_camera.is_running.return_value = True
    mock_camera.capture_one_frame.return_value = fake_frame

    fake_encoding = np.random.RandomState(99).randn(ENCODING_DIM).astype(np.float32)
    n_samples = 3
    progress_calls = []

    with patch("src.services.face_service.face_locations",
               return_value=[(10, 100, 110, 20)]), \
         patch("src.services.face_service.face_encodings",
               return_value=[fake_encoding]):
        result = face.collect_for_user(
            test_user.id, mock_camera,
            n_samples=n_samples,
            on_progress=lambda c, t: progress_calls.append((c, t)),
        )

    # 1) 返回值
    assert result == {"ok": True, "captured": n_samples, "saved": n_samples, "error": None}

    # 2) DB 行数 + 内容
    encodings = face.load_user_encodings(test_user.id)
    assert len(encodings) == n_samples
    np.testing.assert_array_equal(encodings[0], fake_encoding)

    # 3) 文件数 + 命名
    user_dir = Path(Config.DATASET_DIR) / str(test_user.id)
    jpg_files = sorted(user_dir.glob("*.jpg"))
    try:
        assert len(jpg_files) == n_samples
        assert jpg_files[0].name == "000.jpg"
        assert jpg_files[-1].name == f"{n_samples - 1:03d}.jpg"
    finally:
        # 清理 jpg + 用户目录（test_user fixture 只清 DB，不清文件）
        for f in jpg_files:
            f.unlink()
        if user_dir.exists():
            user_dir.rmdir()

    # 4) 进度回调每次都触发
    assert progress_calls == [(1, n_samples), (2, n_samples), (3, n_samples)]

    # 5) 摄像头被调了 n_samples 次（连续有脸时一轮一张）
    assert mock_camera.capture_one_frame.call_count == n_samples


# -----------------------------------------------------
# 6. 回归：face_encodings 持续返回 [] 时不能死循环
#    （历史 bug：consecutive_no_face 在 encs 检查前已清零 + encs 失败时不计数）
# -----------------------------------------------------
def test_collect_for_user_terminates_when_encodings_empty(face: FaceService, test_user):
    """face_locations 命中但 face_encodings 返回 [] 的极端场景：必须超时退出。"""
    import threading
    from src.services import face_service as fs_mod

    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_camera = MagicMock()
    mock_camera.is_running.return_value = True
    mock_camera.capture_one_frame.return_value = fake_frame

    result_holder = {}
    user_dir = Path(Config.DATASET_DIR) / str(test_user.id)

    def run():
        with patch("src.services.face_service.face_locations",
                   return_value=[(10, 100, 110, 20)]), \
             patch("src.services.face_service.face_encodings",
                   return_value=[]):
            result_holder["res"] = face.collect_for_user(
                test_user.id, mock_camera, n_samples=5,
            )

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=10.0)
    try:
        assert not t.is_alive(), "collect_for_user 死循环：face_encodings 返回 [] 超过 10 秒未退出"

        res = result_holder["res"]
        assert res["ok"] is False
        assert res["captured"] == 0
        assert res["saved"] == 0
        assert "采集超时" in res["error"]
        # 应在 NO_FACE_LIMIT 次循环内退出
        assert mock_camera.capture_one_frame.call_count == fs_mod.NO_FACE_LIMIT
    finally:
        if user_dir.exists():
            user_dir.rmdir()
