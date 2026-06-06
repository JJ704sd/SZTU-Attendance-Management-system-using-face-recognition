# W4 实施计划：实验室管理 + 报表 + 安全加固

**编写时间**: 2026-06-06 12:10
**截止**: 6-14（team timeline 给的 7 天）
**估时**: 5-6 天实际
**风格**: 跟 W3 同款 writing-plans，每个 phase 独立可验收

## 范围（用户选 C 完整版）

- **数据库**: 新增 2 张表 `course_enrollment` + `login_attempt`
- **DAO**: 5 个新 DAO
- **Service**: 2 个新 service + 2 个老 service 改造
- **Utils**: 新 `utils/charts.py`（matplotlib 工具）
- **UI**: admin_window 4 Tab 全接入 + teacher_window Tab 3 接入
- **测试**: 29/29 老测试零回归 + 新单测

## 现状摸底（06-06 12:08）

| 层 | 已有 | 待加 |
|---|---|---|
| models | attendance, course, face, **lab**, user | course_enrollment, login_attempt |
| schema.sql | 10 张表（user/face_encoding/course/classroom/**laboratory**/attendance_task/attendance_record/leave_request/**lab_training**/**lab_access_log**） | course_enrollment, login_attempt |
| DAO | attendance, base, classroom, course, face, user | CourseEnrollment, LoginAttempt, Lab, LabTraining, LabAccessLog |
| service | attendance, auth, face | lab_access, report |
| utils | crypto, face_helper | charts |
| UI | login, register, student ✅, teacher ✅, admin (placeholder) | admin 4 Tab + teacher Tab 3 |

**关键发现**：
- `laboratory` / `lab_training` / `lab_access_log` 3 张表 schema 已建 ✅
- `lab.py` model 已建 ✅
- **缺 DAO**（schema 在但 ORM DAO 没人写过）
- admin_window 是 4 placeholder Tab（line 37-40）

## Phase 1: DB schema（**最小可验收**）—— 0.5 天

- [ ] `db/schema.sql` 末尾加 `course_enrollment` + `login_attempt` 两张表的 DDL
- [ ] 新建 `src/models/course_enrollment.py`（CourseEnrollment model）
- [ ] 新建 `src/models/login_attempt.py`（LoginAttempt model）
- [ ] 修 `src/models/__init__.py`（让 Base.metadata 能发现新表）
- [ ] 跑 `python -m src.db`（= init_db）→ 11 张表都建出来
- [ ] **验收**: MySQL 里查 `SHOW TABLES` 看到 12 张表（10 旧 + 2 新）

**注意**：`db/schema.sql` 里有实验室相关的 3 张表，但 DDL 是早期写的，**没有用 `init_db` 走 SQLAlchemy**（init_db 用 Base.metadata.create_all）。这意味着实验室 3 张表**当前不存在**（在 MySQL 里）！Phase 1 顺便修这个——`db.init_db` import 现有 5 个 model 时要能建出全部表。

## Phase 2: DAO 层 —— 0.5 天

- [ ] 新建 `src/dao/course_enrollment_dao.py`
- [ ] 新建 `src/dao/login_attempt_dao.py`
- [ ] 新建 `src/dao/lab_dao.py`（用 models/lab.py 已有 Laboratory model）
- [ ] 新建 `src/dao/lab_training_dao.py`
- [ ] 新建 `src/dao/lab_access_log_dao.py`
- [ ] 测试: `tests/test_*.py` 各加 1-2 个基础 CRUD 单测

## Phase 3: Service 层（最大块）—— 1.5-2 天

### 3a. `auth_service.login` 加 LOGIN_MAX_ATTEMPTS 锁定（0.5 天）
- [ ] `LoginAttemptDao.record_attempt(username, success)`
- [ ] `auth_service.login` 失败时记 `success=False`
- [ ] 登录前查最近 5 次（`Config.LOGIN_MAX_ATTEMPTS`）失败次数 → 超阈值抛 `AuthError("账号已锁定，请 N 分钟后重试")`
- [ ] 测试: 5 次失败后第 6 次抛锁定异常

### 3b. 修 `close_task_and_mark_absent` 走 `course_enrollment`（0.3 天）
- [ ] 不再用 `role='student'` 全部学生
- [ ] 改用 `course_enrollment` 查该课程的学生
- [ ] 课程无人选则降级到 `role='student'`（保持原行为，防御性）

### 3c. 新 `lab_access_service.py`（0.5 天）
- [ ] `check_access(user_id, lab_id) -> AccessResult(granted, reason)`
- [ ] 逻辑：role=student → 查 `lab_training` 该 user+lab 记录 → 培训不存在/过期/分数不够/类型不匹配 → 拒绝
- [ ] 每次结果写 `lab_access_log`
- [ ] 测试: 3 种通过 + 4 种拒绝分支

### 3d. 新 `report_service.py`（0.5 天）
- [ ] `attendance_rate_per_student(course_id) -> list[(student_id, rate)]`
- [ ] `attendance_trend_per_course(course_id, days) -> list[(date, rate)]`
- [ ] `lab_usage_rate(lab_id, days) -> list[(date, hour, count)]`
- [ ] `absent_warning_list(threshold=0.8) -> list[(student_id, rate, course_name)]`
- [ ] 测试: 4 个方法各 1 个用例（mock 数据）

## Phase 4: utils/charts.py（matplotlib 工具）—— 0.5-1 天

- [ ] `chart_attendance_rate_bar(data, ax=None) -> Figure`（学生出勤率柱状图）
- [ ] `chart_attendance_trend_line(data, ax=None) -> Figure`（班级出勤率趋势折线图）
- [ ] `chart_lab_usage_heatmap(data, ax=None) -> Figure`（实验室使用率热力图）
- [ ] `chart_absent_warning_table(data, ax=None) -> Figure`（缺勤预警表格，用 ax.table）
- [ ] 风格: 全局 QSS 深藏青色板，保持项目风格统一
- [ ] 关键: 中文 label 不乱码（设 `font.family = 'Microsoft YaHei UI'`）
- [ ] 测试: 4 个函数各 1 个 smoke（用真 random 数据生成 Figure 不挂）

## Phase 5: admin_window 4 Tab 接入 —— 1.5 天

- [ ] **Tab 1 实验室管理**: QTableWidget 列表 + 增删改查表单（CRUD）
- [ ] **Tab 2 安全培训录入**: QTableWidget 列表 + 增删改查表单
- [ ] **Tab 3 准入日志**: QTableWidget 只读，显示 lab_access_log
- [ ] **Tab 4 使用率报表**: matplotlib FigureCanvas 嵌入 + 4 类图表切换（QComboBox 选类型）
- [ ] 复用全局 QSS（`apply_global_style`）+ welcome_suffix

## Phase 6: teacher_window Tab 3 报表 —— 0.5 天

- [ ] 替换"统计报表"占位文案
- [ ] matplotlib FigureCanvas 嵌入
- [ ] 2 个图表切换：
  - 班级出勤率趋势（折线图，按周聚合）
  - 出勤率排行（柱状图，Top 10 班级）
- [ ] 选课程下拉（默认"全部课程"）

## Phase 7: 端到端 + 文档 + commit —— 0.5 天

- [ ] 新建 `scripts/smoke_lab.py`：
  - 注册 demo_admin（如已存在复用）
  - 创建 1 个实验室
  - 创建 1 条培训记录
  - 调 `lab_access_service.check_access` 验证通过分支
  - 改培训记录 expiry_date=昨天 → 验证拒绝分支
  - 跑通即 exit 0
- [ ] 补 `docs/MANUAL_E2E.md`：加"W4 实验室管理员验收"5 步
- [ ] 跑全量测试 → 29 + 新测试 全过
- [ ] commit + push（按"按阶段验收"工作流，每个 phase 单独 commit；最后 push）

---

## 风险 + 备选

| 风险 | 触发 | 应对 |
|---|---|---|
| matplotlib 中文乱码 | 任何 chart 跑 | 显式 `rcParams['font.sans-serif'] = ['Microsoft YaHei UI']` |
| 老 schema 用 `init_db` 走 SQLAlchemy 不全 | 实验室 3 张表当前 DB 里**可能没有** | Phase 1 跑完 init_db 后**先查 SHOW TABLES**确认 12 张全建 |
| course_enrollment 旧数据缺 | 现有 teacher01 / demo_student 选课关系空 | 降级到 "全部 student" 逻辑（已写在 3b 的防御性分支） |
| `LOGIN_MAX_ATTEMPTS` 时间窗口 | 是"最近 5 次"还是"5 分钟内"？ | 默认"最近 N 次"，注释说"可改时间窗口" |
| admin 端 GUI 复杂 | 4 Tab 都要 CRUD 表格 | 复用 TeacherWindow 的表格模式（已有） |
| matplotlib 嵌入 PyQt5 | offscreen 渲染 + 真机显示 | 用 `FigureCanvasQTAgg`（matplotlib 内置 Qt backend） |

## 文件清单

| 路径 | 状态 | 估时 |
|---|---|---|
| `db/schema.sql` | 加 2 表 | 0.1d |
| `src/models/course_enrollment.py` | 新建 | 0.1d |
| `src/models/login_attempt.py` | 新建 | 0.1d |
| `src/dao/course_enrollment_dao.py` | 新建 | 0.1d |
| `src/dao/login_attempt_dao.py` | 新建 | 0.1d |
| `src/dao/lab_dao.py` | 新建 | 0.1d |
| `src/dao/lab_training_dao.py` | 新建 | 0.1d |
| `src/dao/lab_access_log_dao.py` | 新建 | 0.1d |
| `src/services/lab_access_service.py` | 新建 | 0.5d |
| `src/services/report_service.py` | 新建 | 0.5d |
| `src/services/auth_service.py` | 改 login + LoginAttempt | 0.5d |
| `src/services/attendance_service.py` | 改 close_task 走 enrollment | 0.3d |
| `src/utils/charts.py` | 新建（4 类图） | 0.5-1d |
| `src/ui/admin_window.py` | 重写 4 Tab | 1.5d |
| `src/ui/teacher_window.py` | 改 Tab 3 报表 | 0.5d |
| `scripts/smoke_lab.py` | 新建 | 0.3d |
| `docs/MANUAL_E2E.md` | 补 W4 部分 | 0.2d |
| `tests/test_*.py` | 新增 DAO/service/charts 单测 | 0.5d |
| **总计** | | **5-6d 实际** |

## 推进节奏（按用户"按阶段验收"工作流）

每个 phase 做完 → 跑测试 → 起 GUI 烟雾测试 → 报告 → 等用户点头 → 下个 phase

不批量 commit：每个 phase 单独 commit（W3 也是这样做的）。

最终 W4 结束统一 push 1 次（除非用户中途要求推）。
