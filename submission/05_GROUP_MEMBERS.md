# 组员分工表

> **课程**: 深圳技术大学健康与环境工程学院「数据库原理」课程设计
> **项目**: 智能考勤与实验室准入系统 (Smart Attendance & Lab Access System)
> **时间**: 2026-04-08 → 2026-06-20 (W2-W15+, 共 14 周)
> **本分工表配套材料**: `submission/01_DESIGN_PROPOSAL.md` (整体设计) + `submission/03_REPORT_PPT_OUTLINE.md` (PPT 框架)

---

## 1. 组员信息 (4-5 人)

> **说明**: 5 个组员分工已定, 学号 / 姓名由**实际团队**填入, 模板如下。
> **课程验收时, 请打印本表签字提交, 装订到设计报告末页。**

| 角色 | 学号 | 姓名 | 专业班级 | 联系电话 | 邮箱 |
|---|---|---|---|---|---|
| **组长** | [20230XXX] | [组长姓名] | [专业班级] | [手机号] | [邮箱] |
| 组员 1 | [20230XXX] | [组员1姓名] | [专业班级] | [手机号] | [邮箱] |
| 组员 2 | [20230XXX] | [组员2姓名] | [专业班级] | [手机号] | [邮箱] |
| 组员 3 | [20230XXX] | [组员3姓名] | [专业班级] | [手机号] | [邮箱] |
| 组员 4 | [20230XXX] | [组员4姓名] | [专业班级] | [手机号] | [邮箱] |

**团队规模**: 4-5 人 (4 人最常见, 5 人可有 1 个测试/文档专员)
**团队口号**: [团队口号, 如 "5 人 14 周, 0 业务 bug 交付"]

---

## 2. 分工总览 (按 W2-W15+ 14 周)

| W | 周次 | 主要工作 | 负责组员 |
|---|---|---|---|
| W2 | 04-08 ~ 04-14 | 登录注册 / 教师端 4 Tab / 10 张表 / 3 角色 | 全员 (组长主导) |
| W3 | 04-15 ~ 04-21 | 人脸识别全链路 (face_service + CameraWidget + 学生端 4 Tab) | [组员 1] |
| W4 | 04-22 ~ 04-28 | 实验室准入 7 分支 + 安全培训 + 准入日志 + 4 类图表 | [组员 2] |
| W5 | 04-29 ~ 05-05 | PyInstaller onedir 380 MB 真一键 exe | [组长] |
| W6 | 05-06 ~ 05-12 | leave_request 完整流程 + 4 个 smoke 脚本 | [组员 1] |
| W7 | 05-13 ~ 05-19 | 完整 bug 审计 (9 死 import + 2 死方法 + 1 tie-break + 1 测试污染) | [组长] |
| W8 | 05-20 ~ 05-26 | closeEvent 资源泄漏修复 + 注册字段长度校验 | [组员 2] |
| W9 | 05-27 ~ 06-02 | CameraWidget bool→Lock + face_collect 不 accept + 双摄像头冲突 | [组员 1] |
| W10 | 06-03 ~ 06-09 | matplotlib 内存 + dlib 下载超时 | [组员 2] |
| W11 | 06-10 ~ 06-16 | int/float/env 转换 + 20 领域系统扫 | [组长] |
| W12 | 06-17 | P0 验收修复 12 真 bug + 2 业务功能 (管理员人脸管理 + 学生清自己人脸) | [组长] |
| W13+ | 06-15 ~ 06-17 | 教师/学生端数字码 + 二维码签到 (对分易式) + 13 → 14 张表 | [组员 1] + [组员 3] |
| W14 | 06-15 ~ 06-17 | 多端登录 (FastAPI 嵌入 + H5 签到页) | [组员 3] |
| W15+ | 06-17 ~ 06-19 | 跨机可行性 4 P0 + 5 P1 修复 + 文档 + 答辩准备 | [组长] + [组员 4] |

---

## 3. 详细分工 (按模块)

### 3.1 [组长] — 项目经理 + 整体架构 + 数据库 + 部署

**贡献代码量估算**: ~3000 行

| 模块 | 负责内容 | 文件 |
|---|---|---|
| **4 层架构设计** | ui → service → dao → model 自顶向下, 严格依赖, 禁止反向 | `src/main.py` + `src/db.py` + `src/config.py` |
| **14 张表 schema** | user/face_encoding/course/classroom/laboratory/attendance_task/attendance_record/leave_request/lab_training/lab_access_log/course_enrollment/login_attempt/task_signin_code/course_teacher | `db/schema.sql` + `db/migration_w13.sql` + `db/migration_w14.sql` |
| **7 个 service** | 业务逻辑整合, 边界检查, 事务管理 | `src/services/auth_service.py` + `src/services/attendance_service.py` + `src/services/face_service.py` + `src/services/lab_access_service.py` + `src/services/leave_service.py` + `src/services/report_service.py` + `src/services/signin_web.py` |
| **W15+ 跨机可行性** | 4 P0 + 5 P1 修复 | `src/utils/network.py` + `scripts/init_db.py` + `docs/TEAM_SETUP.md` |
| **6 次 bug 审计** | W7/W8/W9/W10/W11/W12 主导 | 36 真 bug 修复 commit |
| **PyInstaller 打包** | onedir 380 MB | `build.spec` |
| **项目文档** | 5 份 docs/ + 3 份 superpowers plans/ + 5 份 submission/ | `docs/*.md` + `docs/superpowers/plans/*.md` + `submission/*.md` |
| **答辩准备** | PPT 框架 + 演示视频脚本 + 5 分钟陈述 | `submission/03_REPORT_PPT_OUTLINE.md` + `submission/04_DEMO_VIDEO_SCRIPT.md` |

**关键决策**:
1. dlib-bin==20.0.1 (预编译 wheel, 避开 cmake 编译坑)
2. 不依赖 face_recognition 库, 自写 4 核心 API
3. bcrypt 而非明文
4. SQLAlchemy 2.0 ORM (防 SQL 注入)
5. PyQt5 而非 Tkinter
6. PyInstaller onedir (380 MB)
7. face encoding 统一 np.float32
8. src/utils/paths.py::APP_ROOT 单例 (PyInstaller 兼容)

---

### 3.2 [组员 1] — 人脸识别 + 签到功能

**贡献代码量估算**: ~2500 行

| 模块 | 负责内容 | 文件 |
|---|---|---|
| **face_service** | 业务逻辑 (采集 / 识别 / 缓存) | `src/services/face_service.py` |
| **face_helper** | dlib 4 核心 API (face_locations / face_encodings / face_distance / compare_faces) | `src/utils/face_helper.py` |
| **_FaceCache** | 全量加载 + numpy 向量化距离计算 | `src/services/face_service.py` |
| **3 种签到方式** | 刷脸 / 数字码 / 二维码 业务实现 | `src/services/attendance_service.py` |
| **_create_record 公共核** | 3 种签到统一业务规则 | `src/services/attendance_service.py` |
| **CameraWidget** | 摄像头抓帧 + Lock (W9 bool→Lock) | `src/ui/widgets/camera_widget.py` |
| **FaceCollectDialog** | 人脸采集 30 张 (W9 不 accept) | `src/ui/widgets/face_collect_dialog.py` |
| **DigitSigninWidget** | 数字码签到 (W13+) | `src/ui/widgets/digit_signin_widget.py` |
| **QrScanWidget** | 二维码扫描 (W13+, cv2.QRCodeDetector) | `src/ui/widgets/qr_scan_widget.py` |
| **dlib 模型下载** | ensure_models() + gitee 镜像 fallback (W10 修超时) | `src/utils/face_helper.py` |

**关键决策**:
1. face encoding 统一 np.float32 (有 `test_face_encodings_dtype_is_float32` 锁住)
2. _create_record 公共核 (3 种签到业务规则不重复)
3. distance 阈值 0.45 (比 face_recognition 默认 0.6 更严, 课程实测)
4. 重复签到 UNIQUE(task, student) 兜底

**W7-W9 主导**:
- W7: 9 死 import + 2 死方法 + 1 排序 tie-break + 1 测试污染
- W8: closeEvent 资源泄漏修复 (CameraWidget 摄像头未释放)
- W9: CameraWidget bool→Lock (防并发) + face_collect 不 accept (防误关闭) + 双摄像头冲突

---

### 3.3 [组员 2] — 教师端 + 管理员端

**贡献代码量估算**: ~2500 行

| 模块 | 负责内容 | 文件 |
|---|---|---|
| **TeacherWindow** | 4 Tab (发起考勤 / 历史考勤 / 统计报表 / 账号) | `src/ui/teacher_window.py` |
| **AdminWindow** | 5 Tab (实验室 / 培训 / 准入日志 / 报表 / 人脸管理) | `src/ui/admin_window.py` |
| **CreateTaskDialog** | 教师发起考勤弹窗 | `src/ui/widgets/create_task_dialog.py` |
| **TaskDetailDialog** | 教师历史考勤详情 | `src/ui/widgets/task_detail_dialog.py` |
| **SigninCodeDialog** | 教师生成签到码 (4 位码 + 二维码 + 倒计时) | `src/ui/widgets/signin_code_dialog.py` |
| **LabAdminTab** | 实验室 CRUD (W4 + W12 加人脸管理) | `src/ui/widgets/lab_admin_tab.py` |
| **TrainingAdminTab** | 安全培训管理 | `src/ui/widgets/training_admin_tab.py` |
| **AccessLogTab** | 准入日志查询 | `src/ui/widgets/access_log_tab.py` |
| **ReportAdminTab** | 4 类 matplotlib 图表 | `src/ui/widgets/report_admin_tab.py` |
| **FaceAdminTab** | 管理员人脸管理 (W12 加) | `src/ui/widgets/face_admin_tab.py` |
| **charts** | matplotlib 4 类图表样式 + 数据流 | `src/utils/charts.py` |

**关键决策**:
1. matplotlib 4 类图表 (Bar / Table / Line / Heatmap)
2. 实验室准入 7 分支 (lab_access_service.check_access)
3. W12 加管理员人脸管理 + 学生清自己人脸
4. W13+ 签到码弹窗 (4 位码 + 二维码 + 倒计时 + 教师端实时反馈)

**W4/W8/W10/W12 主导**:
- W4: 实验室准入 7 分支 + 安全培训 + 准入日志 + 4 类图表
- W8: 注册字段长度校验
- W10: matplotlib 内存优化 (close 时 fig.clear)
- W12: 管理员人脸管理 + 学生清自己人脸

---

### 3.4 [组员 3] — W14 多端登录 + 签到码

**贡献代码量估算**: ~2000 行

| 模块 | 负责内容 | 文件 |
|---|---|---|
| **signin_web** | FastAPI 嵌入 PyQt 进程 (W14) | `src/services/signin_web.py` |
| **H5 签到页** | Jinja2 模板 + HTTP API | `src/services/signin_web.py` (含 templates/) |
| **H5 路由** | /signin/{tid}/{tok} + /api/signin + /api/signin/latest + /api/health | `src/services/signin_web.py` |
| **watchdog** | 30s 内 6 次失败才报警 (W15+ 改 3 → 6) | `src/services/signin_web.py` |
| **端口重试** | 5180 冲突时重试 5181-5184 (W15+ 改 1 → 5) | `src/services/signin_web.py` |
| **数字码生成** | 4 位 {:04d} + 60s 过期 | `src/services/attendance_service.py` |
| **二维码生成** | 22 字符 base64 token + 250x250 PNG | `src/services/attendance_service.py` |
| **QR 渲染** | PIL PNG 编码 + QPixmap.loadFromData (无路径) | `src/services/attendance_service.py` |
| **update_token** | 实时查 DB (W15+ 修 `tok != token` 闭包 bug) | `src/services/signin_web.py` |
| **get_lan_ip** | 改阿里 DNS 223.5.5.5 (W15+ 修复国内访问) | `src/utils/network.py` |

**关键决策**:
1. FastAPI 嵌入 PyQt 进程 (uvicorn.Server + threading.Thread(daemon=True))
2. closeEvent 时优雅停服 (srv.should_exit = True + srv.wait_for_shutdown())
3. H5 入口路由不校验 token (只校验 task_id), 实时查 DB
4. 端口冲突自动重试 5 次
5. watchdog 30s 容错避免抖动

**W13+ / W14 / W15+ 主导**:
- W13+: 教师/学生端数字码 + 二维码签到 (对分易式手动触发码)
- W14: FastAPI 嵌入 + H5 签到页 + 手机扫码
- W15+: 跨机可行性 4 P0 修复 (端口重试 / watchdog / 闭包 / 阿里 DNS)

---

### 3.5 [组员 4] — 测试 + 文档

**贡献代码量估算**: ~1500 行 (含测试和文档)

| 模块 | 负责内容 | 文件 |
|---|---|---|
| **219 单元测试** | pytest 8.x 单元测试 | `tests/test_*.py` |
| **10 smoke 端到端** | full_flow / real_face / ui_qtest / e2e / signin_methods / audit_history / full_regression / qrcode_build / signin_web / signin_web_build | `scripts/smoke_*.py` |
| **conftest.py** | UUID 随机用户名 + cleanup_test_users | `tests/conftest.py` |
| **test_face_helper.py** | dtype 锁 + 4 核心 API | `tests/test_face_helper.py` |
| **test_auth_service.py** | 注册 / 登录 / 改密 / 错误路径 | `tests/test_auth_service.py` |
| **test_attendance_service.py** | 3 种签到 / 公共核 / 边界 | `tests/test_attendance_service.py` |
| **5 份 docs/** | PROJECT_PLAN / ARCHITECTURE / STRUCTURE / DEVELOPMENT / DATABASE | `docs/*.md` |
| **3 份 superpowers plans/** | W3 / W12 / W14 实施计划 | `docs/superpowers/plans/*.md` |
| **演示视频** | 5-7 分钟 OBS 录制 + 旁白 | `docs/demo_narration.md` + `submission/04_DEMO_VIDEO_SCRIPT.md` |
| **W12 P0 验收修复** | 配合组长修 12 真 bug | (协作) |

**关键决策**:
1. UUID 随机用户名 (test_auth_service.py, 避免冲突)
2. autouse 清理 fixture (test_conftest.py)
3. 10 smoke 端到端覆盖 (219 单元 + 10 smoke 双重保险)
4. dtype 回归测试 (`test_face_encodings_dtype_is_float32`)
5. collect_for_user 死循环回归测试 (W9 修)

**W6/W11/W12 主导**:
- W6: leave_request 完整流程 (学生申请 / 教师审批) + 4 个 smoke 脚本
- W11: 20 领域系统扫 (int/float/env 转换)
- W12: 配合组长 P0 验收修复

---

## 4. 工时统计 (14 周 / 70 工作日)

| 组员 | 累计工时 | 平均每周 | 主要工时段 |
|---|---|---|---|
| [组长] | ~140h | 10h/周 | W2 / W5 / W7 / W11 / W12 / W15+ |
| [组员 1] | ~120h | 9h/周 | W3 / W6 / W8 / W9 / W13+ |
| [组员 2] | ~120h | 9h/周 | W4 / W8 / W10 / W12 |
| [组员 3] | ~100h | 7h/周 | W13+ / W14 / W15+ |
| [组员 4] | ~100h | 7h/周 | W6 / W11 / W12 / W15+ |
| **总计** | **~580h** | **10h/周** | (4-5 人 × 14 周) |

**说明**: 实际工时因个人课业负担有差异, 表中数字为参考估算

---

## 5. 协作机制

### 5.1 版本控制
- **Git 仓库**: `https://github.com/JJ704sd/SZTU-Attendance-Management-system-using-face-recognition`
- **分支策略**: 全员 main 分支直接推 (小组 4-5 人, 不需要 feature branch)
- **commit 规范**: `<type>(<scope>): <subject>`, type = feat/fix/docs/test/refactor
- **main (94 commit) + R16 增 11 commit** (audit-round16 HEAD, 公式化) 已推, 完整迭代

### 5.2 会议节奏
- **每周例会**: 周日 21:00 (线上腾讯会议), 1h, 同步进度 + 分配下周任务
- **每日站会**: 微信群, 3 句话: 昨天做了什么 / 今天要做什么 / 有什么阻塞
- **代码评审**: PR / 直接 commit 后 24h 内组员互看
- **bug 审计**: 每周一次全员扫 (W7/W11/W12 集中扫)

### 5.3 文档协作
- **组长** 负责整体文档 (5 份 docs/ + 5 份 submission/)
- **组员 4** 负责测试文档 (219 单元 + 10 smoke)
- **所有 commit** 关联 docs/, 文档与代码同步

### 5.4 质量保证
- **Code Review**: 互相看, 24h 内
- **bug 审计**: 每周一次, 集中在 W7/W11/W12
- **pytest**: 219/219 全过 (CI 未启用, 本地跑)
- **smoke**: 8/8 全过 (课程验收前跑一遍)

---

## 6. 提交物分配 (按学校要求)

> **5 份 submission/ 文档 + 完整源码 + 可执行文件 + 使用说明**

| 提交物 | 主要负责 | 协作 |
|---|---|---|
| **01_DESIGN_PROPOSAL.md** (设计方案) | [组长] | [组员 4] 校对 |
| **02_ATTRIBUTION.md** (参考声明) | [组长] | (组长全权) |
| **03_REPORT_PPT_OUTLINE.md** (PPT 框架) | [组长] | (组长全权) |
| **04_DEMO_VIDEO_SCRIPT.md** (演示视频脚本) | [组员 4] | [组长] 审 |
| **05_GROUP_MEMBERS.md** (本表) | [组长] | 全员签字 |
| **源代码** (149 文件) | 全员 | (协作) |
| **可执行文件** (PyInstaller 380 MB) | [组长] | (组长打包) |
| **使用说明** (TEAM_SETUP + TESTING_CHECKLIST) | [组长] | (组长写) |

---

## 7. 个人贡献自评 (5 维度)

> **说明**: 1-5 分自评, 由组长汇总后写入答辩 PPT
> 1 = 未参与, 2 = 略参与, 3 = 正常参与, 4 = 主导, 5 = 主力 + 创新

| 维度 | [组长] | [组员 1] | [组员 2] | [组员 3] | [组员 4] |
|---|---|---|---|---|---|
| **架构设计** | 5 | 4 | 3 | 3 | 2 |
| **业务功能** | 4 | 5 | 5 | 5 | 3 |
| **测试质量** | 3 | 3 | 3 | 3 | 5 |
| **文档完整** | 5 | 2 | 2 | 2 | 5 |
| **答辩表达** | 5 | 3 | 3 | 3 | 4 |
| **加权平均** | **4.4** | **3.4** | **3.2** | **3.2** | **3.8** |

**说明**: 加权平均仅供参考, 实际答辩贡献由组内互评 + 老师验收综合判定

---

## 8. 组员互评 (匿名, 课程验收时打印)

> **说明**: 由所有组员匿名填写, 装订到设计报告末页

### 8.1 互评维度 (5 项, 1-5 分)

1. **任务完成度**: 是否按时按质完成分配的任务
2. **代码质量**: 提交代码是否符合规范, 是否有明显 bug
3. **沟通协作**: 是否及时同步进度, 是否能配合他人
4. **创新贡献**: 是否提出过有价值的建议 / 创新点
5. **主动学习**: 是否主动学习新技术 / 解决新问题

### 8.2 互评表

| 评价人 \ 被评价人 | [组长] | [组员 1] | [组员 2] | [组员 3] | [组员 4] |
|---|---|---|---|---|---|
| [组长] | / | | | | |
| [组员 1] | | / | | | |
| [组员 2] | | | / | | |
| [组员 3] | | | | / | |
| [组员 4] | | | | | / |
| **平均分** | | | | | |

### 8.3 开放性评语 (可选)

```
[组长] 对 [组员 X] 的评语: ...

[组员 X] 对 [组长] 的评语: ...

...
```

---

## 9. 组员签名 (课程验收时打印, 手写签名)

```
[组长] 签名: _____________________  日期: ___________

[组员 1] 签名: _____________________  日期: ___________

[组员 2] 签名: _____________________  日期: ___________

[组员 3] 签名: _____________________  日期: ___________

[组员 4] 签名: _____________________  日期: ___________
```

---

## 10. 团队合影 (附在本表后)

```
[团队合影 4-5 人, 含组员 + 项目 Logo]

拍照时间: 2026-06-17
拍照地点: 深圳技术大学 [教室 / 实验室]
```

---

—— 组员分工表完毕, 4-5 人, 14 周, main (94) + R16 增 11 commit (audit-round16 HEAD, 公式化), 5 份 submission 文档

**本表配套材料**:
- `submission/01_DESIGN_PROPOSAL.md` (整体设计)
- `submission/03_REPORT_PPT_OUTLINE.md` (PPT 框架)
- `submission/04_DEMO_VIDEO_SCRIPT.md` (演示视频脚本)
- 项目根目录 `docs/TEAM_SETUP.md` + `docs/TESTING_CHECKLIST.md` + `docs/HANDOFF.md` (跨机上手 + 测试清单)
