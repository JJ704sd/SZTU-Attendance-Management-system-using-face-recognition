"""
tests/test_face_admin_tab.py — FaceAdminTab (W12)

测试管理员 Tab 5「人脸管理」核心逻辑:
- refresh() 正确加载用户 + 编码数
- _do_delete_db() 删 face_encoding 行
- _do_delete_files() 删 dataset 目录
- _do_refresh_cache() 调 _FaceCache.refresh

测试策略:
- offscreen Qt + 真 DB (跟 conftest.py 共享 .env)
- 每次测试用 UUID 用户 + 临时 dataset 目录, 不污染其他测试
"""
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CAMERA_COLOR_MODE", "bgr")

from PyQt5.QtWidgets import QApplication

from src.config import Config
from src.db import session_scope
from src.dao.face_dao import FaceEncodingDao
from src.models.face import FaceEncoding
from src.models.user import User
from src.services.auth_service import AuthService


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def temp_dataset_dir(monkeypatch):
    """临时 dataset 目录, 测试完清理."""
    tmp = Path(tempfile.mkdtemp(prefix="face_admin_test_"))
    monkeypatch.setattr(Config, "DATASET_DIR", tmp)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_user_with_encodings(temp_dataset_dir):
    """建一个测试用户 + 3 条 face_encoding + 3 个 jpg 文件."""
    auth = AuthService()
    face_dao_factory = FaceEncodingDao

    # UUID 用户名避免冲突
    username = f"faceadm_{uuid.uuid4().hex[:6]}"
    user = auth.register(
        username=username, password="123456", real_name="测试同学",
        role="student", student_id=f"S{uuid.uuid4().hex[:6]}",
    )

    # 建 user_dir + 3 个 jpg
    user_dir = temp_dataset_dir / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    for i in range(3):
        (user_dir / f"{i:03d}.jpg").write_bytes(b"fake_jpg_content")

    # 入库 3 条 face_encoding
    import numpy as np
    from src.services.face_service import encode_to_bytes
    for i in range(3):
        enc = np.random.rand(128).astype(np.float32)
        with session_scope() as s:
            s.add(FaceEncoding(
                user_id=user.id,
                encoding=encode_to_bytes(enc),
                image_path=str(user_dir / f"{i:03d}.jpg"),
                is_primary=1 if i == 0 else 0,
            ))

    yield user
    # cleanup: 删 user + encodings
    with session_scope() as s:
        s.query(FaceEncoding).filter(FaceEncoding.user_id == user.id).delete()
        s.query(User).filter(User.id == user.id).delete()


# =============================================================================
# W12: refresh / _do_delete_db / _do_delete_files / _do_refresh_cache
# =============================================================================
def test_refresh_loads_users_with_encoding_counts(qapp, test_user_with_encodings):
    """refresh 加载用户列表, encoding 数 = 3."""
    from src.ui.widgets.face_admin_tab import FaceAdminTab
    tab = FaceAdminTab()
    tab.refresh()
    # 表里至少包含测试用户
    found = False
    for row in range(tab.table.rowCount()):
        if tab.table.item(row, 1) and tab.table.item(row, 1).text() == test_user_with_encodings.username:
            count = int(tab.table.item(row, 4).text())
            assert count == 3, f"期望 3 条编码, 实际 {count}"
            found = True
            break
    assert found, f"测试用户 {test_user_with_encodings.username} 没出现在表里"


def test_do_delete_db_removes_face_encoding_rows(qapp, test_user_with_encodings):
    """_do_delete_db 删 face_encoding 行, 返回删除条数 = 3."""
    from src.ui.widgets.face_admin_tab import FaceAdminTab
    tab = FaceAdminTab()
    n = tab._do_delete_db(test_user_with_encodings.id)
    assert n == 3, f"期望删 3 条, 实际删 {n}"
    # DB 里确认
    with session_scope() as s:
        remaining = FaceEncodingDao(s).find_by_user(test_user_with_encodings.id)
        assert len(remaining) == 0, f"期望 DB 里 0 条, 实际 {len(remaining)}"


def test_do_delete_files_removes_dataset_dir(qapp, test_user_with_encodings, temp_dataset_dir):
    """_do_delete_files 删 dataset/{user_id}/ 目录, 返回文件数 = 3."""
    from src.ui.widgets.face_admin_tab import FaceAdminTab
    user_dir = temp_dataset_dir / str(test_user_with_encodings.id)
    assert user_dir.exists() and len(list(user_dir.glob("*.jpg"))) == 3
    tab = FaceAdminTab()
    n = tab._do_delete_files(test_user_with_encodings.id)
    assert n == 3, f"期望删 3 个文件, 实际删 {n}"
    # 目录应被 rmtree
    assert not user_dir.exists(), f"目录 {user_dir} 应该被删"


def test_do_delete_files_handles_missing_dir(qapp, test_user_with_encodings, temp_dataset_dir):
    """_do_delete_files 用户没 dataset 目录时返 0, 不抛异常."""
    from src.ui.widgets.face_admin_tab import FaceAdminTab
    # 删目录模拟"没数据"
    user_dir = temp_dataset_dir / str(test_user_with_encodings.id)
    if user_dir.exists():
        shutil.rmtree(user_dir)
    tab = FaceAdminTab()
    n = tab._do_delete_files(test_user_with_encodings.id)
    assert n == 0


def test_do_remove_user_from_cache_calls_remove_user(qapp):
    """W12: _do_remove_user_from_cache 调 _FaceCache.get().remove_user(user_id), 不调 refresh().

    背景: 之前 _do_refresh_cache 调 refresh() 全表重载, 158 个用户时主线程假死几秒.
    改用 remove_user(user_id) 只弹该用户, O(1), 不卡 GUI.
    """
    from src.ui.widgets.face_admin_tab import FaceAdminTab
    tab = FaceAdminTab()
    with patch("src.services.face_service._FaceCache") as mock_cache_cls:
        mock_instance = MagicMock()
        mock_cache_cls.get.return_value = mock_instance
        tab._do_remove_user_from_cache(user_id=42)
        # 验证 _FaceCache.get().remove_user(42) 被调
        mock_cache_cls.get.assert_called_once()
        mock_instance.remove_user.assert_called_once_with(42)
        # 关键: 不应该调 refresh() (避免全表重载)
        mock_instance.refresh.assert_not_called()


def test_count_encodings_returns_correct_count(qapp, test_user_with_encodings):
    """_count_encodings 返该用户的编码数."""
    from src.ui.widgets.face_admin_tab import FaceAdminTab
    tab = FaceAdminTab()
    n = tab._count_encodings(test_user_with_encodings.id)
    assert n == 3


# =============================================================================
# W12 v6: 学生端 _on_clear_my_face (复用管理员删除逻辑, 但限定 self.user.id)
# =============================================================================
def test_face_service_delete_user_encodings_removes_all(qapp, test_user_with_encodings):
    """FaceService.delete_user_encodings 是后端真删, 学生端 _on_clear_my_face 调它."""
    from src.services.face_service import FaceService
    n = FaceService().delete_user_encodings(test_user_with_encodings.id)
    assert n == 3
    # DB 里确认清空
    remaining = FaceService().load_user_encodings(test_user_with_encodings.id)
    assert len(remaining) == 0


def test_face_cache_remove_user_clears_only_target(qapp, test_user_with_encodings):
    """_FaceCache.remove_user 只清该用户, 不影响其他人."""
    from src.services.face_service import _FaceCache, FaceService
    # 强制 refresh 让 cache 有这个用户
    _FaceCache.get().refresh()
    cache = _FaceCache.get().all()
    assert test_user_with_encodings.id in cache
    # remove_user 应该只清这一个
    _FaceCache.get().remove_user(test_user_with_encodings.id)
    cache = _FaceCache.get().all()
    assert test_user_with_encodings.id not in cache
