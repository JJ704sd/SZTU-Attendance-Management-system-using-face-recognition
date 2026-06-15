# 签到方式说明

W13+ 引入两种新的签到方式：**数字码签到** 和 **二维码签到**，与原有的**刷脸签到**并存。
设计参考对分易"教师手动触发码 → 学生提交"模式，配套教师端码显示弹窗与学生端三方式切换。

## 1. 整体流程

```
┌──────────────────────────────────────────────────────────────────┐
│  教师端（TeacherWindow）                                          │
│  ┌──────────────────────────────────────────────────┐            │
│  │ 「发起考勤」Tab                                   │            │
│  │   当前 open 任务: #82  BME201 数据库原理           │            │
│  │   [🎲 数字签到]  [📱 二维码签到]  ← 点按            │            │
│  └──────────────────────────────────────────────────┘            │
│              ↓ 弹 SigninCodeDialog(60s 倒计时)                  │
│  ┌──────────────────────────────────────────────────┐            │
│  │  ★  0 4 2 7  ★             倒计时: 00:42           │            │
│  │                                                🔄  │            │
│  │  签到码仅对当前 open 任务生效                      │            │
│  └──────────────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────────┘
                              ↓ 学生看码 / 扫码
┌──────────────────────────────────────────────────────────────────┐
│  学生端（StudentWindow）                                          │
│  ┌──────────────────────────────────────────────────┐            │
│  │ 「签到」Tab 2 (QTabWidget 子 Tab)                  │            │
│  │  [🤳 刷脸] [🔢 数字码] [📷 二维码]                  │            │
│  │ ─────────────────────────────────────             │            │
│  │  🔢 数字码签到                                    │            │
│  │  请输入 4 位数字签到码                              │            │
│  │  ┌──────┐                                         │            │
│  │  │ 0427 │   [签到]                                │            │
│  │  └──────┘                                         │            │
│  │  ✅ 出勤                                          │            │
│  └──────────────────────────────────────────────────┘            │
│              ↓                                                     │
│  AttendanceService.sign_in_by_digit(task_id, user_id, "0427")    │
│              ↓                                                     │
│  attendance_record 表 INSERT (signin_method='digit', ...)        │
└──────────────────────────────────────────────────────────────────┘
```

## 2. 三种签到方式对比

| 维度 | 刷脸 | 数字码 | 二维码 |
|---|---|---|---|
| 教师端动作 | 无（学生自主刷） | 手动点「🎲 数字签到」生成 4 位码 | 手动点「📱 二维码签到」生成 token |
| 学生端动作 | 摄像头对准脸部自动识别 | 在输入框敲 4 位数字 + 点「签到」 | 摄像头对准教师屏/投影自动扫码 |
| 校验材料 | 128 维人脸编码（float32） | 4 位数字 + task_id | 22 字符 base64 token + task_id |
| TTL | 任务整个 open 期间 | **60 秒**（教师可手刷） | **60 秒**（教师可手刷） |
| 失败常见原因 | 摄像头没开 / 脸没对准 | 码过期 / 教师刷新过 / 学生输错 | 同上 / 摄像头对不准 |
| 适合场景 | 平时上课 | 临时忘带工牌 / 摄像头故障 | 大教室后排学生 / 投影展示 |
| 写库 signin_method | `'face'` | `'digit'` | `'qr'` |
| 写库 match_score | 实际欧氏距离 | NULL | NULL |

## 3. 安全考虑

### 码 TTL
- 默认 60 秒（`DEFAULT_CODE_TTL_SECONDS`）
- 最长 600 秒（`MAX_CODE_TTL_SECONDS`），避免教师忘了刷新被人截图滥用
- 教师可随时点「🔄 刷新码」**手动覆盖旧码**

### 覆盖式失效
- 教师「生成新码」时,**同任务同类型的所有未过期码 is_active=0**
- 学生拿到截图 30 秒后用,会发现码已被新码覆盖

### UNIQUE KEY 兜底
- `attendance_record` 表有 `UNIQUE KEY (task_id, student_id)`
- 即使极端 race（同学生两次签到），数据库拒绝第二条入库
- `_create_record` 写记录前先查 existed,提前返 None 避免 INUSE 报错

### 跨任务隔离
- 码 `task_id` 必须匹配,扫到 A 任务的码去签 B 任务 → 返 None
- 教师端「数字签到」按钮:只对 `status='open'` 任务生效

## 4. 数据库表

新增 `task_signin_code` 表（W13）：

```sql
CREATE TABLE task_signin_code (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    task_id     INT NOT NULL,
    code_type   ENUM('digit','qr') NOT NULL,
    code_value  VARCHAR(64) NOT NULL,           -- digit: 4位数字补0; qr: 22字符 base64
    expires_at  DATETIME NOT NULL,
    is_active   TINYINT(1) DEFAULT 1,            -- 1=有效, 0=被新码覆盖或手动失效
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES attendance_task(id) ON DELETE CASCADE,
    INDEX idx_task_type_active (task_id, code_type, is_active),
    INDEX idx_expiry (expires_at)
);
```

`attendance_record` 表新增 `signin_method` 列（迁移见 `db/migration_w13.sql`）：

```sql
ALTER TABLE attendance_record
    ADD COLUMN signin_method ENUM('face','digit','qr') DEFAULT 'face';
```

## 5. 后端 API（service 层）

```python
from src.services.attendance_service import AttendanceService
svc = AttendanceService()

# 教师生成码
result = svc.generate_signin_code(task_id=82, code_type='digit', ttl_seconds=60)
# → {"code": "0427", "code_type": "digit", "expires_at": datetime(...)}

# 学生签到
record = svc.sign_in_by_digit(task_id=82, user_id=123, code_value="0427")
# → AttendanceRecord(id=..., signin_method='digit', status='present'/'late', ...)
# 失败返 None
```

**公共核** `_create_record(task_id, user_id, signin_method, match_score=None)`：
- 三种签到方式最终都走这条路径
- 业务规则集中维护：task open 校验 / user 是 student 校验 / UNIQUE 拦截 / 迟到判定
- 数字码/二维码走 `_create_record_in_session`(同 session 原子性)，刷脸走 `_create_record`(独立 session)

## 6. UI 关键文件

| 文件 | 角色 | 关键逻辑 |
|---|---|---|
| `src/services/attendance_service.py` | 后端 | 抽公共核 + 三种签到方法 + 教师码生成 |
| `src/dao/task_signin_code_dao.py` | 数据访问 | insert / find_active / deactivate |
| `src/models/task_signin_code.py` | ORM | 13 张表新增 1 |
| `src/ui/widgets/signin_code_dialog.py` | 教师端弹窗 | QDialog + QTimer 倒计时 + qrcode 渲染 |
| `src/ui/widgets/digit_signin_widget.py` | 学生端数字码 | QLineEdit (QIntValidator) + 提交按钮 |
| `src/ui/widgets/qr_scan_widget.py` | 学生端二维码 | 复用 CameraWidget + cv2.QRCodeDetector |

## 7. 测试

| 测试文件 | 项数 | 覆盖 |
|---|---|---|
| `tests/test_task_signin_code_dao.py` | 6 | DAO CRUD + 失效 + 边界 |
| `tests/test_attendance_service.py`（扩） | 21 | 三种签到 + 公共核 + 边界 + W2 刷脸回归 |
| `tests/test_signin_code_dialog.py` | 3 | 教师端弹窗构造 |
| `tests/test_digit_signin_widget.py` | 2 | 数字码 widget 构造 |
| `tests/test_qr_scan_widget.py` | 2 | 二维码 widget 构造 |
| `scripts/smoke_signin_methods.py` | 端到端 | 教师 generate → 学生 sign_in 完整流程 |

测试套件跑法：
```powershell
D:\Attendance-Management-system-using-face-recognition\.venv\Scripts\pytest.exe tests/ -q --ignore=tests/test_camera_widget.py --ignore=tests/test_face_service.py --ignore=tests/test_face_helper.py
# → 85 passed, 18 skipped in ~30s
```
（camera/face 测试在 headless 环境会挂，业务无关，已用 `--ignore` 跳过）

## 8. 教师/学生操作手册

### 教师发码
1. 在「发起考勤」Tab 创建一个 open 任务（任务 #82 之类）
2. 点「🎲 数字签到」→ 弹窗出现 4 位大字 + 60s 倒计时
3. 把码读给学生 / 写黑板
4. 码快过期时点「🔄 刷新码」出新码（学生那边旧码立刻失效）
5. 关闭弹窗 = 本轮结束

### 学生签到
1. 在「签到」Tab 选对应任务下拉
2. 选「🔢 数字码」子 Tab → 敲教师给的 4 位数字 → 点「签到」
3. 看到「✅ 出勤」即签到完成
4. 三种签到方式**任选其一**，先到先签，签到后其他方式自动置灰

### 出问题怎么办
- 「码无效或已过期」→ 找教师点 🔄 刷新码，重输
- 「签到码格式错」→ 必须是 4 位数字（不是 4 个任意字符）
- 签到成功后看不到记录 → 切到「我的考勤」Tab 看
