"""
services/face_service.py — 人脸识别服务

Phase 1 范围：序列化工具 + 单人/全量加载 + 删除。
Phase 3 范围：collect_for_user 采集编排（dlib 检测 + 落盘 + 入库）。
Phase 4 会再加：内存缓存 _FaceCache + recognize()。
"""
import logging
import threading
from typing import Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

import cv2
import numpy as np

from src.config import Config
from src.dao.face_dao import FaceEncodingDao
from src.db import session_scope
from src.models.face import FaceEncoding
from src.utils.face_helper import face_distance, face_encodings, face_locations

if TYPE_CHECKING:
    from src.ui.widgets.camera_widget import CameraWidget

log = logging.getLogger(__name__)

# 128 维 dlib 人脸编码向量；与 models/face.py 的 encoding 列注释保持一致
ENCODING_DIM = 128
ENCODING_DTYPE = np.float32  # 序列化/反序列化统一 float32（见 CLAUDE.md 技术决策）

# 连续多少帧没检测到脸就放弃（避免无限循环）
NO_FACE_LIMIT = 30


def encode_to_bytes(arr: np.ndarray) -> bytes:
    """128 维向量 → 512 字节（float32 little-endian）"""
    if arr.shape != (ENCODING_DIM,):
        raise ValueError(f"expected shape ({ENCODING_DIM},), got {arr.shape}")
    return arr.astype(ENCODING_DTYPE).tobytes()


def decode_from_bytes(b: bytes) -> np.ndarray:
    """512 字节 → 128 维 float32 向量"""
    if len(b) != ENCODING_DIM * ENCODING_DTYPE().itemsize:
        raise ValueError(
            f"expected {ENCODING_DIM * ENCODING_DTYPE().itemsize} bytes, got {len(b)}"
        )
    return np.frombuffer(b, dtype=ENCODING_DTYPE)


class FaceService:
    """人脸编码的存取；调用方传 numpy 数组，内部负责序列化/落盘。"""

    # -----------------------------------------------------
    # 单条写入 / 读取
    # -----------------------------------------------------
    def save_encoding(
        self,
        user_id: int,
        encoding: np.ndarray,
        image_path: str,
        is_primary: bool = False,
    ) -> int:
        """写入一条编码，返回新行 id。is_primary=True 时自动把同用户其它行置 0。"""
        blob = encode_to_bytes(encoding)
        with session_scope() as s:
            row = FaceEncoding(
                user_id=user_id,
                encoding=blob,
                image_path=image_path,
                is_primary=1 if is_primary else 0,
            )
            s.add(row)
            s.flush()
            new_id = row.id
            if is_primary:
                # 用同 session 的 dao 完成 set_primary（避免再开一个 session）
                FaceEncodingDao(s).set_primary(new_id, user_id)
            return new_id

    def load_user_encodings(self, user_id: int) -> List[np.ndarray]:
        """加载某用户所有编码（已反序列化为 numpy）。"""
        with session_scope() as s:
            dao = FaceEncodingDao(s)
            rows = dao.find_by_user(user_id)
            return [decode_from_bytes(r.encoding) for r in rows]

    def delete_user_encodings(self, user_id: int) -> int:
        """删除某用户所有编码，返回删除行数。"""
        with session_scope() as s:
            return FaceEncodingDao(s).delete_by_user(user_id)

    # -----------------------------------------------------
    # 全量加载（识别缓存用，Phase 4 会被 _FaceCache 包装）
    # -----------------------------------------------------
    def load_all_user_encodings(self) -> Dict[int, List[np.ndarray]]:
        """一次拉所有 {user_id: [encodings]}。N 大时（>1k 用户）应换 Redis。"""
        with session_scope() as s:
            rows = s.query(FaceEncoding).all()
            out: Dict[int, List[np.ndarray]] = {}
            for r in rows:
                out.setdefault(r.user_id, []).append(decode_from_bytes(r.encoding))
            return out

    # -----------------------------------------------------
    # 采集编排（Phase 3）
    # -----------------------------------------------------
    def collect_for_user(
        self,
        user_id: int,
        camera: "CameraWidget",
        n_samples: int = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        cache: Optional["_FaceCache"] = None,
        stop_event: Optional["threading.Event"] = None,
    ) -> dict:
        """
        从 camera 抓 n_samples 张人脸图，编码后入库。
        返回: {"ok": bool, "captured": int, "saved": int, "error": str|None}

        cache: 可选；传入 _FaceCache.get() 时会在保存编码后增量更新缓存。
               传 None 时不更新缓存（默认；测试场景避免污染单例）。
               UI 层（Phase 5）应传 cache=_FaceCache.get()。

        stop_event: 可选；threading.Event()。UI 取消采集时 .set()，
                    collect_for_user 在每次循环开头检查。设了之后下一轮立即
                    返回 {"ok": False, "error": "用户取消"}。默认 None = 不支持取消。

        ⚠️ 调用方必须在 Qt 工作线程里调（避免阻塞 UI），
        on_progress 回调里如果直接 setText/setValue 会段错误，
        正确做法：把 on_progress 设成 QObject 的 pyqtSignal.emit，
        UI 端用 Qt.QueuedConnection 跨线程更新。
        """
        if n_samples is None:
            n_samples = Config.FACE_SAMPLE_COUNT
        captured = 0
        saved = 0
        # 计数任何一次循环没拿到可入库样本（无帧 / 无脸 / 无编码）；
        # 只在成功落盘后清零，避免 face_encodings 持续返回 [] 时死循环。
        consecutive_no_progress = 0

        user_dir = Config.DATASET_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        while captured < n_samples:
            if stop_event is not None and stop_event.is_set():
                return {"ok": False, "captured": captured, "saved": saved,
                        "error": "用户取消"}
            if not camera.is_running():
                return {"ok": False, "captured": captured, "saved": saved,
                        "error": "摄像头断开"}

            frame = camera.capture_one_frame()
            if frame is None:
                consecutive_no_progress += 1
                if consecutive_no_progress >= NO_FACE_LIMIT:
                    return {"ok": False, "captured": captured, "saved": saved,
                            "error": f"采集超时：连续 {NO_FACE_LIMIT} 帧未获取到人脸样本"}
                continue

            locs = face_locations(frame)
            if not locs:
                consecutive_no_progress += 1
                if consecutive_no_progress >= NO_FACE_LIMIT:
                    return {"ok": False, "captured": captured, "saved": saved,
                            "error": f"采集超时：连续 {NO_FACE_LIMIT} 帧未获取到人脸样本"}
                continue

            encs = face_encodings(frame, known_face_locations=locs)
            if not encs:
                consecutive_no_progress += 1
                if consecutive_no_progress >= NO_FACE_LIMIT:
                    return {"ok": False, "captured": captured, "saved": saved,
                            "error": f"采集超时：连续 {NO_FACE_LIMIT} 帧未获取到人脸样本"}
                continue

            # 1) 原图落盘
            img_path = user_dir / f"{captured:03d}.jpg"
            try:
                ok = cv2.imwrite(str(img_path), frame)
            except Exception as e:
                log.exception("采集：imwrite 失败")
                return {"ok": False, "captured": captured, "saved": saved,
                        "error": f"磁盘写入失败: {e}"}
            if not ok:
                return {"ok": False, "captured": captured, "saved": saved,
                        "error": "磁盘写入失败: cv2.imwrite 返 False"}

            # 2) 编码入库
            try:
                self.save_encoding(user_id, encs[0], str(img_path))
            except Exception as e:
                log.exception("采集：save_encoding 失败")
                return {"ok": False, "captured": captured, "saved": saved,
                        "error": f"数据库写入失败: {e}"}

            # 2.5) 增量更新缓存（如有）
            if cache is not None:
                cache.add(user_id, encs[0])

            captured += 1
            saved += 1
            consecutive_no_progress = 0
            if on_progress is not None:
                try:
                    on_progress(captured, n_samples)
                except Exception:
                    log.exception("on_progress 回调异常（吞掉，避免中断采集）")

        return {"ok": True, "captured": captured, "saved": saved, "error": None}


# =====================================================
# Phase 4：进程内识别缓存 + recognize()
# =====================================================
class _FaceCache:
    """
    进程内单例，启动时全量加载，采集时增量加。
    演示场景下 N<1000，dict 读写在 CPython GIL 下基本安全；
    生产环境 > 1k 用户应换 Redis。
    """
    _instance: Optional["_FaceCache"] = None

    def __init__(self):
        self._encodings: Dict[int, List[np.ndarray]] = {}

    @classmethod
    def get(cls) -> "_FaceCache":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_test(cls) -> None:
        """测试辅助：清空单例。生产代码不要调。"""
        cls._instance = None

    def refresh(self) -> None:
        """全量重建。从 DB 拉所有 {user_id: [encodings]}。"""
        self._encodings = FaceService().load_all_user_encodings()

    def add(self, user_id: int, encoding: np.ndarray) -> None:
        self._encodings.setdefault(user_id, []).append(encoding)

    def remove_user(self, user_id: int) -> None:
        self._encodings.pop(user_id, None)

    def all(self) -> Dict[int, List[np.ndarray]]:
        return self._encodings


def recognize(encoding: np.ndarray,
              cache: Optional[_FaceCache] = None) -> Optional[Tuple[int, float]]:
    """
    在 cache 中找最近用户，距离 ≤ 阈值算命中。
    返回 (user_id, distance) 或 None（空缓存 / 全员超阈值）。

    cache: 可选；传 None 时用 _FaceCache.get() 单例。测试时传 mock cache。
    """
    if cache is None:
        cache = _FaceCache.get()

    encodings_map = cache.all()
    if not encodings_map:
        log.warning("recognize: 缓存为空（库中可能还没有任何人脸编码）")
        return None

    best_user: Optional[int] = None
    best_dist = float("inf")
    for user_id, encs in encodings_map.items():
        if not encs:
            continue
        dists = face_distance(encs, encoding)
        d = float(dists.min())
        if d < best_dist:
            best_dist = d
            best_user = user_id

    if best_user is None or best_dist > Config.FACE_MATCH_THRESHOLD:
        return None
    return best_user, best_dist
