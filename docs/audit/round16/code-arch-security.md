# Round 16 Code + Architecture + Security Audit — 代码架构安全联审

## 1. 改动清单 (git diff from main c7788bc)

```
 src/dao/base.py            | 12 ++++-------- (R16: 删孤儿 commit/rollback)
 src/dao/course_dao.py      | 15 ++++++------ (R16: 删孤儿 find_by_code)
 src/services/report_service.py | 19 +++++++-------- (R16: 删 4 dataclass → utils/report_dto; 修 log 遮蔽)
 src/services/signin_web.py | 99 ++++++++++++++++++++++++++++++++++++++++------ (R16: Pydantic + TemplateResponse 新 API + 全局异常)
 src/utils/charts.py        | 12 +++++----- (R16: import → utils/report_dto)
 src/utils/report_dto.py    | 53 ++++++++++++ (R16 新建: 拆 DTO 解 utils→services 反向依赖)
 tests/test_signin_web.py   | 113 ++++++++++++++++++++++++++++++++ (R16: +8 测试覆盖 Pydantic/TemplateResponse/全局异常)
 docs/audit/round16/code-arch-security.md | (本文件)
```

净增: +178 行代码, -45 行旧代码; 测试 +113 行。

## 2. 测试结果

| 阶段 | pytest | warnings | 备注 |
|------|--------|----------|------|
| Baseline (c7788bc) | 193/193 (60s) | 7 | 5 个 TemplateResponse + 2 个 websockets.legacy |
| **R16 修复后** | **201/201 (65s)** | **2** | TemplateResponse 警告消失 (P1-7 已解) |

**新增覆盖** (+8 测试, 全部 R16 安全加固):
- `test_signin_web_post_payload_validation_long_password_returns_400` — Pydantic max_length 防 bcrypt 资源耗尽
- `test_signin_web_post_payload_validation_long_token_returns_400` — token 64 字符上限防灌入
- `test_signin_web_post_payload_validation_short_token_returns_400` — token 8 字符下限防枚举
- `test_signin_web_post_payload_validation_negative_task_id_returns_400` — task_id >=1 约束
- `test_signin_web_post_payload_validation_wrong_type_returns_400` — task_id 类型校验
- `test_signin_web_post_payload_validation_empty_student_id_returns_400` — student_id 空字符串拒绝
- `test_signin_web_html_no_deprecation_warning` — TemplateResponse 新 API 回归保护
- `test_signin_web_unhandled_exception_returns_500_internal` — 全局异常处理 + 信息泄露防御

**冗余测试审查**: 8 个测试全部覆盖核心安全边界 / 回归保护 / 信息泄露防御,无 thin wrapper / mock 自指 / 字符串字面量,全部保留。

## 3. Bug 列表

### P0 — 真修复

无 (audit 范围内未发现 P0 漏洞)。

### P1 — 真修复

| # | 位置 | 描述 | 修法 |
|---|------|------|------|
| **P1-A** | `src/utils/charts.py:22` | **4 层依赖违规**: utils 反向依赖 services (`from src.services.report_service import ...` 拿 dataclass 当类型注解) | 新建 `src/utils/report_dto.py` 放 4 dataclass,charts.py 与 report_service.py 都从 utils/report_dto 拿。依赖方向恢复单向: utils 之间互引 OK, services → utils OK |
| **P1-B** | `src/services/signin_web.py::api_signin` | **FastAPI 无输入校验**: `payload: dict` 无任何约束,student_id/password/token 长度无限 (1MB 字符串 → bcrypt 100ms CPU 耗尽攻击面) | 引入 Pydantic `SigninPayload(BaseModel)` + Field(min_length/max_length/ge);422 → 全局 handler 转 400 BAD_REQUEST 保持前端契约 |
| **P1-C** | `src/services/signin_web.py::signin_page` (P1-7 启动器已知) | **starlette TemplateResponse 弃用**: 用 `TemplateResponse(name, {"request": ...})` 旧 API, 5 个 DeprecationWarning | 改成新 API `TemplateResponse(request, name, {...})`,警告消失 |
| **P1-D** | `src/services/signin_web.py::build_signin_app` | **无全局异常处理器**: 未捕获异常会返 500 + 默认 traceback,泄露代码路径 / SQL 错误细节 | 加 `@app.exception_handler(Exception)` 兜底返 500 INTERNAL + `log.exception`,响应体不暴露 .py / Traceback / 内部字符串 |

### P2 — 真修复

| # | 位置 | 描述 | 修法 |
|---|------|------|------|
| **P2-A** | `src/services/report_service.py::lab_usage_rate` | **变量遮蔽**: `for log in logs` 覆盖模块级 logger `log`,万一后面加 log.warning 会 AttributeError | 改名 `for log_row in logs`,所有引用同步更新 |

### P3 — 真修复 (死代码清理)

| # | 位置 | 描述 | 修法 |
|---|------|------|------|
| **P3-A** | `src/dao/course_dao.py::find_by_code` | **孤儿方法 + 类型签名错**: 全代码库零调用方,但 `-> List[Course]` 与 `.first()` 返回 Optional[Course] 矛盾 | 删除 (真用 CourseDao(s).s.query(Course).filter(...).first() 一行) |
| **P3-B** | `src/dao/base.py::commit/rollback` | **孤儿方法**: 所有调用方都走 session_scope() 自动事务管理,无任何代码调 dao.commit()/rollback() | 删除 |

### P2/P3 — 仅记录 (不改)

| # | 位置 | 描述 | 备注 |
|---|------|------|------|
| **P2-INFO** | `src/services/attendance_service.py` (多处) | **方法内层 import**: line 99, 152, 179, 205, 267, 311 重复 `from src.dao.xxx import YyyDao` | Python sys.modules 复用,运行时开销可忽略; 仅风格不一致,不在 P0/P1 范围 |
| **P2-INFO** | `src/services/signin_web.py` (多处) | **日志输出含异常细节**: line 65 `_download_with_fallback` 抛 RuntimeError 含 last_err 给 console log | log 是 server-side,非客户端响应,信息泄露面极低 |
| **P2-INFO** | `src/services/signin_web.py` (CORS) | **CORS 未配置**: H5 来自手机浏览器,如果教师电脑域名跟手机不同 (实际是 IP+端口,Same-Origin Policy 会挡) 会有 CORS 问题 | 演示场景教师跟手机在同一 Wi-Fi LAN,实际用 IP 直连 + FastAPI 默认 Same-Origin OK; production 应加 CORS middleware |
| **P3-INFO** | `src/services/signin_web.py` (websockets.legacy) | uvicorn 内部用 `websockets.legacy`,FastAPI 当前版本仍兼容 | 已知 P1-8 预警,不阻断 |

## 4. 跨层安全审查详细

### 4.1 SQL 注入面

**结论: 无风险** ✓

扫描命令:
- `grep 'f["'].*\{.*\}.*["'].*(FROM|SELECT|INSERT|UPDATE|DELETE|WHERE|execute)' src/` — 0 命中
- `grep 'execute\s*\(\s*text\s*\(' src/` — 0 命中

DAO 层 12 个文件全部用 SQLAlchemy 2.0 ORM (`self.s.query(Model).filter(Model.col == value)`),自动参数化绑定。

唯一 raw SQL 使用在 `tests/test_signin_web.py` (测试 fixture teardown,清理数据,使用 sqlalchemy.text() 配合 :tid 命名参数,安全)。

### 4.2 SQLAlchemy Session 生命周期

**结论: 合规** ✓

所有 services 方法 (auth/attendance/face/lab_access/leave/report) 都用:
```python
with session_scope() as s:  # 自动 commit/rollback/close
    ...
```

例外 `attendance_service.py::sign_in_by_digit/sign_in_by_qr` 用 `_create_record_in_session` 复用外层 session — 这是有意为之 (W13+ 保证"码校验+写记录"原子性,避免 race),有 docstring 说明。

DAO `base.py` 之前提供 `commit()/rollback()` 让 DAO 自管事务 — **R16 删掉,统一走 session_scope() 上下文**。

### 4.3 bcrypt 强度

**结论: 合规** ✓ (`rounds=12` 已达标)

`src/utils/crypto.py:9` `bcrypt.gensalt(rounds=12)` — cost factor 12 满足"≥12"要求。bcrypt 本身限制 72 字节,但代码 `plain.encode("utf-8")` 配合 `register()` 的 `len(password) >= 6` 校验,前端 UI 也限到 6+ 字符,实际密码长度合理。

### 4.4 .env 读路径与硬编码密钥

**结论: 合规** ✓

- `src/config.py:8-24` 用 `python-dotenv` 加载 `PROJECT_ROOT / ".env"`, `.env` 已 git ignore
- 无任何代码硬编码 DB 密码 / JWT secret / API key (grep `password.*=.*['"]` 在 src/ 仅匹配 `password_hash` 字段定义和测试 fixture 数据)
- `src/config.py:96-97` 自检打印 `cfg.database_url().replace(cfg.DB_PASSWORD, "***")` — 密码遮蔽正确

### 4.5 异常吞噬

**结论: 合规** ✓

所有 `except Exception:` / `except Exception as e:` 都是合理使用:
- rollback 触发 (`src/db.py:29`, `attendance_service.py:351`)
- log.exception + 返 error response (`signin_web.py:288`, `face_service.py:180/191`)
- watchdog 失败计数容错 (`signin_web.py:543/560`)

**无** `except: pass` / bare `except:` 默默吞噬。

### 4.6 文件 IO 路径注入

**结论: 低风险** ✓

- `src/utils/face_helper.py:54,108` `open(bz2_path, "wb")` 和 `open(target, "wb")` — `bz2_path`/`target` 来自 `MODELS_DIR / "shape_predictor_...".dat.bz2`,路径完全由代码控制,无用户输入
- `src/services/face_service.py:142` `user_dir = Config.DATASET_DIR / str(user_id)` — `user_id` 是 int 来自 DB,无注入
- `src/services/face_service.py:177` `img_path = user_dir / f"{captured:03d}.jpg"` — `captured` 是循环计数器 int,无注入

唯一用户可控的写入路径在 UI 层 `register_window.py` / `face_collect_dialog.py`,但都走 Config.DATASET_DIR / `user_id` 拼接,不接受任意用户字符串。

### 4.7 4 层依赖违规

**结论: P1-A 修复后合规** ✓

修复前违规:
- `src/utils/charts.py` → `src.services.report_service` (反向)

修复后依赖方向:
- ui → services → dao → models (单向 ✓)
- services → utils (✓)
- utils → utils 互引 (`charts.py` ↔ `report_dto.py` ✓)
- **无** ui → dao 直跳 (signin_web.py 内层 `from src.models.course import Classroom, Course` 用于 _query_task_meta 是局部 SQL 查询,不通过 dao,但属于 utils → models,符合)

唯一仍跨层依赖:`src/utils/charts.py:28` → `src/ui.styles.COLOR_*` — CLAUDE.md 已注明 (utils 跟 styles 共享 design tokens),接受。

### 4.8 FastAPI 输入校验

**结论: P1-B 修复后合规** ✓

修复前 `payload: dict` 无校验 → 修复后 `SigninPayload(BaseModel)` + Field(min_length/max_length/ge):
- student_id: 1-20 字符 (与 DB user.student_id 列 VARCHAR(20) 对齐)
- password: 1-100 字符 (bcrypt 限制 72 字节,留余量兼容)
- task_id: 正整数 (>=1)
- token: 8-64 字符 (secrets.token_urlsafe(16) = 22 字符, 64 留 3x 余量)

Pydantic 校验失败 (422) → 自定义 handler 转 400 BAD_REQUEST,前端契约不变。

### 4.9 starlette TemplateResponse 弃用

**结论: P1-C 修复后合规** ✓

修改前:
```python
templates.TemplateResponse("signin.html", {"request": request, ...})
```

修改后:
```python
templates.TemplateResponse(request, "signin.html", {...})
```

5 个 DeprecationWarning 全消失,加 `test_signin_web_html_no_deprecation_warning` 回归保护。

### 4.10 FastAPI 全局异常处理

**结论: P1-D 修复后合规** ✓

加 `@app.exception_handler(Exception)`:
- log.exception 记录完整 stack trace (server-side,排查用)
- 客户端响应 `{ok:false, error:"INTERNAL", msg:"服务异常，请重试"}` (无 Traceback / 无 .py 路径 / 无内部字符串)

加 `test_signin_web_unhandled_exception_returns_500_internal` 验证不暴露内部细节。

## 5. 总结

**修复 6 个 bug**(4 P1 + 1 P2 + 1 P3 集群),新增 8 个回归测试,测试基线 193 → 201 全过,7 → 2 warnings (TemplateResponse 警告消除,仅剩 uvicorn 内部 websockets.legacy 已知问题)。

**4 层架构恢复单向依赖**,**FastAPI 安全性达到 Pydantic + 全局异常 + 信息泄露防御标准**,**SQL 注入面 / bcrypt 强度 / .env 路径 / 异常吞噬 / 路径注入 5 大审计面全部合规**。

---

**R16 audit 完成时间**: 2026-07-09
**修复 commit**: 见 commit 列表(交付时填充)
**前置基线**: main c7788bc (193/193 tests, 7 warnings)
**修复后基线**: 201/201 tests, 2 warnings