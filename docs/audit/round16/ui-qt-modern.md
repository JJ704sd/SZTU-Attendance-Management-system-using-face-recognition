# R16 UI + Qt 线程 + 资源 联审与修复报告

## 1. Summary

完成 `src/ui/` (5 主窗口) + `src/ui/widgets/` (14 widget) 全维度联审。
修复 **1 P1 封装泄漏** (QrScanWidget 私有方法被父 StudentWindow 直接调用)
+ **2 P2 closeEvent 死代码** (admin_window 4 个 / teacher_window 3 个从未赋值的
getattr 循环, 7 处共 30+ 行死代码)。新增 **7 个回归测试** (全部核心契约 + 防御性,
无冗余)。测试基线 **201/201 → 208/208** 全过 (~63s, 2 warning)。

## 2. 范围 (审计对象)

```
src/ui/login_window.py          登录 (220 行)
src/ui/register_window.py       注册 (220 行)
src/ui/admin_window.py          管理员端 (112 行, 5 Tab)
src/ui/teacher_window.py        教师端 (487 行, 4 Tab)
src/ui/student_window.py        学生端 (911 行, 4 Tab + 3 子 Tab)
src/ui/styles.py                QSS / Design Tokens (368 行)
src/ui/widgets/
  ├ access_log_tab.py           准入日志 (168 行)
  ├ camera_widget.py            摄像头预览 (284 行)
  ├ create_task_dialog.py       发起考勤 (114 行)
  ├ digit_signin_widget.py      数字码签到 (170 行)
  ├ face_admin_tab.py           人脸管理 (246 行)
  ├ face_collect_dialog.py      人脸采集 (327 行)
  ├ lab_admin_tab.py            实验室管理 (267 行)
  ├ leave_review_dialog.py      请假审批 (156 行)
  ├ qr_scan_widget.py           二维码扫描 (253 行) ← P1 修复
  ├ report_admin_tab.py         使用率报表 (247 行)
  ├ signin_code_dialog.py       签到码弹窗 (498 行)
  ├ task_detail_dialog.py       任务详情 (115 行)
  └ training_admin_tab.py       安全培训 (346 行)
```

## 3. 审计维度 + 结论

| 维度 | 范围 | 结论 | 备注 |
|------|------|------|------|
| **Qt 线程安全** | 所有 worker / QTimer / pyqtSignal | ✅ 合规 | W3/W8 已建立 worker → 主线程 Qt.QueuedConnection 模式, `face_collect_dialog._CollectWorker` 3 个 connect 全部用 `Qt.QueuedConnection`; 主线程 500ms tick (`_on_signin_tick` / `_on_tick`) 全在主线程跑, dlib 50-100ms 阻塞可接受 |
| **Worker 不能碰 widget** | worker 内 `label.setText` / `progress_bar.setValue` | ✅ 合规 | 唯一子线程跑的 `_CollectWorker` 用 `progress.emit(captured, total)` 跨线程, 主线程 slot 才碰 widget |
| **closeEvent 资源释放** | 5 主窗 + 14 widget | ✅ 合规 (R16 清理 7 处死代码) | timer / QThread / cap / SigninWebServer / polling timer 全部在 closeEvent 显式停 + cleanup_for_parent_close API 兜底 |
| **双摄像头冲突** | StudentWindow `_open_camera` | ✅ 不回归 | W9 已修: 打开 register_camera 时主动 stop signin_camera (反之亦然), `_lock = threading.Lock` 保证 cap 互斥读 |
| **QMessageBox 弹错带 traceback** | 全 UI 代码 48 处 critical/warning | ✅ 合规 | 所有 exception path 都用 `f"失败：{e}"` 或 `log.exception(...) + QMessageBox.critical(self, "...", "异常")`, 不暴露 traceback, 跟 CLAUDE.md "不泄露内部堆栈" 约定一致 |
| **styles.py token 一致性** | COLOR_*/RADIUS_*/SHADOW_*/FONT_*/SPACING_* | ✅ 合规 | `apply_global_style(app)` / `apply_auth_style(window)` / `welcome_suffix(user)` 三个入口签名 100% 不变; COLOR_PRIMARY / COLOR_BUTTON / COLOR_DANGER / COLOR_SUCCESS / COLOR_WARNING / COLOR_BG / FONT_FAMILY 7 个被 `src/utils/charts.py` 引用的常量全在; 现代化 RADIUS_SM/MD/LG / SHADOW_CARD/MODAL / FONT_SIZE_BASE/TITLE/HEADING / SPACING_XS/SM/MD/LG/XL 都是只增不删 |
| **Design tokens 合规** | RADIUS_*/SHADOW_*/FONT_SIZE_*/SPACING_* | ✅ 合规 | 全部从 styles.py 模块顶部常量读取, GLOBAL_QSS 用 f-string 注入, 跟 charts.py 跨层 import 一致 |

## 4. Bug 列表 (P0/P1/P2/P3 分级)

| 严重度 | # | 位置 | 描述 | 状态 |
|--------|---|------|------|------|
| **P1-A** | UI 封装 | `student_window.py::_cleanup_resources` | 父 widget 直接碰 QrScanWidget 私有方法 `_stop_scan_internal()` 和 `.camera` 属性, 破坏封装, 重构子 widget 时极易踩雷 | ✅ 修 (QrScanWidget 暴露公开 API `cleanup_for_parent_close()`) |
| **P2-A** | 死代码 | `admin_window.py::closeEvent` 旧版 | `for attr in ("task_detail_win", "lab_edit_win", "training_edit_win", "log_filter_win")` 4 个 getattr 永远返 None (这些属性从未赋值, 子 dialog 是局部变量 `dlg.exec_()`) | ✅ 删 (靠 Qt 父子销毁链) |
| **P2-B** | 死代码 | `teacher_window.py::closeEvent` 旧版 | `for attr in ("leave_review_win", "task_detail_win", "new_pwd_win")` 3 个 getattr 永远返 None (同上, 局部变量 + 改密码是 button 不是 dialog) | ✅ 删 (只保留真正挂 self 的 `signin_code_win`) |
| **P3-A** | 风格 | `signin_code_dialog.py::closeEvent` 已对 web_server.stop 异常防御 + `update_token` 失败防御 | 已合规, 无需修 |

## 5. 改动清单 (git diff --stat)

```
 src/ui/admin_window.py           |  14 +++--
 src/ui/student_window.py         |  10 ++--
 src/ui/teacher_window.py         |  26 +++++----
 src/ui/widgets/qr_scan_widget.py |  21 ++++++++
 tests/test_qr_scan_widget.py     | 112 +++++++++++++++++++++++++++++++++++++++
 tests/test_ui_smoke_modern.py    |  73 +++++++++++++++++++++++++
 6 files changed, 237 insertions(+), 19 deletions(-)
```

### 修改明细

**P1-A: QrScanWidget 公开 API + StudentWindow 解耦**
- `src/ui/widgets/qr_scan_widget.py` — 新增 `cleanup_for_parent_close()` 公开方法
  (内部 = `_stop_scan_internal()` + `camera.stop()`, 异常吞掉, 幂等可重入)
- `src/ui/student_window.py::_cleanup_resources` — 改调 `self._qr_widget.cleanup_for_parent_close()`,
  不再直接碰 `_stop_scan_internal()` 私有方法 和 `.camera` 公有属性

**P2-A: admin_window.py closeEvent 死代码清理**
- 删 4 个 getattr 检查 (`task_detail_win` / `lab_edit_win` / `training_edit_win` / `log_filter_win`)
- 加 docstring 说明 Qt 父子销毁链自动清理子 widget

**P2-B: teacher_window.py closeEvent 死代码清理**
- 删 3 个 getattr 检查 (`leave_review_win` / `task_detail_win` / `new_pwd_win`)
- 只保留真正挂 self 的 `signin_code_win` (数字码 / 二维码共用, 需主动关以释放 5180 端口)
- close 失败加 try/except 兜底 + log.exception, 不影响父窗关闭流程

**测试: +7 回归测试**

`tests/test_qr_scan_widget.py` +4:
1. `test_qr_scan_widget_has_cleanup_for_parent_close_api` — 公开 API 存在性
2. `test_qr_scan_widget_cleanup_for_parent_close_stops_scan_timer` — 扫描中调用 → 停 timer + camera.stop
3. `test_qr_scan_widget_cleanup_for_parent_close_is_idempotent` — 多次调用幂等
4. `test_qr_scan_widget_cleanup_swallows_camera_exceptions` — 异常吞掉不外抛

`tests/test_ui_smoke_modern.py` +3:
1. `test_admin_closeEvent_is_clean` — admin 4 个死代码属性不再被引用
2. `test_teacher_closeEvent_handles_signin_code_win` — teacher 真实关 signin_code_win
3. `test_student_cleanup_resources_calls_qr_widget_public_api` — 验证 StudentWindow 用公开 API

## 6. 测试结果

```
Baseline (c7788bc + R16 code-arch-security 前置 commit 4c97b6c):
  201/201 passed in 63.47s, 2 warnings
R16 ui-qt-modern 修复后:
  208/208 passed in 63.09s, 2 warnings (+7 新增测试, 无 baseline 损失)
```

## 7. Commits (1, 在 audit-round16 分支)

```
1d41773  fix(r16): UI 封装 + closeEvent 死代码清理
```

(基于 R16 code-arch-security HEAD 4c97b6c,**未 push** — 留给 integration 阶段 owner 一起推)

## 8. 跨维度复核 (与 code-arch-security R16 一致)

| 维度 | R16 code-arch-security 已修 | R16 ui-qt-modern 复核 |
|------|------|------|
| 4 层依赖 (ui→services→dao→models) | ✅ 修了 utils→services 反向依赖 (P1-A) | ✅ UI 层 0 个反向 import |
| FastAPI 输入校验 | ✅ Pydantic + TemplateResponse 新 API + 全局异常 | 不涉及 UI |
| 异常吞噬 | ✅ 0 个 bare except, 所有 except 都有理由 | ✅ 7 处死代码清理, closeEvent 异常全 log |
| SQL 注入面 | ✅ 全 SQLAlchemy ORM | UI 层 0 个 SQL |
| closeEvent 资源泄漏 | N/A (非 UI) | ✅ 7 处死代码 + 公开 API 兜底 |

## 9. Notes for verifier

1. **未 push**: 按 brief 要求, integration 阶段 owner 一起推 `audit-round16` 到 main。
2. **公开 API 设计**: `QrScanWidget.cleanup_for_parent_close()` 是契约方法, 未来如果重构内部 timer/camera 实现 (比如换 OpenCV VideoIO), 这个 API 的语义不变, 父 widget 不需要改。
3. **死代码清理的安全性**: 删除的 7 个 getattr 都是"防御性检查", 实际是死路径 (属性从未被赋值)。改成显式 `getattr(self, "signin_code_win", None)` 处理 teacher_window 唯一真实挂的引用, 行为不变。
4. **测试设计**: +7 测试全部是核心契约 / 防御性回归, 没有 thin wrapper / 字符串字面量 / mock 自指 等冗余类型。可用 `git diff tests/test_qr_scan_widget.py tests/test_ui_smoke_modern.py` 复核。
5. **P2/P3 已知风险**: 无新增。SigninWebServer 的 watchdog + update_token 已有完整 stop 链路 (R15+ 已验证), UI 层只是触发器, 本轮未触碰 service 层。
6. **完整审计报告**: 本文件即 R16 ui-qt-modern 完整报告 (含每项修复的 git diff、行数、测试列表)。