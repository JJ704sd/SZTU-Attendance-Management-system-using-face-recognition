# Smoke 测试指南 (SMOKE_TESTS)

> W6 收口: 列出项目所有 smoke 脚本 + 用法 + 验收点。
> 跑 smoke 是验证完整业务流的快速方式 (不需要 GUI 用户参与)。

## 1. 总览

| 脚本 | 范围 | 估时 | 用法 |
|---|---|---|---|
| `smoke_full_flow.py` | 完整 9 步业务流 + 6.5 请假 + 7. 准入 7 分支 | ~10s | dev / CI |
| `smoke_real_face.py` | dlib 真脸端到端 (摄像头 + 编码 + 匹配 + 签到) | ~5s | 需摄像头对正脸 |
| `smoke_ui_qtest.py` | PyQt5.QtTest 真实 UI 交互 (3 角色登录 + Tab + chart) | ~5s | dev / CI (offscreen) |
| `smoke_e2e.py` | 打包后端到端 (拷 dist + 启 exe + 验 7 关键日志) | ~15s | W5 打包验收 |
| `smoke_face.py` | W3 face 采集/识别烟测 (旧) | ~3s | W3 历史 |

所有 smoke 默认从项目根目录跑：

```powershell
.venv\Scripts\python.exe scripts\smoke_full_flow.py
```

退出码 `0` = PASS, 非零 = FAIL。

---

## 2. smoke_full_flow.py — 完整业务流 (W6)

模拟一个完整学期跑一遍：

1. 启应用 (init_db + FaceCache + dlib 路径)
2. 注册 3 角色 (admin/teacher/3 students)
3. 老师 create_task + 3 student 报名
4. 3 学生 sign_in_by_face (mock distance 0.30) + ghost user 返 None
5. 老师 close_task + 缺勤补齐
6. 老师查 report_service (3 方法)
6.5 W6 Phase 1: 请假流程 (申请 / 批准 / 拒绝 / 任务关闭后补假)
7. 管理员 check_access 7 分支 (7a-7g 全验)
8. 管理员 LabDao CRUD
9. cleanup

**用法**:

```powershell
.venv\Scripts\python.exe scripts\smoke_full_flow.py
```

**验收点** (PASS 输出样例):

```
=== 1. 应用启动 ===
  [OK] init_db: 12 张表 ready
  [OK] FaceCache 预热
  [OK] dlib 模型: sp=...dat fr=...dat
=== 2. 注册 3 角色 ===
  [OK] admin id=...
=== 3. 老师 create_task ===
  [OK] course_id=..., lab_id=...
=== 7. 管理员 check_access 7 分支 ===
  [OK] [7a] admin (非学生) access: granted=True
  [OK] [7b] student 0 (有培训 score 85) access: granted=True
  [OK] [7c] student 1 (无培训) access: granted=False
  [OK] [7d] student 0 (培训过期) access: granted=False
  [OK] [7e] student 0 (持设备, 化学实验室) access: granted=False reason='培训类型不匹配...'
  [OK] [7f] student 0 (score 85, safety=4) access: granted=False reason='高等级实验室...要求分数≥90'
  [OK] [7g] 不存在 user (999999) access: granted=False
```

**踩坑提醒**:

- **7e 漏加错类型培训 → 走分支 3 而不是 5**:
  smoke 给 student 0 加 chem_lab 的"设备"培训才能触发"类型不匹配"
- **7f 同样**: 需给 high_lab 加 score=85 培训才能触发"高等级分数不够"
- **course_enrollment 必加**: 不加会让 close_task 走 fallback 标记**所有** student 缺勤 (测试污染)

---

## 3. smoke_real_face.py — dlib 真脸端到端 (W6)

打开摄像头拍 3 帧，dlib 真检测 + 编码 + 匹配 + 业务签到。

**用法**:

```powershell
.venv\Scripts\python.exe scripts\smoke_real_face.py
.venv\Scripts\python.exe scripts\smoke_real_face.py --wait 2  # 帧间隔 2s
```

**两种结果**:

- **有摄像头 + 正对人脸** → 完整真脸路径 (7 步全过)
- **有摄像头 + 没正对人脸** (对着环境/桌面) → 降级到 fallback 静态 IO 链路
- **无摄像头** (CI / 远程) → 直接 fallback

**fallback 验证内容**:

- `face_distance` 同/异 encoding
- `save_encoding + load_user_encodings` round-trip
- `recognize` 命中 / 不命中

**踩坑提醒**:

- 项目内 `dataset/face_images/1/000-002.jpg` 是 W3 测试时存的黑图 (摄像头没启), 测不了真匹配
- 真脸端到端需 GUI 端学生 Tab 1 采 30 张图后用 Tab 2 刷脸签到

---

## 4. smoke_ui_qtest.py — QTest 真实 UI 交互 (W6)

用 PyQt5.QtTest 模拟用户键入 + 按钮点击。

**用法**:

```powershell
.venv\Scripts\python.exe scripts\smoke_ui_qtest.py
```

**覆盖**:

1. 准备 3 角色账号
2. 学生登录 + 4 Tab 切换 (人脸注册/刷脸签到/我的考勤/我的请假)
3. 教师登录 + 4 Tab 切换
4. 管理员登录 + 4 Tab + 4 chart 切换
5. 错误密码登录 (QMessageBox.warning 拦截)

**关键技术**:

- `QMessageBox.*` monkey-patch 静默 → 避免 offscreen 模态 hang
- `QTest.qWait(50-300)` 给信号槽时间
- `role_combo` 用 `itemText` 匹配

**踩坑提醒**:

- 必须在 offscreen 模式 (`QT_QPA_PLATFORM=offscreen`)
- 真用户使用时模态弹窗正常 — monkey-patch 只在 smoke 范围

---

## 5. smoke_e2e.py — 打包后端到端 (W5)

验证 `dist/attendance-system/` 在"客户机拷一份"场景下能起 GUI。

**用法**:

```powershell
.venv\Scripts\python.exe scripts\smoke_e2e.py
.venv\Scripts\python.exe scripts\smoke_e2e.py --dist C:\path\to\attendance-system
.venv\Scripts\python.exe scripts\smoke_e2e.py --keep --wait 15
```

**验收点**: 进程 10s 不挂 + app.log 含 7 关键节点 (init_db / create_all / cache / dlib OK)。

详见 `docs/PACKAGING.md` 第 4 节。

---

## 6. smoke_face.py — W3 历史 (face 采集)

W3 时写的旧烟测，验 face_service 基础 + dlib 模型加载。**已被 smoke_real_face 覆盖大部分功能**，保留作为 W3 历史参考。

---

## 7. 完整验收清单

| 项 | 命令 | 期望 |
|---|---|---|
| 单元测试 | `pytest tests/ -q` | 81 passed |
| 完整业务流 | `python scripts/smoke_full_flow.py` | 9+1 步全过 |
| 真脸端到端 | `python scripts/smoke_real_face.py` | 7 步 或 fallback IO |
| UI 交互 | `python scripts/smoke_ui_qtest.py` | 5 步全过 |
| 打包产物 | `python scripts/smoke_e2e.py` | 7 log markers |

**课程验收前必跑全 4 项**。

---

## 8. 添加新 smoke 脚本的规范

1. 文件名: `scripts/smoke_<scope>.py`
2. 顶部 docstring 写明: 范围 / 用法 / 退出码
3. 强制 `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")`
4. 业务数据 cleanup 必须倒序 (FK 反向引用)
5. 跑完 print 完整 PASS 摘要
6. 退出码 0=PASS / 1=FAIL
7. 更新本文档 (第 N+1 节)
