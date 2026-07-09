# R16 测试覆盖补足 + 冗余清理报告

**branch**: `audit-round16`
**任务窗口**: 2026-07-09 (R16 第三轮)
**执行**: coder agent
**前后 test 计数**: 208 → 219 (+11 净增, 12 新增 + 1 删除)

---

## 1. 删除冗余: 1 个文件

### 1.1 `tests/test_styles.py`  (80 行 → 0)

**判定**: 完全冗余,与 `tests/test_styles_modern.py` 重叠。

| `test_styles.py` 唯一测试的断言 | `test_styles_modern.py` 中对应覆盖 |
|---|---|
| `QLabel[role="status"][state="warning"]` QSS 规则 | `test_warning_state_visual_rule_preserved` L179 |
| `COLOR_WARNING == "#F59E0B"` 字面量 | `TestDesignTokens.test_color_tokens_are_hex_strings` L81 |
| QLabel 实例 polish 测试 | — (PyQt 内部行为,非业务) |
| `WARNING_PROMPTS = ("未识别到人脸", "识别到他人")` 字符串字面量断言 | — (literal 字面量,无业务覆盖) |
| `widget.property("state")` round-trip | — (PyQt 内部行为) |

**理由 (符合任务「thin wrapper / 字符串字面量 → 删」)**:
1. `QLabel polish + property roundtrip` 是 PyQt 内部机制, 不是本项目业务代码。
2. 唯一真正的业务断言 (warning QSS 规则 + COLOR_WARNING 字面量) 已在 `test_styles_modern.py` 100% 覆盖, 且更系统 (含 nearby 颜色验证)。
3. `WARNING_PROMPTS` 两个字符串字面量的 walk-through 是「在 widget 文字里找魔法字符串」—— 没有业务价值, 删。
4. 文件存在没意义 (1 个 test 与 11 个 test 重复) — 维护成本 ≠ 价值。

**保留**: `tests/test_styles_modern.py` (14 个 test, 完整 token/QSS 契约测试 + apply_global_style 实跑)。

---

## 2. 补覆盖: 4 处加测, 12 个新 test

### 2.1 `_FaceCache` 类方法覆盖 (新文件 `tests/test_face_cache.py`, 8 项)

**动机**: `src/services/face_service.py:215` `_FaceCache` 类 W3 引入但从未直接单测。
- 现有 `test_face_service.py` 用 `_MockCache` 测了 `recognize()`, 但 `_FaceCache` 类本身的
  singleton / `reset_for_test` / `add` / `remove_user` / `all` / `refresh` 接口契约从未测过。
- `test_face_admin_tab.py::test_face_cache_remove_user_clears_only_target` (W12) 只覆盖了
  `remove_user` 一次, 没覆盖其他 5 个方法。

**新增 8 项**:
1. `test_face_cache_get_returns_singleton_instance` — `get()` 是进程内单例 (UI 多处依赖)
2. `test_face_cache_reset_for_test_clears_instance` — `reset_for_test()` 实际清实例
3. `test_face_cache_add_stores_in_per_user_list` — `add(user_id, enc)` 增量加, 同 user 多张累积
4. `test_face_cache_remove_user_clears_only_target` — `remove_user()` 只清 target, 不影响他人 (补测试, 原本只有 1 处有)
5. `test_face_cache_remove_user_nonexistent_is_safe` — 不存在 id 是 no-op, 不抛
6. `test_face_cache_all_returns_dict` — `all()` 返 dict (空单例也返 {}, 不返 None)
7. `test_face_cache_refresh_calls_load_all_user_encodings` — `refresh()` 走 FaceService.load (契约测试, 不测实现)
8. `test_face_cache_refresh_replaces_entire_dict` — `refresh()` 是 replace 语义, 不是 merge

**autouse fixture**: 每个 test 前 `reset_for_test`, 防单例污染 (前 test 残留污染后 test)。

### 2.2 `close_task_and_mark_absent` 边界补全 (`tests/test_attendance_service.py`, +2 项)

**动机**: 任务点出 close_task 边界 (全/0/partial enrolled):
- 已有 `test_close_task_uses_course_enrollment` 覆盖 partial (3 student, 2 enrolled + 1 not)
- 已有 `test_close_task_fallback_to_all_students_when_no_enrollment` 覆盖 0 enrollment + fallback
- 缺: **all enrolled (全名单)** — 3 学生全选, close 后应 3 条 absent, 不能漏
- 缺: **完全空课程** — 0 enrollment + 其他 fixture 没污染 → close 应静默不挂, 不写 record

**新增 2 项**:
1. `test_close_task_all_enrolled_marks_each_as_absent` — 3 学生全 enroll → 3 条 absent record (无丢无重)
2. `test_close_task_empty_course_no_students_gracefully` — 0 enrollment + 无其他 student → close 不抛, teacher 自己绝不被 mark

**配套 helpers (4 个 `_setup_*` / `_cleanup_*`)** 单独定义在 file 底部, 避免污染现有 fixtures。

### 2.3 `teacher_review` rejected 后再 review 应 raise (`tests/test_leave_service.py`, +1 项)

**动机**: 任务点出"已 rejected 后再 review 应 raise"。
- 已有 `test_teacher_review_already_processed_raises` 覆盖 **approve → 改 approve/reject 都 raise**
- 缺: **reject → 再任何 review 也 raise** (同一 raise 分支, 但任务点明确要求覆盖)

**新增 1 项**:
1. `test_teacher_review_rejected_then_review_raises` — 先 reject → 再调 raise + DB 验证 status 仍是 `rejected` (被 raise 拦截, 没二次写)

**实现核对**: `src/services/leave_service.py:96-97` 单 raise 分支 `if req.status != "pending": raise LeaveError(...已处理...)`, 不区分 approved/rejected — 所以测试帮防后续 refactor 把 approve / reject 分支化。

### 2.4 `dao.find_active_by_value` 多条件组合过滤 (`tests/test_task_signin_code_dao.py`, +1 项)

**动机**: 任务点出多条件组合过滤。
- 现有 4 个 test 各覆盖单个过滤条件 (wrong_value / expired / inactive / happy_path)
- 缺: **同时校验 5 个条件 (task_id + code_type + code_value + is_active=1 + expires_at>now) 的组合行为**

**新增 1 项**:
1. `test_find_active_by_value_combo_filter_all_conditions` —
   - (a) 全条件 match → 返 active_digit
   - (b) value 撞但 type 不 match → None
   - (c) 全条件 match → 返 active_qr (验证 type filter)
   - (d) value 撞但 expired → None (时间过滤)
   - (e) value 撞但 wrong task_id → None (防「value 撞上但签别人 task」)

这是学生签到校验的核心 SQL — 单条件覆盖已过, 但「value 撞上 + task 错」的覆盖空白是新风险点 (W15+ 修的就是这类 bug)。

---

## 3. 任务点「dao.find_by_teacher 在 join + 主教师并存时的去重」

**核对结果**: **已在 `tests/test_course_dao.py:104` 覆盖**, 任务描述冗余。

```python
# test_course_dao.py:104
def test_find_by_teacher_dedupes_main_and_assistant():
    """同一门课同时是主讲(在 Course.teacher_id)又是关联表 main 角色 →
    DISTINCT 兜底, 不能返 2 行。"""
```

无需新增。R16-P1A (W15+) 的 course_teacher 关联表迁移时一并补了此回归点。

---

## 4. 全测试结果

```
$ pytest tests/ -q
219 passed, 2 warnings in 66.34s (0:01:06)
```

**对比 baseline (R16 第二轮尾)**: 208 → **219 passed** (+11 净增)

| 项 | 数 |
|---|---|
| 删除测试文件 | 1 (`test_styles.py`) |
| 删除测试用例 | -1 (来自被删文件的单 test) |
| 新增测试文件 | 1 (`test_face_cache.py`) |
| 新增测试用例 | +12 (8 _FaceCache + 2 close_task + 1 leave rejected + 1 combo filter) |
| **净增** | **+11** |

**warnings**: 仍是 2 个 (`websockets.legacy` + `uvicorn.protocols.websockets_impl` 的 starlette 依赖项 DeprecationWarning, 来自 test_signin_web.py 启动 uvicorn 子进程, 非本轮新增)。
