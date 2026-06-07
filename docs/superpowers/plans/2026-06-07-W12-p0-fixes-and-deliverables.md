# W12 实施计划：P0 验收修复 + 课程交付收口

**编写时间**: 2026-06-07 14:58
**截止**: 2026-06-20（课程大截止，剩 13 天）
**风格**: 跟 W3/W4/W5/W6 同款 writing-plans，每个 phase 独立可验收

## 现状摸底（06-07 14:58）

W11 收口后 P0 验收发现一批 W11 漏掉的真 bug，**W12 全部修了**（commit `78e344a` 已推 GitHub）：

| 类别 | 修了什么 | 文件 |
|---|---|---|
| 摄像头启动 | MSMF 句柄冲突 + retry | `camera_widget.py` |
| 摄像头容错 | 截屏/DWM 重合成 try/except | 同上 |
| dialog 黑屏 | 复用主窗 cap 不双开 | `face_collect_dialog.py` |
| dialog 预览静态 | 砍 dialog timer，主窗 timer 渲染同步显示 | 同上 |
| 30 张只采 6 张 | worker 独占 _lock | 同上 |
| closeEvent 闪退 | sip.isdeleted + try/except | 同上 |
| 色彩 3 模式错 | 统一走 cv2.cvtColor | `camera_widget.py` |
| UI 误导 | 砍色彩模式按钮，改"🎨 颜色 OK"绿标签 | `student_window.py` |
| 管理员删人脸 | 新 Tab 5 "👤 人脸管理" | `face_admin_tab.py` + `admin_window.py` |
| 学生自己管理 | Tab 1 加"🗑 清空我的人脸" | `student_window.py` |
| 演示数据 | `seed_demo_data.py` (course + 任务 #82) | 新增 |
| 测试残留 | `cleanup_test_users.py` (清 190 条) | 新增 |
| 文案 | 30 张是单轮目标 | `student_window.py` |

**测试**: `tests/test_camera_widget.py` 17 项 + `tests/test_face_admin_tab.py` 8 项 = **106/106 全过**

---

## Phase 1: 课程报告 PDF —— 0.5-1 天（截止 6-15）

**15 页 PDF**，从 `docs/` 已有内容拼。

**结构**（参考清华大学《数据库原理》课程设计通用模板）：
```
1. 封面 (200字) — 项目名 / 组员 / 指导老师 / 日期
2. 目录 (1页)
3. 项目概述 (1页) — 需求 / 目标 / 创新点
4. 需求分析 (1.5页) — 用例图 + E-R 图 (从 docs/DATABASE.md 拿)
5. 总体设计 (2页) — 4 层架构 (从 docs/ARCHITECTURE.md 拿) + 业务流程图
6. 详细设计 (3页) — 10 张表 schema (从 db/schema.sql 拿) + service/dao 关键类图
7. 编码实现 (2.5页) — 4 段: 注册/登录/刷脸签到/考勤报表 (贴 4 张 GUI 截图)
8. 测试 (2页) — 106/106 单元测试 + 4 个 smoke (从 docs/SMOKE_TESTS.md 拿) + 性能数据
9. 部署 (1页) — PyInstaller 380MB onedir + 启动脚本 (从 docs/PACKAGING.md 拿)
10. 总结 (0.5页) — 难点 + 心得 + 改进方向
11. 参考文献 (0.5页) — PyQt5 / dlib / SQLAlchemy / face_recognition / bcrypt / etc.
```

**自动化**（节约时间）：
```python
# scripts/build_report.py
# - 从 docs/ARCHITECTURE.md / DATABASE.md / SMOKE_TESTS.md / PACKAGING.md 抽章节
# - 嵌 4 张 GUI 截图 (MANUAL_E2E.md 那 5 步截的图)
# - 渲染成 PDF (用 reportlab 或 weasyprint)
# 输出: docs/REPORT.pdf
```

**验收**: PDF 15 页 + 4 张截图 + 106 测试数据

---

## Phase 2: 答辩 PPT —— 0.5 天（截止 6-17）

**15-20 页 PPT**，摘报告精华。

**结构**:
```
1. 封面 (1页)
2. 项目背景与目标 (1页) — 智慧校园 / 人脸识别考勤
3. 需求分析 (2页) — 3 角色 + 用例
4. 架构设计 (2页) — 4 层架构 + 业务流程
5. 数据库设计 (2页) — E-R 图 + 10 张表
6. 关键实现 (4页) — 4 段配 4 张 GUI 截图
   - 注册人脸 (弹采集 dialog 截图)
   - 刷脸签到 (状态变绿截图)
   - 教师发考勤 (弹 create_task dialog 截图)
   - 报表 (matplotlib 图表截图)
7. 测试 (1页) — 106 测试 + 4 smoke
8. 部署与运行 (1页) — PyInstaller 380MB
9. 难点与创新 (1页) — W11 + W12 修了 44 个 bug
10. 总结与展望 (1页)
```

**风格**（用全局深藏青色 `#1E3A5F` + 主按钮蓝 `#2563EB`，跟 `src/ui/styles.py` 一致）

**验收**: PPT 15-20 页 + 4 张 GUI 截图

---

## Phase 3: 演示视频 —— 1 小时（截止 6-18）

**3-5 分钟录屏**（Win+G Xbox Game Bar 或 OBS）

**脚本**（已有 GUI 截图 + 流程）：
```
0:00-0:30   启动 GUI + 登录窗展示
0:30-1:30   学生注册 (login → register → 录脸 → 30 张)
1:30-2:30   教师登录 + 创建考勤任务 (course BME201 + 教室 A101)
2:30-3:15   学生刷脸签到 (Task 2 选 → 摄像头 → 签到成功)
3:15-3:45   教师查看签到详情 (历史考勤 → 详情 → ✅ 出勤)
3:45-4:15   管理员端 (Tab 5 人脸管理 → 删 demo_student)
4:15-4:30   总结页 (项目介绍 / 技术栈 / 106 测试)
```

**工具**: Win+G（省事）或 OBS / Bandicam
**输出**: mp4 1920x1080
**加字幕**: 用剪映 / Pr 加解说字幕

**验收**: 4-5 分钟 mp4 + 4 段截屏

---

## Phase 4: 个人报告 —— 1 小时（截止 6-19）

**每人一份 PDF**（N 份 = 组员数）

**结构**（清华通用模板）:
```
1. 个人分工 (300字) — git log --author="你的名字" 翻提交
2. 负责模块说明 (1页) — 从 ARCHITECTURE.md 摘你写的部分
3. 关键技术细节 (2页) — 你遇到的真问题 + 解决 (从 W7-W12 修的 44 个 bug 里挑你负责的)
4. 遇到的问题 + 解决 (1.5页) — 3-5 个具体场景
5. 个人收获与反思 (1页)
6. 后续改进建议 (0.5页)
```

**素材**（我能给）:
- `git log --author="你的名字"` 拉你的提交
- `src/` 里你写的模块清单
- W7-W12 修的 bug 里你负责的（看 commit 作者）

**验收**: N 份 PDF，每份 5-7 页

---

## Phase 5: 参考文献清单 —— 10 分钟

`docs/references.txt`，每行一条：

```
[1] PyQt5 5.15.11. Riverbank Computing, 2024. https://www.riverbankcomputing.com/software/pyqt5
[2] dlib-bin 20.0.1. Davis E. King, 2024. https://github.com/jloh02/dlib/releases
[3] SQLAlchemy 2.0.43. Mike Bayer, 2024. https://www.sqlalchemy.org/
[4] face_recognition 1.3.0. Adam Geitgey, 2024. https://github.com/ageitgey/face_recognition
[5] bcrypt 5.0.0. Niels Provos, 2024. https://github.com/pyca/bcrypt
[6] OpenCV 4.13.0.92. Intel, 2024. https://opencv.org/
[7] MySQL 8.0. Oracle, 2024. https://www.mysql.com/
[8] PyInstaller 6.20. Hartmut Goebel, 2024. https://pyinstaller.org/
[9] matplotlib 3.10.9. Hunter et al., 2024. https://matplotlib.org/
[10] numpy 2.3.5. Harris et al., 2024. https://numpy.org/
```

**验收**: 10+ 条，覆盖所有 import 的包

---

## Phase 6: 提交物打包 —— 10 分钟（截止 6-20）

```bash
# scripts/build_submission.py
# 输出: submission_2024001.zip (组长学号)
# 包含:
#   src/                   # 项目代码
#   dist/attendance-system/  # 打包后 380MB
#   README.md
#   docs/REPORT.pdf        # 课程报告
#   docs/PRESENTATION.pptx  # 答辩 PPT
#   docs/demo.mp4           # 演示视频
#   docs/references.txt
#   docs/personal/*.pdf     # N 份个人报告
#   requirements.txt
```

**验收**: 1 个 zip + sha256 校验

---

## 时间线

| 截止 | 工作 | 工作量 |
|---|---|---|
| 6-15 | 课程报告 PDF (Phase 1) | 0.5-1 天 |
| 6-17 | 答辩 PPT (Phase 2) | 0.5 天 |
| 6-18 | 演示视频 (Phase 3) | 1 小时 |
| 6-19 | 个人报告 (Phase 4) | 1 小时 |
| 6-19 | 参考文献 (Phase 5) | 10 分钟 |
| 6-20 | 提交物打包 (Phase 6) | 10 分钟 |

**总工作量**: 半天报告 + 半天 PPT + 1 小时视频 + 1 小时个人报告 = **2-3 天**

---

## 验收总览（6-20 截止前）

```
✅ Phase 1 课程报告 PDF (15 页 + 4 张截图)
✅ Phase 2 答辩 PPT (15-20 页)
✅ Phase 3 演示视频 (3-5 分钟 mp4)
✅ Phase 4 个人报告 (N 份 PDF)
✅ Phase 5 参考文献 (10+ 条)
✅ Phase 6 提交物 zip (含 380MB dist/)
+ 106/106 测试 + W12 修复全保留
```

---

## 不在范围 (W11 接受风险)

- N > 1000 性能 (项目约束 N<1000)
- dlib C++ race
- Linux/macOS 跨平台
- 商业级 dlib 替代 (InsightFace/ArcFace)
- i18n 化 (错误信息 hardcode 中文)
- pytest fixture 重构
- 日志脱敏
- 慢查询监控
- admin_window 4 Tab 懒加载

—— 课程要的不是 production-ready, 是**能跑 + 能演示 + 文档齐**。
