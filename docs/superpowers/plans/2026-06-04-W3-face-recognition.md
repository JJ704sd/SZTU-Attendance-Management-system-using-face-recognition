# W3：人脸采集 + 训练 + 识别（核心 1） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学生端可刷脸注册、可刷脸签到，端到端跑通；为 W4 实验室准入的"刷脸核验"提供可调用的识别接口。

**Architecture:** 在已就绪的 4 层架构（ui / services / dao / models）上加一条 face 主线：
- **DAO 层**：补 `FaceEncodingDao`
- **Service 层**：新建 `FaceService`，含 `collect_for_user` / `recognize` / 内存编码缓存
- **UI 层**：新建 `CameraWidget`（cv2 → QPixmap）、`FaceCollectDialog`；**重写** `StudentWindow`（从 68 行占位 → 3 个真 tab）
- **Model 层**：`FaceEncoding` 加 `to_dict()` debug 辅助

**Tech Stack:** OpenCV 4.13（`cv2.VideoCapture` + `cv2.imencode`）/ dlib-bin 20.0.1（`face_helper` 已封装）/ numpy 2.3 / PyQt5 `QTimer` / SQLAlchemy 2.0 / pytest

**截止：** 2026-06-07（W3 末）
**估时：** 4.5 天（5 人组可拆 1 人主做 + 1 人辅助；单人 4.5 天）

---

## 现状盘点

| 项 | 状态 | 备注 |
|---|---|---|
| `src/utils/face_helper.py` | ✅ | 4 个核心 API，7/7 单测 |
| `src/models/face.py` `FaceEncoding` | ✅ | 在；缺 `to_dict()` |
| `db/schema.sql` `face_encoding` 表 | ✅ | utf8mb4，含 `is_primary` 索引 |
| `src/dao/face_dao.py` | ❌ | 待建 |
| `src/services/face_service.py` | ❌ | 待建 |
| 摄像头 PyQt5 封装 | ❌ | 待建 |
| `src/ui/student_window.py` | ❌ | 68 行占位，4 个 tab 全 placeholder |
| `attendance_service.sign_in_by_face()` | ✅ | 在，但还没被 UI 调过 |
| `Config.FACE_MATCH_THRESHOLD` / `FACE_SAMPLE_COUNT` | ✅ | 已在 `.env.example` 和 `config.py` |

---

## 阶段划分

### Phase 1：基础层（0.5 天） ✅ 已完成

- [x] **新建 `src/dao/face_dao.py`**
  - `find_by_user(user_id) -> list[FaceEncoding]`
  - `delete_by_user(user_id) -> int`（返回删除行数）
  - `set_primary(encoding_id, user_id) -> None`（先把同用户其他行的 `is_primary` 置 0，再设本行 1）
- [x] **新建 `src/services/face_service.py`**
  - 模块级常量 `ENCODING_DIM = 128`、`ENCODING_DTYPE = np.float32`（与 `models/face.py` 注释及 `face_helper.face_encodings` 输出一致；CLAUDE.md 技术决策已锁）
  - `encode_to_bytes(arr: np.ndarray) -> bytes`：用 `arr.astype(np.float32).tobytes()`
  - `decode_from_bytes(b: bytes) -> np.ndarray`：反向
  - `save_encoding(user_id, encoding, image_path, is_primary=False) -> int`（用 `encode_to_bytes` 序列化）
  - `load_user_encodings(user_id) -> list[np.ndarray]`（用 `decode_from_bytes` 反序列化）
  - `load_all_user_encodings() -> dict[int, list[np.ndarray]]`（一次拉所有，识别缓存用）
  - `delete_user_encodings(user_id) -> int`
- [ ] **`src/models/face.py` 加 `to_dict()`**：`{"id", "user_id", "image_path", "is_primary", "created_at"}`（Phase 4 一起做，与缓存调试合用）

**验收命令：**
```bash
pytest tests/test_face_service.py::test_encode_decode_roundtrip -v
pytest tests/test_face_service.py::test_save_load_encoding -v
pytest tests/test_face_service.py::test_delete_user_encodings -v
pytest tests/test_face_service.py::test_set_primary -v
```

---

### Phase 2：摄像头封装（1 天） ✅ 已完成

- [x] **新建 `src/ui/widgets/camera_widget.py` `CameraWidget(QWidget)`**
  - 内部持 `cv2.VideoCapture`
  - `QTimer(self)` 设 30 ms 间隔，每 tick 拉一帧 → 转 `QImage`（`cv2.cvtColor(bgr, COLOR_BGR2RGB)` + `QImage.rgbSwapped`）→ 缩放贴 `QLabel`
  - 信号 `frame_ready = pyqtSignal(np.ndarray)`（把 BGR 帧发给上层做检测）
  - 方法 `start(device_id: int = 0) -> bool`（打不开返回 False + 在 widget 上盖红色 "摄像头不可用"）
  - 方法 `stop()`
  - 方法 `capture_one_frame() -> np.ndarray | None`（带 `_lock` 互斥，避免与 timer 抢帧）
  - `closeEvent` 调 `stop()`，`__del__` 兜底 `self._cap.release()`
  - 不在本阶段做**人脸框叠加**（留给 Phase 5 一起做）

**验收命令：**
```bash
# 手动：python -c "from PyQt5.QtWidgets import QApplication; \
# from src.ui.widgets.camera_widget import CameraWidget; \
# import sys; app = QApplication(sys.argv); w = CameraWidget(); w.show(); w.start(); \
# from PyQt5.QtCore import QTimer; QTimer.singleShot(3000, app.quit); app.exec_()"
# 预期：窗口打开 3 秒，看到自己画面，3 秒后无报错退出
```

---

### Phase 3：采集 service（0.5 天） ✅ 已完成

- [x] **在 `src/services/face_service.py` 加：**
  ```python
  def collect_for_user(
      user_id: int,
      camera: "CameraWidget",
      n_samples: int = None,  # None 时回退 Config.FACE_SAMPLE_COUNT
      on_progress: Optional[Callable[[int, int], None]] = None,  # (captured, target)
  ) -> dict:
      """
      从 camera 抓 n_samples 张人脸图，编码后入库。
      返回: {"ok": bool, "captured": int, "saved": int, "error": str|None}
      """
  ```
  - 循环：`frame = camera.capture_one_frame()` → `face_locations` → 0 张则计数 + continue → ≥1 张 → `face_encodings` 算 128 维（也可能返回 []，同样计数）
  - 原图存到 `Config.DATASET_DIR / f"{user_id}" / f"{idx:03d}.jpg"`（`cv2.imwrite`）
  - 调 `save_encoding()` 写 DB
  - 触发 `on_progress(captured, n_samples)`（UI 用这个更新进度条）；回调异常吞掉，不中断采集
  - 中途连续 `NO_FACE_LIMIT=30` 次未拿到可入库样本（**无帧 / 无脸 / 无编码三选一**）→ 返回 `{"ok": False, "error": "采集超时：连续 30 帧未获取到人脸样本"}`
    - **回归保护**：`test_collect_for_user_terminates_when_encodings_empty` 锁住，防止重现"face_encodings 持续返回 [] → 死循环"的历史 bug
  - 异常路径：摄像头断开 → `{"ok": False, "error": "摄像头断开"}`；磁盘写入失败 → `{"ok": False, "error": "磁盘写入失败: ..."}`

- [x] **加单测 `test_collect_for_user_writes_encodings`**：mock `CameraWidget` + patch `face_locations`/`face_encodings`，断言返回值 / DB 行数 / 文件数 / 进度回调次数 / 摄像头调用次数
- [x] **加回归单测 `test_collect_for_user_terminates_when_encodings_empty`**：用 `threading.Thread + join(10s)` 兜底，确认 face_encodings 持续返空时仍能超时退出

**验收命令：**
```bash
pytest tests/test_face_service.py::test_collect_for_user_writes_encodings -v
```

---

### Phase 4：识别 service（0.5 天）

- [ ] **在 `src/services/face_service.py` 加：**
  ```python
  class _FaceCache:
      """进程内单例，启动时全量加载，采集时增量加。"""
      _instance = None
      def __init__(self):
          self._encodings: dict[int, list[np.ndarray]] = {}
      @classmethod
      def get(cls) -> "_FaceCache": ...
      def refresh(self) -> None: ...           # 全量重建
      def add(self, user_id: int, encoding: np.ndarray) -> None: ...  # 增量
      def remove_user(self, user_id: int) -> None: ...
      def all(self) -> dict[int, list[np.ndarray]]: ...

  def recognize(encoding: np.ndarray) -> Optional[Tuple[int, float]]:
      """
      在 _FaceCache 中找最近用户，距离 ≤ Config.FACE_MATCH_THRESHOLD 算命中。
      返回 (user_id, distance) 或 None。
      """
  ```
  - 遍历 `cache.all()`，对每个用户的多个编码取**最近**距离
  - 距离 ≤ 阈值 → 返回
  - 全部 > 阈值 → `None`
  - 缓存空（库没编码）→ `None` + log warning

- [ ] **在 `src/main.py` 启动时**调一次 `face_service._FaceCache.get().refresh()`（避免识别时第一次冷启动慢）

- [ ] **加单测：**
  - `test_recognize_returns_user_id`：cache 注入 `{1: [zeros128]}`，传 `zeros128 + 0.01` → 应返回 `(1, ~0.01)`
  - `test_recognize_returns_none_below_threshold`：cache 注入 `{1: [zeros128]}`，传 `zeros128 + 1.0` → 应返回 `None`
  - `test_recognize_empty_cache`：空 cache → `None`

**验收命令：**
```bash
pytest tests/test_face_service.py::test_recognize_returns_user_id -v
pytest tests/test_face_service.py::test_recognize_returns_none_below_threshold -v
pytest tests/test_face_service.py::test_recognize_empty_cache -v
```

---

### Phase 5：学生端 UI（1.5 天）

- [ ] **新建 `src/ui/widgets/face_collect_dialog.py` `FaceCollectDialog(QDialog)`**
  - 嵌入 `CameraWidget`（或直接用 camera 句柄）
  - 进度条 `QProgressBar`（0 → `Config.FACE_SAMPLE_COUNT`）
  - 标签实时显示"已采集 N 张，请缓慢转头..."
  - 按钮：开始 / 取消
  - 用 `QThread` 或 `QTimer` 异步调 `face_service.collect_for_user()`，避免卡 UI
  - 完成 → 弹"成功采集 N 张编码" → accept
  - 失败 → 弹错误 → reject

- [ ] **重写 `src/ui/student_window.py`**

  - **Tab 1：人脸注册**
    - 顶部说明"需采集 30 张不同角度的人脸"
    - 一个 `CameraWidget` 实时预览（带人脸框：用 `face_locations` + `cv2.rectangle` 画到 QImage 上）
    - 按钮"开始采集" → 弹 `FaceCollectDialog`
    - 完成后显示"已注册 N 张编码"，并提示可去签到

  - **Tab 2：刷脸签到**
    - 下拉 `QComboBox` 列出当前 `status='open'` 的任务（查 `attendance_dao.find_open_tasks()`，**注意**：当前 DAO 没有这个方法，要先加）
    - 嵌入 `CameraWidget` + 同样的人脸框叠加
    - `QTimer` 每 500 ms 抓一帧 → `face_encodings` → `face_service.recognize()`
    - 命中：`attendance_service.sign_in_by_face(task_id, user_id, distance)`
      - 成功 → 弹"签到成功" + 停止识别
      - 失败 / 已签到 → 弹对应提示
    - 标签实时显示"识别中... 上次匹配：user_id=3, 距离=0.32"

  - **Tab 3：我的考勤**
    - `QTableWidget` 查 `attendance_record` 自己的记录，按 `sign_in_time` 倒序
    - 列：日期 / 课程 / 状态 / 匹配距离
    - 状态着色：present 绿、late 黄、absent 红、leave 蓝
    - 需要加 `attendance_dao.find_by_student(student_id)`

  - **Tab 4：我的实验室**（保持占位，标"W4 接入"）

- [ ] **补 DAO 方法：**
  - `attendance_dao.find_open_tasks() -> list[AttendanceTask]`
  - `attendance_dao.find_by_student(student_id) -> list[AttendanceRecord]`

**验收命令：**
```bash
# 手动 E2E（见 Phase 6 的 checklist）
pytest tests/ -v   # 全过
```

---

### Phase 6：联调 + 烟测（0.5 天）

- [ ] **新建 `scripts/smoke_face.py`**
  - 自动注册 `demo_student` 账号（如已存在则复用）
  - 调 `face_service.collect_for_user()` 时注入 mock 摄像头（带人脸的固定 numpy 帧）
  - 调 `face_service.recognize()` 验证能识别回 `demo_student`
  - 跑通即 exit 0

- [ ] **新建 `docs/MANUAL_E2E.md`** —— 5 步手动 E2E 清单：
  1. 注册 student 账号 `demo_student / 123456`
  2. 登录后 Tab 1"人脸注册" → 采 30 张 → 看到"成功"
  3. 切到教师端 `teacher01` 登录 → 发起一个 open 任务（BME201，10 分钟内）
  4. 切回学生端 → Tab 2"刷脸签到" → 选任务 → 看到自己 → 弹"签到成功"
  5. 教师端"历史考勤 → 查看签到详情" → 看到 `demo_student` 状态 present

- [ ] **更新 `docs/WORKFLOWS.md` 的"流程 1：学生人脸注册"**：`face_recognition.*` 引用 → `face_helper.*`（之前漏改了 Phase 3 之后的步骤描述，复查一遍）

**验收命令：**
```bash
python scripts/smoke_face.py
echo $?  # 预期 0
pytest tests/ -v   # 预期全过
```

---

## 文件清单

| 路径 | 状态 | 行数估计 |
|---|---|---|
| `src/dao/face_dao.py` | 新建 | ~60 |
| `src/services/face_service.py` | 新建 | ~200 |
| `src/ui/widgets/camera_widget.py` | 新建 | ~120 |
| `src/ui/widgets/face_collect_dialog.py` | 新建 | ~150 |
| `src/ui/student_window.py` | **重写** | 68 → ~280 |
| `src/dao/attendance_dao.py` | 加 2 个方法 | +30 |
| `src/models/face.py` | 加 `to_dict()` | +10 |
| `src/main.py` | 启动时 refresh cache | +3 |
| `tests/test_face_service.py` | 新建 | ~180 |
| `scripts/smoke_face.py` | 新建 | ~60 |
| `docs/MANUAL_E2E.md` | 新建 | ~50 |
| `docs/WORKFLOWS.md` | 复查 face_helper 引用 | — |

---

## 风险 + 备选

| 风险 | 触发条件 | 触发后应对 |
|---|---|---|
| 本机没摄像头 | 演示机无 USB 摄像头 | Phase 5 加"上传图片签到"作为兜底按钮 |
| 采集光照差 | 教室演示 | 采集时弹"请正对光源"；演示前把 `.env` 的 `FACE_MATCH_THRESHOLD` 调到 `0.5` |
| 30 张采样太长 | 用户不耐烦 | 演示时把 `.env` 的 `FACE_SAMPLE_COUNT` 降到 `10`（5 秒搞定） |
| 摄像头被其他程序占用 | Windows 常见 | `start()` 返回 False 时弹"请关闭其他使用摄像头的程序 + 重试"按钮 |
| dlib 模型下载失败 | 断网 / 防火墙 | `face_helper.ensure_models()` 已有重试，**Phase 2 启动时**确认 `models/*.dat` 存在，缺失就立即报错 |
| `_FaceCache` 内存膨胀 | 用户数 > 1000 | 演示场景不会触发；文档里标"生产环境应换 Redis" |

---

## 提交策略

每个 Phase 收尾一个 commit（与 `CLAUDE.md` 里的 commit 规范一致）：

1. `feat(dao): add FaceEncodingDao + service skeleton (encode/decode helpers)`
2. `feat(ui): add CameraWidget for OpenCV frame display in PyQt5`
3. `feat(face): add collect_for_user service with progress callback + tests`
4. `feat(face): add recognize service with in-memory encoding cache + tests`
5. `feat(ui): rewrite student_window with face register / sign-in / history tabs`
6. `docs: add MANUAL_E2E checklist + smoke_face script + update WORKFLOWS`

---

## Definition of Done（W3 完成的强标准）

- [ ] `pytest tests/ -v` 全部通过（17 原有 + ≥ 7 新增 = ≥ 24 项）
- [ ] `python scripts/smoke_face.py` 退出码 0
- [ ] 手动 E2E checklist 5 步全打勾
- [ ] 教师端"查看签到详情"能看到新签到的学生（端到端联通）
- [ ] 代码 commit 在 main 分支，git log 干净
- [ ] 演示视频录了 1 段：注册 30 张 → 教师发起任务 → 学生刷脸签到 → 教师看到记录

---

## 执行方式（handoff）

- **推荐：subagent-driven**：每个 Phase 派一个 fresh subagent，前一个 Phase 完成后做两阶段 review 再进下一个
- **也可 inline**：在本会话里顺序执行 Phase 1→6，每个 Phase 完成后用 `verification-before-completion` 跑过验收命令再继续
