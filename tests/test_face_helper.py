"""
tests/test_face_helper.py — face_helper 单元测试

测试 face_locations / face_encodings / face_distance / compare_faces
不依赖数据库，需要 dlib 模型文件已下载到 models/
"""
import numpy as np
import pytest

from src.utils.face_helper import (
    face_locations, face_encodings, face_distance, compare_faces,
)


def _blank_image() -> np.ndarray:
    """480x640 BGR 空白图（无人脸）"""
    return np.zeros((480, 640, 3), dtype=np.uint8)


def test_face_locations_blank_returns_empty():
    locs = face_locations(_blank_image())
    assert isinstance(locs, list)
    assert locs == []


def test_face_encodings_blank_returns_empty():
    encs = face_encodings(_blank_image())
    assert isinstance(encs, list)
    assert encs == []


def test_face_distance_empty_input():
    dist = face_distance([], np.zeros(128, dtype=np.float64))
    assert isinstance(dist, np.ndarray)
    assert dist.size == 0


def test_face_distance_self_is_zero():
    enc = np.random.rand(128).astype(np.float64)
    dist = face_distance([enc], enc)
    assert dist.shape == (1,)
    assert dist[0] < 1e-9


def test_face_distance_two_distinct_encodings():
    a = np.zeros(128, dtype=np.float64)
    b = np.ones(128, dtype=np.float64)
    dist = face_distance([a], b)
    # 128 维全 1 向量模长 = sqrt(128) ≈ 11.31
    assert 11.0 < dist[0] < 12.0


def test_compare_faces_threshold_logic():
    a = np.zeros(128, dtype=np.float64)
    b = a.copy() + 0.01  # 距离 0.01 < 0.45 → 匹配
    c = a.copy() + 1.0   # 距离 ≈ 11.3 > 0.45 → 不匹配

    matched = compare_faces([a, c], b, tolerance=0.45)
    assert matched == [True, False]


def test_face_encodings_known_locations_skips_detection():
    """传 known_face_locations 时不应再次调用 detector"""
    img = _blank_image()
    # 即使图片里没人脸，只要传 location 就走编码流程
    locs = [(10, 100, 110, 20)]
    encs = face_encodings(img, known_face_locations=locs)
    # 空白图编码后是 128 维零向量附近的向量
    assert len(encs) == 1
    assert encs[0].shape == (128,)


def test_face_encodings_dtype_is_float32():
    """锁住 dtype=float32：face.py 列注释 + W3 序列化都用 float32"""
    img = _blank_image()
    locs = [(10, 100, 110, 20)]
    encs = face_encodings(img, known_face_locations=locs)
    assert encs[0].dtype == np.float32, (
        f"face_helper 必须返回 float32，与 FaceEncoding 列注释一致；"
        f"当前是 {encs[0].dtype}。改回 float64 会让 W3 序列化/比对量纲不一致。"
    )
