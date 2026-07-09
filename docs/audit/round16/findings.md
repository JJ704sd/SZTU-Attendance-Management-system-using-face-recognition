# R16 docs-sync findings (P1/P2 — 留待 R17+)

> 本文件是 R16 docs-sync 任务的 P1/P2 记录。P0 已修 (见 deliverable.md + 2 个新 commit), 本文件只列未修项 + 推荐修法。

## P1 (建议修, 影响长期维护)

### F1. `docs/audit/round16/*.md` 内部 widget 计数自相矛盾

**位置**:
- `docs/audit/round16/ui-qt-modern.md:5` "14 widget"
- `docs/audit/round16/ui-qt-modern.md:42` "5 主窗 + 14 widget"

**实际**:
- `src/ui/widgets/` 共 14 个 .py 文件 (含 `__init__.py`)
- 不含 `__init__.py` = 13 个 widget
- HANDOFF.md / README.md 全部用 13 widget 口径

**冲突**:
- R16 联审报告自己写 "14 widget", 但 R16 报告主文 (line 21-33) 列出的 widget 是 13 个
- 与 R16 修过的 HANDOFF.md (7 service / 13 widget / 5 主窗口) 数字不一致

**推荐修法**: R17 开头统一 R16 审计报告口径, "14 widget" → "13 widget (directory 含 __init__.py 共 14 文件)"

### F2. `submission/01_DESIGN_PROPOSAL.md` L337 "6 service + 13 dao" 与 smoke 脚本实际不符

**位置**: `submission/01_DESIGN_PROPOSAL.md:337`

**实测** (`.venv\Scripts\python.exe -c "import scripts.smoke_full_regression as s; ..."` 或 grep):
- `scripts/smoke_full_regression.py` 只 import 5 个 service:
  - `auth_service` / `attendance_service` / `lab_access_service` / `leave_service` / `report_service`
- 缺 `face_service` (camera/dlib 依赖) + `signin_web` (W14+ 新增)
- dao 也是 12 个 (不带 signin_web 关联的 dao)

**冲突**:
- 项目总 service = 7 (含 signin_web), smoke 测试 = 5
- 项目总 dao = 15, smoke 测试 = 12
- "29/29 OK" 数字是基于 5 service + 12 dao 跑出来的, 跟项目 7+15 数字不一样

**推荐修法**: 把 "6 service + 13 dao" 改为 "5 service + 12 dao (注: 含 signin_web 时 dao 跑不动需要 pytest 数据库)" 或加脚注说明 smoke 测试是子集

### F3. `docs/superpowers/plans/2026-06-06-W4-lab-and-report.md` 仍写 "12 张表"

**位置**: `docs/superpowers/plans/2026-06-06-W4-lab-and-report.md:41`

**冲突**:
- W4 plan 是当时写的, 那时确实 12 张表
- 但用户明确说 "不要改 docs/superpowers/plans/"

**推荐**: 用户原话禁止改, 留作历史 artifact。如要更新, R17 用户确认后批量加 "本计划写于 W4, 当时 12 张表; 现在 14 张表" 注释

### F4. `docs/audit/round16/*.md` 写 "5 次 bug 审计"

**位置**:
- `docs/audit/round16/code-arch-security.md` 等多处

**实际**:
- R16 报告说 "5 次 bug 审计 (W7-W11) + W12 P0 + W14 收尾"
- 用户口径 "6 次 bug 审计 (W7/W8/W9/W10/W11/W12)" 包含 W12 P0 验收

**推荐**: 跟 F1 一起 R17 统一

## P2 (锦上添花, 不修)

### F5. HANDOFF.md 4 个超链接锚点风格不统一

- L23: `git log --oneline | head -20` (W2 → W15+, 共 14 周) — 加了 shell 提示
- L138: `dlib-bin 20.0.1` — 用 backtick
- L145: `src/utils/paths.py::APP_ROOT` — 用 backtick + 路径

风格混用, 但功能 OK, 不修。

### F6. `submission/04_DEMO_VIDEO_SCRIPT.md` SRT 字幕时间戳可能不准

**位置**: L440-454

**风险**: SRT 字幕时间是基于录屏脚本假设录 5-7 分钟写的, 实际录的时候可能对不上。需实际录屏时调整。

**推荐**: 录屏时手动调整, 不算 docs bug

## 已验证 OK 的项

- **0 死链残留**: 全仓 Grep `\]\([^h#m][^)]*\)` 跨 docs/README/submission/快速验证, 0 命中
- **gitignore 行为**: 新文件名 (orig/v1-revised) bypass 了精确匹配模式, R16 决策入库
- **测试基线**: `pytest tests/ -q` = 219 passed in ~67s 3 warning (与 doc 一致)
- **commit 历史**: 2 个新 commit on audit-round16 (24b230e + 048b2c9), 0 conflict
- **未推**: 留给 integration phase push, 不抢 verifier

## R17+ 推荐行动

1. F1 + F4: 统一 R16 审计报告数字 (10 分钟)
2. F2: 在 smoke 脚本注释加 "5 service + 12 dao" 注释 (5 分钟)
3. F3: 不动, 尊重用户原话
4. F5/F6: 不动, 锦上添花
