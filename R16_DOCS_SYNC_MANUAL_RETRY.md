# R16 docs-sync attempt 4 — 完整 manual_retry 指令

> 来源：owner (Mavis / mvs_1281b4f7369f4d228bd660ab3bc511c7) Cycle 5 arbitration 决策 (manual_retry)
> 工作目录：`D:\Attendance-Management-system-using-face-recognition\.worktrees\r16`
> 当前 HEAD：ea9af4d / audit-round16 / 105 commits

---

## 【问题诊断 - 看清楚再动】

verifier attempt 1/2/3 三次都 FAIL 同根因：**commit count 自指循环**

- 你写 `'docs 当前 101 commit'` → 加新 commit 同步 docs → HEAD 变 102 → 文档过期 → 又加 commit → 死循环
- 实际数字（**这是 ground truth，看完再动**）：
  - `git rev-list main --count` = **94**（main HEAD = `c7788bc`）
  - `git rev-list HEAD --count` = **105**（audit-round16 HEAD = `ea9af4d`）
  - R16 增 = **11 commit**（main + 11 = 105）
- attempt 3 你写 `'104'`，实际 **105**，差 1（没数自己那条 `ea9af4d`）

**根因**：你用的"具体数字"措辞本身就会过期。每次加新 commit 同步 docs，docs 数字变旧 → 触发下一轮 sync → 死循环。

---

## 【修法 — 二选一】

### 修法 A（推荐）：改措辞，**永远正确**

把所有 `'104 commit'` / `'105 commit'` / `'X commit'` 字面量改成：

```
main (94 commit) + R16 增 11 commit
```

或更精确：

```
HEAD = main + 11 commit (= main 94 + R16 增 11)
```

**这种措辞不依赖具体数字，未来再加 commit 也不会过期**。

### 修法 B（备选）：amend 现有 commit

1. 把所有 `'104'` 改成 `'105'`
2. `git add -u && git commit --amend --no-edit`（amend `ea9af4d`，不新增 commit）
3. amend 后 HEAD 仍是 `ea9af4d`，docs 写 105 = HEAD，匹配

---

## 【还要补 — 之前 3 attempt 都漏了】

### 1. 写 `docs/audit/round16/docs-sync.md` deliverable 入库

之前 3 次 attempt 这个 deliverable 文件**根本没写**！必须含：

- 改动清单（`git diff --stat main..HEAD` 输出）
- `.docx` 入库 hash + commit（attempt 24b230e 那条）
  - docx 内容审计（与 HANDOFF.md / SIGNIN_METHODS.md / W14-defense-outline.md 一致性矩阵）
  - 死链残留 grep 结果（应 = 0）
  - commit 列表（11 个，含 main..HEAD 全部 hash）

### 2. grep 验证 commit count

跑：`grep -rE '\b10[0-9]\b.*commit' docs/ submission/ README.md`

- 应只匹配描述性叙述（"101 commit 之内" "101+ 个 commit"），**不匹配具体 commit 总数**
- 如果还有 `'104 commit'` `'105 commit'` 等字面量 → 改成 `'main + 11 commit'`

---

## 【禁止】

- ❌ 不要直接写 `'105 commit'` / `'104 commit'` 等具体数字（下次还会过期）
- ❌ 不要改 CLAUDE.md「关键技术决策」表（已是真理之源）
- ❌ 不要改 docs/superpowers/plans/（那是 planning process 痕迹）
- ❌ 不要 push origin（留给 integration-smoke-push task）
- ❌ 不要 force push / rebase -i / 任何破坏性操作

---

## 【commit 风格 — 严格遵守】

中文主题 multi `-m`（PowerShell 不要单 -m 加 `\n`）。例：

```powershell
git add -A
git commit `
  -m 'docs(r16): commit count 改用 main + 11 措辞 + 补 docs-sync.md deliverable' `
  -m '- 12 个文件 commit count 从字面量数字改为 main + 11 措辞,永不过期' `
  -m '- docs/audit/round16/docs-sync.md 入库(3 attempt 都漏)' `
  -m '- 2 docx hash + 一致性矩阵 + 死链残留 grep 在 deliverable' `
  -m '- main = 94 / R16 增 11 / HEAD = 105'
```

**已知坑**（来自 CLAUDE.md + memory）：
- 单 `-m "subject\nbody"` 会被 PowerShell 字面 `\n` 吞 → 用 multi `-m`
- `git commit -m` body 里 `- xxx` / `:` 后跟文件名会被吞 pathspec → 把文件名放最末或用反引号引
- `git commit -m` 不带 pathspec 会把所有 staged 都带走 → 用 `git add <精确路径>` 限定

---

## 【执行后必须回报 6 项】

1. **新 commit hash + title**（`git log -1 --format='%H %s'`）
2. **`git rev-list HEAD --count` 输出**（应 = 105 或 106，依修法）
3. **`grep -rE 'main \+ 11' docs/ submission/ README.md | wc -l`**（应 ≥ 8，涵盖所有原 commit 数位置）
4. **`docs/audit/round16/docs-sync.md` 是否入库**（应是最后那个 commit）
5. **pytest 跑一遍确认 219/219 仍 PASS**：
   ```powershell
   D:\Attendance-Management-system-using-face-recognition\.venv\Scripts\python.exe -m pytest tests/ -q --tb=line
   ```
6. **0 死链验证**（应 = 0）：
   ```powershell
   Select-String -Path "D:\Attendance-Management-system-using-face-recognition\.worktrees\r16\docs\*.md" -Pattern 'http(s)?://' | Select-String -Pattern '404|dead' | Measure-Object
   ```

---

## 【回报方式】

执行完后用 `mavis communication send --to mvs_1281b4f7369f4d228bd660ab3bc511c7 --command prompt --content "..."` 发回 owner session，含上面 6 项。

owner session id：**mvs_1281b4f7369f4d228bd660ab3bc511c7**

---

## 【owner 备注】

- decision JSON 已落 `.mavis/plans/decision-cycle-5.json`（plan engine 已 apply）
- attempt 4 = manual_retry 第 1 次（task max_retries=1 在 attempt 2 已用完，这次走的是 owner arbitration channel）
- 如果 attempt 4 仍 FAIL，owner 会再做 1 次仲裁；建议 attempt 4 直接修对

**加油，这是 R16 docs-sync 最后一搏**。