"""
tests/test_face_cache.py — _FaceCache 类方法覆盖 (R16 补)

_FaceCache 是 src/services/face_service.py 里的进程内单例识别缓存,
W3 引入, W12 改用 remove_user(O(1)) 替代 refresh(全表), UI 集成加重.

历史覆盖:
  - test_face_service.py 用 _MockCache 测试 recognize() — 但 _FaceCache
    类本身的方法 (singleton / add / remove_user / all / refresh /
    reset_for_test) 从未直接测过.
  - test_face_admin_tab.py::test_face_cache_remove_user_clears_only_target
    测了 remove_user 一次, 但 reset_for_test / add / refresh 等没覆盖.

补覆盖 (5 项) — 都是纯内存操作, 不依赖 DB, 跑得快:
  - get() 单例
  - reset_for_test() 清实例
  - add(user_id, enc) 增量加, 不污染其他 user
  - remove_user(user_id) 只清该 user
  - all() 返 dict of {uid: [encs]}
  - refresh() 走 FaceService.load_all_user_encodings — 这里只验"调到了"
    (避免测实现细节, 只测 _FaceCache 自己公开契约)
"""
import uuid

import numpy as np
import pytest

from src.services.face_service import (
    ENCODING_DIM,
    _FaceCache,
    FaceService,
)


@pytest.fixture(autouse=True)
def _isolate_face_cache_singleton():
    """autouse: 每个 test 前 reset_for_test, 保证单例干净。

    _FaceCache 是进程内单例, 测试间不 reset 会污染 (前一个 test 加
    的 encoding 残留到后一个 test, 引起 leak 误判)。
    """
    _FaceCache.reset_for_test()
    yield
    _FaceCache.reset_for_test()


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _enc(seed: int) -> np.ndarray:
    """生成一个 128 维确定性编码 (同 seed = 同 vector)。"""
    return np.random.RandomState(seed).randn(ENCODING_DIM).astype(np.float32)


# ============================================================
# 1. Singleton & reset 契约
# ============================================================
def test_face_cache_get_returns_singleton_instance():
    """_FaceCache.get() 两次返同一实例 (singleton 契约)。

    背景: UI 层从 student_window / face_admin_tab / main.py 多处调
    _FaceCache.get() — 都拿到的是同一份缓存, 否则 flush 后其他处还看
    到旧数据。
    """
    a = _FaceCache.get()
    b = _FaceCache.get()
    assert a is b, "_FaceCache.get() 应返进程内单例"


def test_face_cache_reset_for_test_clears_instance():
    """reset_for_test() 后下次 get() 拿到新实例 (测试隔离必备)。"""
    a = _FaceCache.get()
    _FaceCache.reset_for_test()
    b = _FaceCache.get()
    assert a is not b, "reset_for_test 后应拿新实例"


# ============================================================
# 2. add / remove_user / all 三件套
# ============================================================
def test_face_cache_add_stores_in_per_user_list():
    """add(user_id, enc) 增量加, 同 user 多张编码累积进 list。"""
    cache = _FaceCache.get()
    assert cache.all() == {}, "新单例应空"

    cache.add(user_id=1, encoding=_enc(1))
    cache.add(user_id=1, encoding=_enc(2))
    cache.add(user_id=2, encoding=_enc(3))

    snap = cache.all()
    assert set(snap.keys()) == {1, 2}, f"应为 2 个 user, 实际 {snap.keys()}"
    assert len(snap[1]) == 2, f"user 1 应有 2 张编码, 实际 {len(snap[1])}"
    assert len(snap[2]) == 1
    # 内容应为传入的 vector (float32 dtype lock 住)
    np.testing.assert_array_equal(snap[1][0], _enc(1))
    np.testing.assert_array_equal(snap[1][1], _enc(2))
    np.testing.assert_array_equal(snap[2][0], _enc(3))


def test_face_cache_remove_user_clears_only_target():
    """remove_user(user_id) 只清该 user, 不影响其他人。"""
    cache = _FaceCache.get()
    cache.add(user_id=10, encoding=_enc(10))
    cache.add(user_id=20, encoding=_enc(20))
    cache.add(user_id=30, encoding=_enc(30))

    cache.remove_user(20)

    snap = cache.all()
    assert 10 in snap, "删 20 不应影响 user 10"
    assert 20 not in snap, "user 20 应被删"
    assert 30 in snap, "删 20 不应影响 user 30"


def test_face_cache_remove_user_nonexistent_is_safe():
    """remove_user 不存在的 user_id → no-op, 不抛异常。"""
    cache = _FaceCache.get()
    cache.add(user_id=1, encoding=_enc(1))

    # 应不抛
    cache.remove_user(999_999)
    snap = cache.all()
    assert 1 in snap, "remove_user 不存在的 id 不应删已有数据"


def test_face_cache_all_returns_dict():
    """all() 应返 dict (MutableMapping 契约), 不返 None 即便空。"""
    cache = _FaceCache.get()
    assert isinstance(cache.all(), dict), f"all() 应返 dict, 实际 {type(cache.all())}"
    assert cache.all() == {}, "空单例 all() 应返空 dict"


# ============================================================
# 3. refresh 调 FaceService.load_all_user_encodings (契约)
# ============================================================
def test_face_cache_refresh_calls_load_all_user_encodings(monkeypatch):
    """refresh() 走 FaceService.load_all_user_encodings, 不引用具体表。

    验证方法: monkey-patch FaceService.load_all_user_encodings → spy,
    调 _FaceCache.get().refresh(), 验 spy 被调一次。
    """
    from src.services import face_service as fs_mod

    called = {"n": 0}

    def fake_load():
        called["n"] += 1
        return {777: [_enc(99)]}  # 假装 DB 里 user 777 有编码

    monkeypatch.setattr(fs_mod.FaceService, "load_all_user_encodings",
                        staticmethod(fake_load))

    cache = _FaceCache.get()
    cache.refresh()

    assert called["n"] == 1, "refresh 应调一次 load_all_user_encodings"
    snap = cache.all()
    assert 777 in snap, "refresh 后缓存应含 load 返回的 user"
    assert len(snap[777]) == 1


def test_face_cache_refresh_replaces_entire_dict():
    """refresh() 是「全量重建」语义 — 不是 merge, 是 replace。

    这是 W12 改 remove_user 的反例: refresh() 仍走全表重载,
    适合初次启动; 已运行时单用户移除应走 remove_user.
    """
    from src.services import face_service as fs_mod

    # 第一次 load: user 1
    monkey_first = {"data": {1: [_enc(1)]}}

    def load_first():
        return monkey_first["data"]

    # 在测试内暂存旧的方法 (避免破坏其他测试)
    original = fs_mod.FaceService.load_all_user_encodings
    try:
        fs_mod.FaceService.load_all_user_encodings = staticmethod(load_first)

        cache = _FaceCache.get()
        cache.add(user_id=999, encoding=_enc(999))  # 缓存里有「残留」999
        assert 999 in cache.all()

        cache.refresh()
        snap = cache.all()
        assert 1 in snap, "refresh 后应有 user 1"
        assert 999 not in snap, "refresh 应 replace (含清理旧 user)"
    finally:
        fs_mod.FaceService.load_all_user_encodings = original
