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
- `.docx` 入库 hash + commit（att