# 架构说明

> W3-W8 8 周迭代后最终架构, 含 6 个 service / 10 个 dao / 4 角色 UI

## 1. 分层架构

```
┌──────────────────────────────────────────────────────────────┐
│ 1. 表现层 (Presentation) — PyQt5                            │
│    login / register / student / teacher / admin              │
│    + widgets/ (8 个自定义对话框)                             │
├──────────────────────────────────────────────────────────────┤
│ 2. 业务逻辑层 (Service) — 6 个 service                       │
│    auth_service / attendance_service / face_service /        │
│    lab_access_service / leave_service (W6) / report_service  │
├──────────────────────────────────────────────────────────────┤
│ 3. 数据访问层 (DAO) — SQLAlchemy 2.0 ORM, 10 个 dao         │
│    base / user / login_attempt / face / course / classroom /  │
│    course_enrollment / attendance / leave_request /          │
│    lab / lab_training / lab_access_log                       │
├──────────────────────────────────────────────────────────────┤
│ 4. 数据持久层 (Persistence) — MySQL 8.0                     │
│    12 张表 + dlib 二进制模型权重 (本地文件系统)               │
└──────────────────────────────────────────────────────────────┘
```

### 1.1 依赖方向

**严格自顶向下, 禁止反向依赖**:
- `ui/` → `services/` / `models/` (model 仅作类型引用)
- `services/` → `dao/` / `models/`
- `dao/` → `models/` / `db.py`
- `models/` → 不 import 任何业务模块
- `utils/` → 不依赖项目内任何业务模块, 可被任意层调用

### 1.2 为什么这样分

| 收益 | 说明 |
|---|---|
| 可测试 | service / dao 可独立 mock, UI 可不启动做集成测试 |
| 可替换 | UI 可换成 Web (FastAPI+Vue), service / dao 不用动 |
| 可读 | 文件小, 单一职责, 新人 1 天上手 |
| 可演进 | 新增场景 (实验室准入) 只新增 service + ui 标签 |

## 2. 模块依赖图

```
login_window ── register_window
              ├─ auth_service ── UserDao ── User
              │                  ├─ LoginAttemptDao ── LoginAttempt (W4)
              │                  └─ face_encoding (via FaceService)
              ├─ student_window ── face_service (采集/识别) ── FaceEncodingDao
              │                   ├─ attendance_service (sign_in / close_task)
              │                   ├─ leave_service (W6 申请) ── LeaveRequestDao
              │                   └─ course_enrollment
              ├─ teacher_window ── attendance_service (create_task)
              │                   ├─ leave_service (review)
              │                   └─ report_service (W4 报表)
              └─ admin_window ── 4 Tab:
                  ├─ lab_admin_tab     ── LabDao ── Laboratory
                  ├─ training_admin_tab── LabTrainingDao ── LabTraining
                  ├─ access_log_tab    ── LabAccessLogDao ── LabAccessLog
                  └─ report_admin_tab  ── ReportService + utils/charts
```

## 3. Service 职责 (6 个)

| service | 职责 | 阶段 |
|---|---|---|
| `auth_service` | 注册/登录/改密/防暴力锁定 (LOGIN_MAX_ATTEMPTS) | W2-W4 |
| `attendance_service` | 考勤任务/签到（刷脸+数字码+二维码）/缺勤补齐/请假 | W2-W6 + W13+ |
| `face_service` | 采集 (collect_for_user) / 识别 (recognize) / _FaceCache | W3 |
| `lab_access_service` | 7 分支准入检查 (admin 自由/学生培训) | W4 |
| `report_service` | 出勤率/趋势/实验室使用率/缺勤预警 4 方法 | W4 |
| `leave_service` | 请假申请/审批/列表 | W6 |

## 4. DAO 列表 (10 个)

| dao | model | 关键方法 |
|---|---|---|
| `base` | (Generic) | get/get_all/add/delete |
| `user_dao` | User | find_by_username / find_by_student_id / find_by_role |
| `login_attempt_dao` | LoginAttempt | record_attempt / count_recent_failures |
| `face_dao` | FaceEncoding | find_by_user / delete_by_user / set_primary |
| `course_dao` | Course | find_by_code / find_by_teacher / find_all |
| `classroom_dao` | Classroom | (基础 CRUD) |
| `course_enrollment_dao` | CourseEnrollment | find_by_course / find_by_student |
| `attendance_dao` | AttendanceTask/Record | find_open_tasks / find_by_teacher / find_open_tasks_for_teacher (W6) |
| `leave_request_dao` | LeaveRequest (W6) | find_pending_by_task / find_by_student |
| `lab_dao` | Laboratory | find_by_id / find_all |
| `lab_training_dao` | LabTraining | find_valid_by_student_lab / find_by_student |
| `lab_access_log_dao` | LabAccessLog | log_attempt / find_by_lab (W7 加 id DESC tie-break) |
| `task_signin_code_dao` | TaskSigninCode (W13+) | insert_new / find_active_by_value / deactivate_active_for_task_type |

## 5. utils (4 个)

| 模块 | 用途 |
|---|---|
| `paths` | APP_ROOT 单例 (W5 PyInstaller 兼容, dev 走项目根/打包后走 exe 同级) |
| `face_helper` | dlib 4 核心函数 (face_locations / encodings / distance / compare_faces) |
| `crypto` | bcrypt 12 rounds 密码哈希 |
| `charts` | matplotlib 4 类图表 (出勤率/趋势/热力/缺勤表格) |

## 6. 测试覆盖 (W8 最终)

| 层 | 数量 | 备注 |
|---|---|---|
| `utils/` | 纯函数, pytest 直跑 | face_helper 等 |
| `services/` | 需 MySQL, pytest 用独立 username 隔离 | 82 项全过 |
| `dao/` | 复用 service 测试覆盖 | 间接覆盖 |
| `ui/` | QTest 模拟键入+按钮 (W6), offscreen 模式 | 5 步全过 |
| `e2e/` | 4 个 smoke 脚本 (W5/W6) | 启动→注册→登录→签到全跑通 |
| **PyInstaller 打包** | dist/attendance-system/ 双击 exe | W5 smoke_e2e 全过 |

## 7. 关键设计决策

| 决策 | 原因 |
|---|---|
| dlib-bin 20.0.1 (cp311+ wheel) | 避开 Windows + Python 3.13 cmake 编译坑 |
| face encoding dtype = float32 | 避免序列化/比对时量纲不一致 (W3 决定) |
| PyInstaller onedir (380 MB) | 真一键双击, 不依赖系统 Python |
| bcrypt 12 rounds | 密码哈希, 不明文 |
| session_scope 上下文管理 | 自动 commit/rollback/close |
| QMessageBox.warning 兜底 | UI 层异常不静默失败 |
| closeEvent 释放资源 (W8) | 避免点 X 关窗后摄像头/timer 泄漏 |
| LabAccessLog.id DESC tie-break (W7) | MySQL DATETIME 同秒插入时排序稳定 |
| autouse fixture 清 smk_ student (W7) | close_task fallback 测试间污染修复 |
