# W6 实施计划：未实现部分 + 真人人脸端到端

**编写时间**: 2026-06-06 20:11
**截止**: 6-20（项目大截止）
**风格**: 跟 W3/W4/W5 同款 writing-plans，每个 phase 独立可验收

## 现状摸底（06-06 20:10）

W5 收口后跑 `smoke_full_flow.py` 9 步全过，但发现 **3 类未实现**：

| 类别 | 内容 | 状态 |
|---|---|---|
| **A. leave_request 请假流程** | schema 留了表, model 有, service/UI 没接 | **0%** |
| **B. check_access 完整 7 分支** | 验过 4 个, 缺 3 个 (类型不匹配 / 高等级分数 / 不存在) | 4/7 |
| **C. 真人人脸端到端** | dlib 模型加载路径 OK, 但 collect_for_user + 真匹配未实测 | 0% |
| **D. 真实 UI 交互** | 窗口能起 + Tab 切 OK, 按钮点击 + 输入框未用 QTest 验 | 部分 |

**用户选**: 全部完成 (本次)

## Phase 1: leave_request 流程 —— 0.5-1 天

数据库已有 `leave_request` 表 (W2 留)，需要：
- `src/services/leave_service.py` 新建
  - `student_apply(student_id, task_id, reason) -> LeaveRequest` (状态 pending)
  - `teacher_review(request_id, approve: bool, comment) -> LeaveRequest` (状态 approved/rejected)
  - `list_pending_for_teacher(teacher_id) -> List[LeaveRequest]`
- `src/dao/leave_request_dao.py` (复用 BaseDao)
- 测试 `tests/test_leave_service.py` (3 用例)
- UI 接入:
  - StudentWindow: 加 "请假" 按钮 + 弹窗 (输入 task_id + reason)
  - TeacherWindow: 在任务详情里看 leave_request 列表 + 批/驳
- `smoke_full_flow.py` 加 step 5.5: student 请假 → teacher 批

**验收**: smoke_full_flow.py 9+1 步全过；71+3 测试全过

## Phase 2: check_access 补全 3 分支 —— 0.2 天

加测试覆盖：
- **培训类型不匹配**: lab=设备, training=化学 → 拒绝 "培训类型不匹配"
- **高等级实验室分数不够**: lab.safety_level=4 + score<90 → 拒绝
- **不存在的 user / lab**: → 拒绝 "用户或实验室不存在"

**验收**: 71+3=74 测试全过 (test_lab_access_service 7 分支覆盖)

## Phase 3: 真人人脸端到端 —— 0.5-1 天

**挑战**: 需要摄像头硬件 + 真人正脸
**方案**:
- 用 `dataset/` 已有图片 (W3 测试存过的)
- 或用户自己拍 1 张正脸照
- 写 `scripts/smoke_real_face.py`:
  1. 找/拍一张正脸照 `test_face.jpg`
  2. 注册一个 student
  3. `face_service.save_encoding(student_id, encoding, image_path)` 喂入 (用 face_helper.face_encodings 真编码)
  4. teacher create_task
  5. 用同图 `sign_in_by_face` 测真匹配 (distance < 0.45)
  6. 拿图路径不同时再测 → 距离更大 (验证真区分)
- 不依赖摄像头 (用静态图)

**验收**: smoke_real_face.py PASS；distance 同图 < 0.4, 异图 > 0.5

## Phase 4: QTest 真实 UI 交互 —— 0.3 天

**目标**: 用 PyQt5.QtTest 模拟"用户输入 + 点击按钮"

- `scripts/smoke_ui_qtest.py`:
  1. 启 LoginWindow (offscreen)
  2. QTest.keyClicks 输用户名 + 密码
  3. QTest.mouseClick 登录按钮
  4. 断言: 打开对应 role 的 window (Teacher / Admin / Student)
  5. 切 Tab: QTest.mouseClick tab bar
  6. 切 Chart: QTest.keyClicks + Enter

**验收**: smoke_ui_qtest.py PASS；offscreen 模式下 3 角色登录 + 切 Tab 全过

## Phase 5: 整合 smoke + commit + push —— 0.2 天

- scripts/ 现有: init_db / run_dev / smoke_face (W3) / smoke_e2e (W5) / smoke_full_flow (W6)
- 加 smoke_real_face (Phase 3) + smoke_ui_qtest (Phase 4)
- docs/SMOKE_TESTS.md: 列出所有 smoke 用法
- commit + push

---

## 风险 + 备选

| 风险 | 触发 | 应对 |
|---|---|---|
| 用户电脑没摄像头 | smoke_real_face 跑不了 | 用静态图 (无需摄像头) 替代 |
| dataset/ 没正脸图 | sign_in 测不了 | 用户临时拍 1 张 (README 指引) |
| QTest 跨平台差异 | Linux offscreen 行为不同 | 优先 Windows 测; 跑通就够课程验收 |
| leave_request UI 设计 | 是弹窗还是列表? | 简单弹窗 (QInputDialog) + TeacherWindow 加 tab/区 |
| PyQt5 QMessageBox 模态 | 跟 W5 P2 修复一样, 用 status label | 不弹模态 |

## 推进节奏 (按阶段验收)

- Phase 1 (leave) 做完 → smoke 9+1 步 → 测试 74 → commit → 报告
- Phase 2 (3 分支) → 测试 74 → commit → 报告
- Phase 3 (真脸) → smoke_real_face → commit → 报告
- Phase 4 (QTest UI) → smoke_ui_qtest → commit → 报告
- Phase 5 (整合 + 文档 + push)

不批量 commit, 每个 phase 单独 commit (W3/W4/W5 都是这样做的)。
最终 W6 结束统一 push 1 次 (除非用户中途要求推)。
