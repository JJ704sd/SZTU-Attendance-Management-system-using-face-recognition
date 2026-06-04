"""
face_service.py — 人脸采集与识别核心服务
依赖：face_recognition, OpenCV, numpy
作者参考：face_recognition 官方文档 https://github.com/ageitgey/face_recognition
说明：参考网络代码比例约 15%（API 用法），业务逻辑为本组自研。
"""

import os
import cv2
import numpy as np
import face_recognition
from datetime import datetime
from typing import Optional, Tuple, List

# 距离阈值，工程经验值：< 0.45 视为同一人
FACE_MATCH_THRESHOLD = 0.45
# 采集张数
SAMPLE_COUNT = 30
# 图像保存根目录
DATASET_DIR = "./dataset/face_images"


class FaceService:
    """人脸采集、注册、识别服务"""

    def __init__(self, db_session):
        self.db = db_session
        # 缓存：user_id -> 128维向量列表（识别时减少 DB 查询）
        self._cache: dict = {}

    # -----------------------------------------------------
    # 1. 采集人脸：摄像头采集 N 张并保存
    # -----------------------------------------------------
    def capture_faces(self, user_id: int, output_dir: Optional[str] = None) -> List[np.ndarray]:
        """
        打开摄像头，采集 SAMPLE_COUNT 张人脸图像。
        返回：所有采集到的 128 维编码列表。
        """
        output_dir = output_dir or os.path.join(DATASET_DIR, str(user_id))
        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(0)  # 0 = 默认摄像头
        if not cap.isOpened():
            raise RuntimeError("无法打开摄像头")

        encodings: List[np.ndarray] = []
        saved = 0
        no_face_frames = 0

        print(f"[INFO] 开始采集，目标 {SAMPLE_COUNT} 张...")
        while saved < SAMPLE_COUNT:
            ret, frame = cap.read()
            if not ret:
                break

            # BGR -> RGB（face_recognition 要求 RGB）
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 检测人脸位置
            locations = face_recognition.face_locations(rgb, model="hog")  # hog 快，cnn 准

            if not locations:
                no_face_frames += 1
                if no_face_frames > 50:
                    print("[WARN] 连续 50 帧未检测到人脸，超时退出")
                    break
                continue

            no_face_frames = 0
            # 取第一张脸编码
            enc = face_recognition.face_encodings(rgb, known_face_locations=[locations[0]])[0]

            # 保存原图（带人脸框）
            top, right, bottom, left = locations[0]
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            image_path = os.path.join(output_dir, f"{saved+1:03d}.jpg")
            cv2.imwrite(image_path, frame)

            encodings.append(enc)
            saved += 1
            print(f"[INFO] 已采集 {saved}/{SAMPLE_COUNT}")

            # 显示预览（带倒计时）
            cv2.putText(frame, f"{saved}/{SAMPLE_COUNT}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Face Registration", frame)
            if cv2.waitKey(100) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
        return encodings

    # -----------------------------------------------------
    # 2. 把采集到的编码写入数据库
    # -----------------------------------------------------
    def save_encodings(self, user_id: int, encodings: List[np.ndarray], image_dir: str) -> int:
        """
        将 N 个 128 维向量写入 face_encoding 表。
        返回：写入条数。
        """
        from models.face import FaceEncoding  # 避免循环导入

        rows = []
        for i, enc in enumerate(encodings):
            rows.append(FaceEncoding(
                user_id=user_id,
                encoding=enc.astype(np.float32).tobytes(),  # numpy 向量序列化为 bytes
                image_path=os.path.join(image_dir, f"{i+1:03d}.jpg"),
                is_primary=(i == 0),  # 第一张为主图
            ))
        self.db.add_all(rows)
        self.db.commit()
        return len(rows)

    # -----------------------------------------------------
    # 3. 实时识别一帧
    # -----------------------------------------------------
    def recognize_frame(self, frame_bgr) -> Tuple[Optional[int], float]:
        """
        输入一帧 BGR 图像，返回 (user_id, distance)。
        距离 < 阈值视为识别成功。
        """
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model="hog")
        if not locations:
            return None, float("inf")

        # 只处理第一张脸
        enc = face_recognition.face_encodings(rgb, known_face_locations=[locations[0]])
        if not enc:
            return None, float("inf")
        enc = enc[0]

        # 从缓存或 DB 加载所有用户编码
        if not self._cache:
            self._load_cache()

        if not self._cache:
            return None, float("inf")

        # 与库中所有人脸对比，取最小距离
        best_user_id = None
        best_distance = float("inf")
        for user_id, known_encs in self._cache.items():
            distances = face_recognition.face_distance(known_encs, enc)
            d = float(np.min(distances))
            if d < best_distance:
                best_distance = d
                best_user_id = user_id

        if best_distance > FACE_MATCH_THRESHOLD:
            return None, best_distance
        return best_user_id, best_distance

    def _load_cache(self):
        """启动时把所有人脸编码加载到内存，提升识别速度"""
        from models.user import User
        from models.face import FaceEncoding

        users = self.db.query(User).filter(User.role == "student").all()
        for u in users:
            encs = []
            for fe in u.face_encodings:
                arr = np.frombuffer(fe.encoding, dtype=np.float32)
                encs.append(arr)
            if encs:
                self._cache[u.id] = encs
        print(f"[INFO] 已加载 {len(self._cache)} 个学生的人脸编码到缓存")

    def refresh_cache(self):
        """注册新学生后调用"""
        self._cache.clear()
        self._load_cache()
