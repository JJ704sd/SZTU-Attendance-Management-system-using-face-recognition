"""
utils/face_helper.py — 人脸检测与编码工具
基于 dlib + opencv，自行实现 face_recognition 风格的 4 个核心函数
原因：face_recognition 1.3.0 在 Windows + Python 3.13 上有 cmake 编码编译坑，
dlib-bin 20.0.1 已经装好（cp313 wheel），所以直接用 dlib。

W5 改动：路径走 src.utils.paths 单例（兼容 PyInstaller 打包）
"""
import bz2
import urllib.request
from pathlib import Path
from typing import List, Tuple, Optional

import cv2
import numpy as np
import dlib

# 路径单例：dev 是项目根，打包后是 exe 同级目录
from src.utils.paths import MODELS_DIR  # noqa: F401

SHAPE_PREDICTOR_URL = (
    "https://github.com/davisking/dlib-models/raw/master/"
    "shape_predictor_68_face_landmarks.dat.bz2"
)
FACE_REC_MODEL_URL = (
    "https://github.com/davisking/dlib-models/raw/master/"
    "dlib_face_recognition_resnet_model_v1.dat.bz2"
)

# W15+: 国内镜像 fallback. GitHub raw 国内经常被墙/超时, 失败时自动试 gitee 镜像.
# gitee 镜像由 community 维护, 偶尔会同步延迟; 失败时再走原始 GitHub URL.
SHAPE_PREDICTOR_URL_GITEE = (
    "https://gitee.com/anyxch/dlib-models-raw/raw/master/"
    "shape_predictor_68_face_landmarks.dat.bz2"
)
FACE_REC_MODEL_URL_GITEE = (
    "https://gitee.com/anyxch/dlib-models-raw/raw/master/"
    "dlib_face_recognition_resnet_model_v1.dat.bz2"
)


def _download_with_fallback(urls, target, log):
    """依次尝试 urls 列表, 第一个成功就停.

    W15+: 国内组员用 GitHub raw 经常被墙/超时, fallback 到 gitee 镜像.
    失败时保留最后一次的 .bz2 给下次重试 (跟之前一样, 不会下到一半删了重来).
    """
    last_err = None
    for i, url in enumerate(urls):
        try:
            log.info("Downloading %s (mirror %d/%d) -> %s", url, i + 1, len(urls), target.name)
            with urllib.request.urlopen(url, timeout=60) as resp:
                bz2_path = target.with_suffix(target.suffix + ".bz2")
                with open(bz2_path, "wb") as f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            return  # 成功
        except Exception as e:
            last_err = e
            log.warning("镜像 %s 失败 (%s), 试下一个", url, e)
    # 全部失败
    raise RuntimeError(
        f"所有镜像下载失败 (试了 {len(urls)} 个): {last_err}\n"
        f"请检查网络; 国内组员可挂代理后重试, 或手动下载 {target.name}.bz2 "
        f"放到 {target.parent}/ 下重跑"
    )


def _download_and_decompress(url: str, target: Path):
    """下载 .bz2 文件并解压到 target

    W9 修复:
    - 加 timeout (默认 60s), 避免 GitHub 慢响应时 urlretrieve 永久阻塞
    - 改用 logging 而非 print, 跟项目其它代码一致
    - 解压失败保留 bz2 文件, 避免下次重下 100MB

    W15+ 修复:
    - 改成调 _download_with_fallback(URL 列表), 失败时自动试下一个镜像
    - 兼容外部调用 (ensure_models 仍传单个 URL 即可, 我们在内部补镜像)
    """
    import logging
    log = logging.getLogger(__name__)

    target.parent.mkdir(parents=True, exist_ok=True)
    bz2_path = target.with_suffix(target.suffix + ".bz2")
    if target.exists():
        return

    # W15+: 拼 fallback URL 列表 (原始 URL 优先, gitee 镜像兜底)
    if url == SHAPE_PREDICTOR_URL:
        urls = [SHAPE_PREDICTOR_URL, SHAPE_PREDICTOR_URL_GITEE]
    elif url == FACE_REC_MODEL_URL:
        urls = [FACE_REC_MODEL_URL, FACE_REC_MODEL_URL_GITEE]
    else:
        urls = [url]

    try:
        _download_with_fallback(urls, target, log)
    except Exception as e:
        # W9: 保留 bz2 文件, 避免下次重下 100MB
        log.error("下载失败 (bz2 已保留供重试): %s", e)
        raise
    log.info("Decompressing %s ...", target.name)
    try:
        with bz2.open(bz2_path, "rb") as src, open(target, "wb") as dst:
            dst.write(src.read())
    except Exception as e:
        log.error("解压失败 (bz2 已保留供重试): %s", e)
        raise
    bz2_path.unlink()
    log.info("Done: %s (%.1f MB)", target, target.stat().st_size / 1024 / 1024)


def ensure_models() -> Tuple[Path, Path]:
    """确保两个模型文件存在，不存在就下载"""
    sp_path = MODELS_DIR / "shape_predictor_68_face_landmarks.dat"
    fr_path = MODELS_DIR / "dlib_face_recognition_resnet_model_v1.dat"
    _download_and_decompress(SHAPE_PREDICTOR_URL, sp_path)
    _download_and_decompress(FACE_REC_MODEL_URL, fr_path)
    return sp_path, fr_path


# 全局懒加载（避免重复读盘）
_detector: Optional[dlib.fhog_object_detector] = None
_sp: Optional[dlib.shape_predictor] = None
_facerec: Optional[dlib.face_recognition_model_v1] = None


def _load_models():
    global _detector, _sp, _facerec
    if _detector is None:
        _detector = dlib.get_frontal_face_detector()
    if _sp is None or _facerec is None:
        sp_path, fr_path = ensure_models()
        _sp = dlib.shape_predictor(str(sp_path))
        _facerec = dlib.face_recognition_model_v1(str(fr_path))


# =====================================================
# 1. face_locations(image) -> [(top, right, bottom, left), ...]
# 模仿 face_recognition 接口，返回 (top, right, bottom, left) 元组列表
# =====================================================
def face_locations(image_bgr: np.ndarray, model: str = "hog") -> List[Tuple[int, int, int, int]]:
    """
    检测人脸位置。
    model="hog": CPU 快（默认）
    model="cnn": GPU/CPU 准但慢（本机无 GPU 时不推荐）
    """
    _load_models()
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    # dlib detector 接收 RGB 图像
    dets = _detector(rgb, 1)  # 1 = 上采样 1 次，提升小人脸检出率
    return [(d.top(), d.right(), d.bottom(), d.left()) for d in dets]


# =====================================================
# 2. face_encodings(image, known_face_locations=None) -> [np.ndarray(128), ...]
# 提取 128 维特征向量
# =====================================================
def face_encodings(image_bgr: np.ndarray,
                   known_face_locations: Optional[List[Tuple[int, int, int, int]]] = None) -> List[np.ndarray]:
    """
    提取 128 维人脸特征向量。
    如果不传 known_face_locations，会先调用 face_locations 检测。
    """
    _load_models()
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    if known_face_locations is None:
        known_face_locations = face_locations(image_bgr, model="hog")

    encodings = []
    for (top, right, bottom, left) in known_face_locations:
        # 转 dlib.rectangle
        rect = dlib.rectangle(left, top, right, bottom)
        shape = _sp(rgb, rect)               # 68 关键点
        # 统一用 float32：dlib 内部 compute_face_descriptor 返回的就是 float32，
        # face.py:16 列注释也写 "128维float32"，避免 W3 序列化/比对时量纲不一致
        encoding = np.array(_facerec.compute_face_descriptor(rgb, shape), dtype=np.float32)
        encodings.append(encoding)
    return encodings


# =====================================================
# 3. face_distance(face_encodings, face_to_compare) -> np.ndarray
# 计算欧氏距离，越小越像
# =====================================================
def face_distance(face_encodings: List[np.ndarray], face_to_compare: np.ndarray) -> np.ndarray:
    """
    返回每个已知编码到 face_to_compare 的欧氏距离数组。
    """
    if len(face_encodings) == 0:
        return np.array([])
    known = np.array(face_encodings)
    diff = known - face_to_compare
    return np.linalg.norm(diff, axis=1)


# =====================================================
# 4. compare_faces(known_encodings, encoding, tolerance=0.6) -> [bool, ...]
# 简单阈值判定
# =====================================================
def compare_faces(known_encodings: List[np.ndarray], face_encoding: np.ndarray,
                  tolerance: float = 0.45) -> List[bool]:
    distances = face_distance(known_encodings, face_encoding)
    return (distances <= tolerance).tolist()


# =====================================================
# 自检
# =====================================================
if __name__ == "__main__":
    print("Loading models (first run will download ~120MB)...")
    sp, fr = ensure_models()
    print(f"shape_predictor: {sp}")
    print(f"face_rec_model:  {fr}")
    print("Models ready.")
