# 架构说明

## 1. 分层架构

本项目采用经典的**四层架构**，自顶向下为：

```
┌──────────────────────────────────────────────────────┐
│  1. 表现层 (Presentation) — PyQt5                    │
│     login / register / student / teacher / admin     │
│     ＋ widgets/（自定义对话框）                        │
├──────────────────────────────────────────────────────┤
│  2. 业务逻辑层 (Service)                             │
│     auth_service / attendance_service / face_service│
│     / lab_access_service / report_service            │
├──────────────────────────────────────────────────────┤
│  3. 数据访问层 (DAO) — SQLAlchemy ORM                │
│     base / user / course / classroom / attendance    │
├──────────────────────────────────────────────────────┤
│  4. 数据层 (Persistence) — MySQL 8.0                 │
│     10 张表 + dlib 二进制模型权重 (本地文件系统)      │
└──────────────────────────────────────────────────────┘
```

### 1.1 依赖方向

严格**自顶向下**调用，**禁止反向依赖**：

- `ui/` 只 import `services/` 和 `models/`（model 仅作为类型引用）
- `services/` 只 import `dao/` 和 `models/`
- `dao/` 只 import `models/` 和 `db.py`
- `models/` 不 import 任何业务模块
- `utils/` 不依赖项目内任何业务模块，可被任意层调用

### 1.2 为什么这样分

| 收益 | 说明 |
|---|---|
| 可测试 | service / dao 可独立 mock，UI 可不启动做集成测试 |
| 可替换 | UI 可换成 Web（FastAPI+Vue），service / dao 不用动 |
| 可读 | 文件小，单一职责，新人 1 天上手 |
| 可演进 | 新增场景（实验室准入）只新增 service + ui 标签页 |

## 2. 模块依赖图

```
login_window ─┐
register_window
              ├─→ AuthService ──→ UserDao ──→ User (model)
teacher_window ──→ AttendanceService ──→ AttendanceTaskDao ──→ AttendanceTask
                  │                      └─→ AttendanceRecordDao ──→ AttendanceRecord
                  ├─→ CourseDao ──→ Course
                  └─→ ClassroomDao ──→ Classroom
                  (W3 接入) face_service ──→ FaceEncodingDao ──→ FaceEncoding
                  (W3 接入) face_service ──→ face_helper (utils)
```

## 3. 关键数据流：学生刷脸签到

```
[摄像头帧]
    ↓ OpenCV.VideoCapture
[face_service.capture_frame()]
    ↓ dlib detector + shape_predictor
[128 维编码] ─── compare_faces() ──→ [比对结果]
    ↓
[attendance_service.sign_in_by_face(task_id, user_id, distance)]
    ↓
[attendance_dao.insert(record)]
    ↓
[MySQL: attendance_record]
```

## 4. 关键设计决策

| 决策 | 取舍 |
|---|---|
| **dlib-bin 而不是源码编译 dlib** | Python 3.13 上源码编译需要 cmake + VS Build Tools，环境成本高 |
| **不依赖 face_recognition** | face_recognition 1.3.0 的 dlib 子依赖在 cp313 上无 wheel；自写 4 个核心函数成本极低 |
| **bcrypt 而不是 hashlib** | bcrypt 自动加盐、慢哈希（防彩虹表），课程要求"密码不能明文" |
| **PyQt5 而不是 Tkinter** | PyQt5 控件丰富、风格统一（Fusion），教师/管理员端有大量表格和表单 |
| **SQLAlchemy 2.0 ORM 而不是裸 SQL** | 防 SQL 注入 + 跨数据库可移植（演示可一键切 SQLite） |
| **DAO 显式注入而不是全局 session** | 单元测试可注入 mock session，避免污染主库 |
| **所有 service 方法内部用 `session_scope()`** | 自动 commit/rollback/close，调用方零样板 |
| **不把 dlib 模型权重入 git** | 单文件 95 MB，接近 GitHub 100 MB 警告线；运行时按需下载 |
| **不把 .env 入 git** | 含明文数据库密码 |
| **`code/core_samples/` → `reference/patelrahul4884/`** | 区分"本项目代码"和"参考代码"，避免误 import |

## 5. 异常与错误处理约定

| 层级 | 错误处理 |
|---|---|
| `dao/` | 不抛业务错误，只抛 SQLAlchemy 原生异常 |
| `services/` | 校验入参 → 抛 `ValueError`；业务冲突 → 自定义 `AuthError` 等 |
| `ui/` | `try/except` 包裹 service 调用 → `QMessageBox` 提示用户 |

## 6. 配置加载

```python
# src/config.py
class Config:
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    ...
    @classmethod
    def database_url(cls) -> str: ...
```

- 配置统一从 `.env` 读取
- `.env.example` 是模板（**入 git**），`.env` 是真实值（**不入 git**）
- 修改配置后无需改代码，重启服务即可

## 7. 测试策略

| 层级 | 测试方式 | 当前覆盖 |
|---|---|---|
| `utils/` | 纯函数，pytest 直跑 | ✅ face_helper 7 项 |
| `services/` | 真 MySQL，pytest 用独立 username 隔离 | ✅ auth_service 10 项 |
| `dao/` | 复用 service 测试覆盖 | ⚠️ 间接覆盖 |
| `ui/` | 启动后人工目测，offscreen 模式有兼容问题 | ❌ 待 W4 引入 pytest-qt |
| `e2e/` | 启动 → 注册 → 登录 → 签到 | ⚠️ W3 接入 |
