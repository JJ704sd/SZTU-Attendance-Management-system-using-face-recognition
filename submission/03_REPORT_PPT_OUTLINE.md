# 答辩 PPT 框架 (Markdown 草案)

> **说明**: 本文档是 PPT 内容草案, 12-15 页, 5 分钟陈述用。
> 排版建议: 1 页 1 主题, 关键词加粗, 图表用项目截图。
> 配套材料: `submission/01_DESIGN_PROPOSAL.md` (整体设计) + `submission/04_DEMO_VIDEO_SCRIPT.md` (演示视频)

---

## 第 1 页 — 封面 (10s)

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│         智能考勤与实验室准入系统                         │
│         Smart Attendance & Lab Access System         │
│                                                      │
│         ─── 答辩汇报 ───                              │
│                                                      │
│   团队: [组长姓名] [组员1] [组员2] [组员3] [组员4]      │
│   课程: 数据库原理课程设计                              │
│   时间: 2026-06-20                                   │
│   学院: 深圳技术大学 健康与环境工程学院                  │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 第 2 页 — 目录 (5s)

```
1. 项目背景与意义
2. 需求分析
3. 系统架构设计
4. 数据库设计
5. 核心功能演示
6. 测试与质量保证
7. 跨机可行性
8. 创新点与亮点
9. 项目总结与展望
```

---

## 第 3 页 — 项目背景与意义 (30s)

### 业务痛点
- **传统签到效率低**: 5 分钟点名 50 人, 占课堂 1/6 时间
- **代签难以防范**: 刷卡/纸质签到易代签, 溯源困难
- **实验室管理松散**: 谁/什么时候/进了哪个实验室 无审计
- **跨机部署困难**: dlib cmake 编译 / MySQL 字符集 / 防火墙 / LAN IP

### 解决方案
- **3 种签到方式**: 刷脸 + 数字码 + 二维码, 防代签
- **W14 多端登录**: 手机扫码 → 浏览器 → 教师端实时反馈
- **3 角色完整业务链**: 学生 / 教师 / 管理员
- **跨机可行性 4 P0 修复**: 阿里 DNS / gitee 镜像 / 防火墙文档

**关键词**: 智能 / 防代签 / 跨机可跑

---

## 第 4 页 — 需求分析 (20s)

### 3 角色 4-5-5 Tab 矩阵

| 角色 | Tab 数 | 核心场景 |
|---|---|---|
| **学生** | 4 | 人脸注册 / 3 种签到 / 我的考勤 / 请假 |
| **教师** | 4 | 发起考勤 / 历史考勤 / 统计报表 / 账号 |
| **管理员** | 5 | 实验室 CRUD / 安全培训 / 准入日志 / 使用率报表 / 人脸管理 (W12 加) |

### 非功能需求
- 响应 ≤ 2s | 准确率 ≥ 95% | 并发 ≥ 10 | 跨平台 Windows 10/11
- 219 单元 + 10 smoke 测试

---

## 第 5 页 — 系统架构设计 (30s)

### 4 层架构

```
┌────────────────────────────────────────┐
│  UI 层 (src/ui/)                       │
│  - 5 主窗口 + 13 widget                │
│  - PyQt5 5.15                          │
└────────────────────────────────────────┘
              ↓ 调 service
┌────────────────────────────────────────┐
│  Service 层 (src/services/)            │
│  - 7 service: auth/attendance/face/    │
│    lab_access/leave/report (+signin_web)
│  - 业务逻辑: 3 种签到统一 _create_record
└────────────────────────────────────────┘
              ↓ 调 dao
┌────────────────────────────────────────┐
│  DAO 层 (src/dao/)                     │
│  - 13 dao + SQLAlchemy 2.0 ORM         │
│  - 防 SQL 注入 + 跨数据库可移植        │
└────────────────────────────────────────┘
              ↓ 调 model
┌────────────────────────────────────────┐
│  Model 层 (src/models/)                │
│  - 8 ORM + 4 张表无 ORM 走纯 SQL       │
│  - 共 14 张表                          │
└────────────────────────────────────────┘
```

**严格自顶向下依赖, 禁止反向**

---

## 第 6 页 — 数据库设计 (30s)

### 14 张表关系图 (核心)

```
                    ┌────────┐
                    │  user  │ (主表)
                    └────┬───┘
        ┌──────┬──────┬─┴──┬──────┬──────┬──────┐
        │      │      │    │      │      │      │
        ▼      ▼      ▼    ▼      ▼      ▼      ▼
  ┌────────┐┌──────┐┌────┐┌────┐┌────┐┌────┐┌────┐
  │face_  ││atten-││atten││leave││lab_ ││lab_ ││cour-│
  │encod. ││dance ││dance││req. ││trai-││acce-││se_e│
  │       ││_task ││_rec.││     ││ning ││ss_..││nrol│
  └────┬───┘└──┬───┘└──┬─┘└──┬─┘└──┬─┘└──┬─┘└──┬─┘
       │       │       │     │     │     │     │
       │       └───────┴─────┴─────┴─────┘     │
       │              (FK → user)              │
       │                                       │
       └──── (CASCADE 删 user 时级联) ───────────┘
```

### 关键设计
- **字符集**: utf8mb4 + utf8mb4_unicode_ci (支持 emoji)
- **3 UNIQUE 约束**: (task, student) / (student, course) / (course, teacher, role)
- **19 FK 关系**: 全部走 SQLAlchemy ORM, 自动维护
- **CASCADE**: face_encoding / attendance_record / leave_request / task_signin_code

**数据完整性**: 14 张表 + 19 FK + 3 UNIQUE, 0 死表

---

## 第 7 页 — 核心功能 1: 3 种签到方式 (40s)

### 7.1 刷脸签到
```
采集 (CameraWidget 30 张)  →  dlib 编码 (128 维 float32)  →  入库 face_encoding
                                                                          ↓
签到 (CameraWidget 500ms 抓帧)  →  face_helper.face_encodings  →  全量比 _FaceCache
                                                                          ↓
                              距离 ≤ 0.45  →  _create_record  →  写 attendance_record
```

### 7.2 数字码签到 (对分易式)
```
教师生成 4 位数字码 + 60s 倒计时  →  task_signin_code 表 is_active=1, expires_at
                                                                              ↓
学生输入 4 位码  →  查 active + 未过期  →  _create_record  →  写 attendance_record
```

### 7.3 二维码签到 (电脑 + W14 手机)
```
教师生成 base64 token + 60s 倒计时  →  渲染 250x250 PNG (无路径, 纯内存)
                                                                  ↓
【电脑】 CameraWidget 抓帧 + cv2.QRCodeDetector  →  _create_record
【手机】 扫 → 浏览器 H5 签到页 → 输账号密码 →  POST /api/signin → 写记录
```

### 7.4 统一公共核 (`_create_record`)
```python
def _create_record(self, task_id, user_id, signin_method, match_score=None):
    # 边界 1: task 存在 + status='open'
    # 边界 2: user 存在 + role='student' (防 FK 1452 race)
    # 边界 3: UNIQUE(task, student) 拦截 → 返 None
    # 边界 4: 迟到判定: now > start_time + 10min → 'late', 否则 'present'
    # 写: INSERT attendance_record
    # 返: AttendanceRecord (已 expunge)
```

**3 种签到共用同一核, 业务规则不重复, W13+ 核心架构升级**

---

## 第 8 页 — 核心功能 2: W14 多端登录 (30s)

### 架构: FastAPI 嵌入 PyQt 进程

```
┌────────────────────────────────────────────┐
│  PyQt 进程 (主 GUI 线程)                     │
│   - StudentWindow / TeacherWindow           │
│   - SigninCodeDialog (含 FastAPI server)    │
│        ┌──────────────────────────┐         │
│        │ FastAPI (uvicorn 嵌入)   │         │
│        │ - uvicorn.Server         │         │
│        │ - daemon Thread          │         │
│        │ - 0.0.0.0:5180 (LAN)     │         │
│        └──────────────────────────┘         │
└────────────────────────────────────────────┘
                  ↕ HTTP (LAN)
┌────────────────────────────────────────────┐
│  手机浏览器                                  │
│  - http://<lan_ip>:5180/signin/<task>/<tok>│
│  - 输账号密码 → POST /api/signin            │
│  - 3s polling GET /api/signin/latest       │
└────────────────────────────────────────────┘
```

### 关键修复 (W15+)
- 端口冲突重试 1 → 5 次 (5180-5184)
- watchdog 失败阈值 3 → 6 次 (30s 容错)
- 删 `tok != token` 闭包校验, 实时查 DB
- get_lan_ip 改阿里 DNS 223.5.5.5

**创新点**: 多端登录在桌面应用内嵌, 教师端实时反馈, 不依赖外网

---

## 第 9 页 — 核心功能 3: 实验室准入 7 分支 (20s)

### lab_access_service.check_access(student_id, lab_id)

```python
def check_access(student_id, lab_id):
    # 1. 学生账号有效 (is_active=1)
    # 2. 实验室存在 + safety_level 在范围
    # 3. 学生有有效培训记录 (expiry_date > now)
    # 4. 安全等级 ≤ 培训等级
    # 5. 未超 5 分钟重复准入 (防刷)
    # 6. 准入理由 (科研 / 课程 / 培训)
    # 7. 写 lab_access_log 审计记录
    return (granted, reason)
```

### 4 类统计报表
- 课程出勤率排行 (Bar)
- 缺勤预警名单 (Table)
- 出勤趋势 (Line)
- 实验室使用率 (Heatmap)

---

## 第 10 页 — 测试与质量保证 (30s)

### 219 单元测试 + 10 smoke 端到端

| 类型 | 数量 | 通过率 |
|---|---|---|
| 单元测试 (pytest) | 219 | **219/219 ✓** |
| 端到端 smoke | 10 | **10/10 ✓** |
| 跑测时间 | ~60s | 0 业务 warning |

### 10 个 smoke 脚本
1. `smoke_full_flow.py` — 完整业务流
2. `smoke_real_face.py` — dlib 真脸端到端
3. `smoke_ui_qtest.py` — QTest 真实 UI
4. `smoke_e2e.py` — 打包后端到端
5. `smoke_signin_methods.py` — 数字码 + 二维码签到
6. `smoke_audit_history.py` — 6 次 bug 审计回归
7. `smoke_full_regression.py` — 6 service + 13 dao 全公开方法
8. `smoke_qrcode_build.py` — W14+ 防 hiddenimports 漏配 (二维码)
9. `smoke_signin_web.py` — W14 H5 多端签到
10. `smoke_signin_web_build.py` — W14+ 打包后多端登录

### 6 次 bug 审计 (W7-W12, 36 真 bug)
- W7: 9 死 import + 2 死方法 + 1 排序 tie-break + 1 测试污染
- W8: closeEvent 资源泄漏 + 注册字段长度校验
- W9: CameraWidget bool→Lock + face_collect 不 accept + 双摄像头冲突
- W10: matplotlib 内存 + dlib 下载超时
- W11: int/float/env 转换 + 20 领域系统扫
- W12: P0 验收修复 12 真 bug + 2 业务功能

---

## 第 11 页 — 跨机可行性 (W15+ 4 P0 + 5 P1) (20s)

### 4 P0 (必修)
| 修复 | 触发条件 | 方案 |
|---|---|---|
| init_db.py 跑 migration_w14.sql | 14 张表建不全 | 加 `--migration` 参数 + 顺序 |
| import_schedule.py 删错误脚本提示 | 跑通报"找不到脚本" | 改 `scripts/` 显式 list |
| TEAM_SETUP.md 统一 Python 3.10+ | 3.11/3.12 装不上 dlib | 软化到 "3.10+ 推荐 3.13.x" |
| get_lan_ip 改阿里 DNS | 国内组员拿不到 IP | 探测 223.5.5.5 (阿里 DNS) |

### 5 P1 (次修)
- main.py 启动验 .env
- TEAM_SETUP.md 加防火墙说明
- TEAM_SETUP.md 数字同步 (219 / 14 表 / 10 smoke)
- signin_web 端口重试 5 次 (5180-5184)
- signin_web watchdog 6 次 (30s 容错)

**验收**: 4 P0 + 5 P1 修复全过, 组员零环境也能跑

---

## 第 12 页 — 创新点与亮点 (20s)

### 6 大创新

1. **W14 多端登录**: FastAPI 嵌入 PyQt 进程, 桌面应用具备 Web 服务能力
2. **3 种签到统一公共核**: `_create_record` 业务规则不重复, W13+ 架构升级
3. **跨机可行性 4 P0 修复**: 国内组员零环境也能跑, 阿里 DNS / gitee 镜像 fallback
4. **face encoding 统一 np.float32**: 序列化/比对链路量纲一致
5. **dlib-bin 预编译 wheel**: 避开 cmake 编译坑, Python 3.10+ 通吃
6. **6 次 bug 审计 36 真 bug**: W7-W12 系统扫, commit 可追溯

### 关键技术决策
- dlib-bin==20.0.1 而非源码编译
- 不依赖 face_recognition 库, 自写 4 核心 API
- bcrypt 而非明文
- SQLAlchemy 2.0 ORM 防 SQL 注入
- PyQt5 而非 Tkinter
- PyInstaller onedir 380 MB 一键 exe

---

## 第 13 页 — 项目总结与展望 (20s)

### 完成度
- ✅ **219 单元测试 + 10 smoke** 端到端全过
- ✅ **14 张表 + 19 FK + 3 UNIQUE** 数据完整
- ✅ **7 service + 15 dao + 13 widget** 业务闭环
- ✅ **W14 多端登录** 创新功能
- ✅ **跨机可行性 4 P0 + 5 P1** 修复
- ✅ **5 份 docs/** + **3 份 superpowers plans/** + **5 份 submission/** 文档完整
- ✅ **105 commit (audit-round16 HEAD)** GitHub 完整迭代

### 展望
- 集成 GStreamer 摄像头 (Linux 兼容)
- 引入 Redis 缓存签到码 (替代 SQLite/MySQL 查)
- 支持 Sentry 错误监控
- 提供 Docker 镜像 + 一键启动

---

## 第 14 页 — Q&A (自由问答)

### 评委可能问 + 我们的标准答案

| 问题 | 标准答案 |
|---|---|
| "dlib 怎么装的？" | "用 dlib-bin 预编译 wheel, 避开 cmake 编译坑, 详细见 TEAM_SETUP.md" |
| "为什么不只刷脸？" | "W13+ 加了 3 种, 对分易式 UX, 防刷和兜底, 刷脸失败还能用码" |
| "W14 H5 怎么实现？" | "FastAPI 嵌入 PyQt 进程, uvicorn + daemon 线程, 详细见 signin_web.py" |
| "跨电脑能跑吗？" | "4 P0 + 5 P1 修复, 阿里 DNS, gitee 镜像, 防火墙文档, 详细见 TEAM_SETUP.md" |
| "有没有 License 风险？" | "17 个第三方库全部 MIT/BSD/Apache, 无冲突, 详细见 02_ATTRIBUTION.md" |
| "测试覆盖率？" | "219 单元 + 10 smoke, 95% 核心逻辑覆盖, 0 业务 warning" |
| "数据库设计亮点？" | "3 UNIQUE 约束, 19 FK, CASCADE, 详细见 06_DATABASE.md" |
| "为什么用 PyQt5？" | "5 主窗口 + 13 widget 大量表格 + 表单, 控件丰富" |

---

## 答辩技巧

1. **前 30s 抓眼球**: 直接说 "3 种签到方式 + W14 手机扫码 + 跨机零环境"
2. **架构图 + 数据流图优先**: 评委看懂架构, 业务自己就懂
3. **数字说话**: 219 单元 / 10 smoke / 14 张表 / 105 commit / 4 P0 修复
4. **避免长代码**: 关键逻辑用伪代码 + 流程图
5. **Q&A 准备 8 个常见问题** (见上), 主动抛出

**建议答辩时长**: 5 分钟陈述 + 5 分钟 Q&A = 10 分钟

---

—— PPT 框架完毕, 共 14 页, 5 分钟陈述

**排版建议**: 标题用 24-28pt 加粗, 正文 18-20pt, 关键数字 (219/10/14/105) 32pt 高亮
