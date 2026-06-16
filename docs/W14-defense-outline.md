# W14 答辩 PPT 大纲（智能考勤与实验室准入系统）

> **课程**: 数据库原理 课程设计  
> **截止**: 2026-06-20  
> **作者**: 项目组  
> **配套文档**: `docs/ARCHITECTURE.md` / `docs/SIGNIN_METHODS.md` / `docs/superpowers/plans/2026-06-07-W12-p0-fixes-and-deliverables.md`  
> **演示视频**: 见 `docs/DEMO_RECORDING.md` / `docs/RECORD_QUICKSTART.md`  

---

## 全局风格建议

- 主色：天蓝 #3B8DD8（与 `src/ui/styles.py::COLOR_PRIMARY` 一致）
- 辅色：成功 #2EA66C / 警告 #E0A92E / 危险 #D24A4A
- 字体：思源黑体 / 微软雅黑；正文 22pt、代码 16pt
- 节奏：技术深度的页面（P4-P5、P9、P13）多放图少放字

---

## P1. 封面页
**标题**: 智能考勤与实验室准入系统  
**副标题**: 基于 PyQt5 + MySQL + dlib 的桌面应用  
**信息条**: 深圳技术大学 · 健康与环境工程学院 · 数据库原理课程设计 · 2026.06  
**讲者**: 项目组（按真实分工填）  
**页脚**: 截止 2026-06-20

**截图需求**: 无（封面）

---

## P2. 项目背景
**要点**:
- 高校实验室管理痛点：纸质签到慢、刷卡易代刷、培训记录散落在 Excel
- 高校课堂考勤痛点：老师逐个点名 + 学委代签
- 安全合规要求：实验室准入必须配套安全培训记录

**讲法**: 用"上课点名 5 分钟 / 学生挤在讲台刷卡"等场景图开场

**截图需求**: 痛点配图（可手绘或 stock）

---

## P3. 系统目标
**要点**:
- **3 角色一体化**：学生刷脸签到 / 教师发起考勤 / 管理员管实验室
- **考勤 + 准入双场景**：考勤用刷脸 / 数字码 / 二维码；准入要过培训关
- **数据持久化**：13 张表 / utf8mb4 / bcrypt 密码哈希 / SQLAlchemy ORM
- **桌面端一键 exe**：PyInstaller onedir 打包 ≈396 MB（带 W14 FastAPI 嵌入）

**截图需求**: 三大窗口总览拼图（`docs/ARCHITECTURE.md` 里有布局参考）

---

## P4. 系统架构（4 层）
**要点**:
- `ui/` → PyQt5 窗口（login/register/student/teacher/admin + 11 widget）
- `services/` → 业务逻辑（auth/attendance/face/lab_access/leave/report/signin_web 7 个）
- `dao/` → SQLAlchemy 数据访问（13 个）
- `models/` → ORM 模型（13 张表）
- `utils/` → crypto/face_helper/network/charts/paths

**讲法**: 自顶向下依赖图（严格禁止反向），service 用 `session_scope()` 自动 commit

**截图需求**: 4 层架构图（手绘 + Mermaid 渲染）

---

## P5. 数据库设计（13 表）
**要点**:
- 核心表：user / course / classroom / attendance_task / attendance_record
- W6: leave_request（学生请假流程）
- W13+: task_signin_code（数字码 / 二维码 token + TTL）
- 准入：lab / lab_training / lab_access_log
- 安全：login_attempt（失败锁定计数）
- W12: face_encoding（管理员端人脸管理）

**讲法**: E-R 图 → 重点表字段示例 → bcrypt 密码哈希 / utf8mb4 / 索引设计

**截图需求**: E-R 图 + 几张关键表的 DDL 截图（`db/schema.sql` + `db/migration_w13.sql`）

---

## P6. 三角色登录 Demo（截图占位）
**要点**:
- `src/ui/login_window.py::_open_role_window()` 按 role 路由
- 三窗口都换 W12 设计稿（天空蓝主题 / design tokens）

**截图需求**（从 `dataset/screenshots/` 或实拍拿）:
- [ ] login_window 主界面
- [ ] student_window 4 tab 全景
- [ ] teacher_window 4 tab 全景
- [ ] admin_window 5 tab 全景

---

## P7. 教师发起考勤
**要点**:
- 选课程 → 选教室 → 选起止时间 → 创建 task
- 三种签到方式按钮：
  - 「📷 刷脸签到」→ 摄像头 Widget
  - 「🔢 数字码签到」→ 4 位数字（对分易式）
  - 「📱 二维码签到」→ **W14 新增**，弹窗生成 URL 二维码

**截图需求**:
- [ ] 「发起考勤」Tab 表单截图
- [ ] 三按钮 UI 截图

---

## P8. 三种签到方式对比
**要点**（详见 `docs/SIGNIN_METHODS.md`）:
| 方式 | 触发 | 学生端入口 | 适用场景 |
|---|---|---|---|
| 刷脸 | 教师现场开摄像头 | `FaceSigninTab` | 教室有摄像头、教师机位置固定 |
| 数字码 | 教师点「生成 4 位码」 | 学生输入数字 | 没摄像头、防止代签 |
| 二维码（URL） | 教师点「二维码」 | **手机浏览器**扫码 | 学生没带电脑（W14 多端登录卖点） |

**截图需求**:
- [ ] 刷脸识别中 + 成功提示
- [ ] 数字码 4 位 + 输入框
- [ ] 二维码弹窗 + URL 显示

---

## P9. ⭐ W14 多端登录签到（重点讲）
**要点**（这是答辩差异化亮点）:
- 业务背景：传统二维码签到 = 裸 token，学生必须用**教师那台电脑**的摄像头扫
- W14 方案：二维码内容 = 完整 URL（`http://lan_ip:5180/signin/<task>/<token>`），学生手机浏览器扫码后渲染 H5 表单
- 架构：FastAPI 嵌入到 PyQt 进程，`uvicorn.Server` 跑在 `threading.Thread(daemon=True)` 内，closeEvent 同步 stop
- 实时反馈：教师端 QTimer 2 秒 polling `GET /api/signin/status`，签到列表顶部追加
- 演示流程：教师点按钮 → 屏幕显示二维码 + URL → 学生手机扫码 → 输入学号密码 → 教师端立刻「✓ 张三 已签到」

**截图需求**:
- [ ] 教师端二维码弹窗（带 URL 文本）
- [ ] 手机浏览器扫码后 H5 表单（手绘或截图）
- [ ] 教师端实时签到列表

**讲法**: 时序图（参考 `docs/superpowers/plans/2026-06-16-W14-multidevice-signin-design.md` 第 3 节）

---

## P10. 实验室准入 + 安全培训
**要点**（W4 完整 7 分支逻辑）:
- 准入规则 = 培训类型匹配 + 分数阈值 + 安全等级
- 培训类型（设备/化学/生物...）× 实验室类型匹配
- 7 分支 demo：
  - 非学生 → 直接放行
  - 有培训且分数够 → 放行
  - 无培训 → 拒绝
  - 培训过期 → 拒绝
  - 培训类型不匹配 → 拒绝
  - 安全等级不足 → 拒绝
  - 用户/实验室不存在 → 拒绝

**截图需求**:
- [ ] 实验室 CRUD Tab
- [ ] 安全培训 Tab
- [ ] 准入日志 Tab
- [ ] 7 分支流程图

---

## P11. 数据报表 + 统计
**要点**:
- `report_service` 出 4 类 matplotlib 图表（出勤率/趋势/缺勤警告/培训完成率）
- 同步 `src/ui/styles.py` 主题色（跨层依赖，详见 CLAUDE.md 决策表）
- 教师端「统计报表」Tab 出图（不存文件，纯内存 `plt.close()` 防泄漏）

**截图需求**:
- [ ] 出勤率柱状图
- [ ] 趋势折线图
- [ ] 缺勤警告列表

---

## P12. 请假流程（W6）
**要点**:
- 学生申请 → 教师审批 → 自动写入对应 task 的 attendance_record
- `leave_request` 表 + `leave_service`
- 边界：closed task 不能补请假

**截图需求**:
- [ ] 学生「我的请假」Tab
- [ ] 教师审批 Tab

---

## P13. 关键技术决策（答辩高频追问点）
| 决策 | 原因 |
|---|---|
| **dlib-bin==20.0.1** 预编译 wheel | Python 3.13 + Windows 上 cmake 编译 dlib 太坑 |
| **不依赖 face_recognition** | cp313 上无 wheel；自写 4 API (`face_locations / encodings / distance / compare_faces`) |
| **bcrypt 而非明文** | 课程硬要求 |
| **SQLAlchemy 2.0 ORM** | 防 SQL 注入 + 跨库可移植（演示可切 SQLite） |
| **PyQt5 而非 Tkinter** | 控件丰富（4 窗口 + 大量表格表单） |
| **face encoding 统一 float32** | 与 dlib 内部一致；有 `test_face_encodings_dtype_is_float32` 锁住 |
| **FastAPI 嵌入 PyQt** | 桌面端 + HTTP 服务同进程统一生命周期；避免端口/进程管理分裂 |
| **二维码内容 = URL** | 学生用手机浏览器扫码，区别于"必须用电脑摄像头"的旧方案 |

**讲法**: 这些决策的"为什么"要能讲 2-3 分钟，是答辩被追问最多的

---

## P14. 测试矩阵
**要点**:
- 单元测试：**179/179** 全过，~55s 4 warning
- Smoke 脚本：**9 个** 全过
  - `smoke_full_flow.py` 9 步业务流
  - `smoke_signin_web.py` 9 步 W14 全链路
  - `smoke_qrcode_build.py` + `smoke_signin_web_build.py` 防 hiddenimports 漏配
  - `smoke_real_face.py` / `smoke_signin_methods.py` / `smoke_audit_history.py` / `smoke_ui_qtest.py` / `smoke_e2e.py`
- PyInstaller onedir exe：`dist/attendance-system/` 总 **396 MB**（含 W14 FastAPI 嵌入）

**截图需求**:
- [ ] pytest 终端 179 passed 截图
- [ ] smoke_signin_web 9 步全过截图
- [ ] dist/attendance-system/ 文件夹大小截图

---

## P15. 总结 + 致谢
**要点**:
- 完成情况：W2-W14 全 13 周迭代，覆盖登录/考勤/实验室/请假/统计/H5 签到
- 数据规模：13 张表 + 179 单元测试 + 9 smoke 脚本 + 396 MB exe
- 可改进点：实验室 IoT 集成 / 微信扫码（需企业认证）
- 致谢：指导老师 + 团队成员

**讲法**: 控制在 1 分钟内，留时间给提问

**截图需求**: 团队合照（可选）

---

## 附录：PPT 文件制作流程（不录视频，按用户要求）

1. 在 PowerPoint 新建空白演示文稿，**16:9** 版式
2. 按上述 P1-P15 顺序插入 15 张幻灯片
3. 主题色：设计 → 颜色 → 自定义 → 主色 #3B8DD8
4. 截图素材：直接复用 `dataset/screenshots/` 或 W14 演示时录制
5. 时长：建议 12-15 分钟（每页平均 1 分钟）
6. 导出：PDF 备份（`文件 → 导出 → 创建 PDF`）

---

## 答辩话术提示

- **开头 30 秒**: "我们做的不是一个简单的考勤系统，而是把考勤 + 实验室准入 + 安全培训三个场景整合到一起的桌面应用"
- **W14 重点**: "W14 我们加了多端登录 — 学生不用电脑也能签到，这是答辩的差异化亮点"
- **结尾**: "我们完整跑了 13 周迭代，179 单元测试 + 9 个 smoke 全过，欢迎老师提问"

---

> **下一步**: 把此大纲复制到 PowerPoint → 按「截图需求」清单补图 → 导出 PDF