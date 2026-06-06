# TODO / 待办 / 已知风险

> W7-W11 四轮审计 (36 领域) 后的待办清单.
> 包含: (1) 还没扫的领域 (2) 项目约束接受的已知风险 (3) 真正需要做的后续工作.

最后更新: 2026-06-06 (W11 收口)

## 1. 还没扫的领域 (代码扫描覆盖不到)

| # | 领域 | 为什么扫不到 | 建议 |
|---|---|---|---|
| A | **真实 GUI 端到端** (学生真拍照 → 真识别 → 真签到) | 需真人 + 摄像头 + 灯光 | 老师验收时**自己跑一次** dev 模式 `python -m src.main` |
| B | **演示 UX 细节** (字体、对齐、动画、错误文案是否友好) | 自动化只能查语法 | 老师看演示视频 + 学生跑一次 |
| C | **N > 1000 性能** (report_service 全表扫) | 项目约束 N<1000 | 课程不要求, 但生产前要换 Redis / 索引 |
| D | **dlib C++ 库内部 race** | dlib 自身不线程安全 | CLAUDE.md 之前承认 N<1000 + GIL 接受 |
| E | **MySQL 索引选择性 / 慢查询日志** | 需真实大表数据 | 课程不要求 |
| F | **跨平台 (Linux/macOS)** | 当前只在 Windows 测试 | spec 文件按需扩展, CLAUDE.md 已注 "当前 spec 只 Windows" |
| G | **国际字符 (emoji / CJK 路径 / 特殊文件名)** | 项目内都是英文 + ASCII | 真用户使用时大概率 OK |
| H | **PyQt5 主题适配 (Win10/Win11 风格差异)** | Fusion 风格已统一 | 验收时看是否一致 |
| I | **dlib 模型下载失败回退** (断网) | smoke 已验有 models 场景 | 用户首次启动断网时手动下 .dat 指引 (见 PACKAGING.md) |
| J | **dlib 编码失败回退** (face_locations 返空) | 已 fallback 提示 | 验收时观察 |

## 2. 项目约束接受的已知风险 (有意识地不改)

| # | 风险 | 原因 | 缓解 |
|---|---|---|---|
| 1 | `_FaceCache` 单例 dict 不是线程安全 | CPython GIL 下基本安全, N<1000 | 生产前换 Redis |
| 2 | `report_service` 4 个方法全表扫 attendance_record | N<1000 接受 | 加 LIMIT / 索引 |
| 3 | `FaceEncodingDao.set_primary` 2 次 UPDATE | 短暂状态不一致 (W3 接受) | 改 transaction 包裹 |
| 4 | `sign_in_by_face` mock 距离 0.30 验证业务 | GUI 端真脸验证 | 老师验收实测 |
| 5 | `src/assets/` 目录未建 + `Config.ASSETS_DIR` 死代码 | W5 阶段占位 | 后续扩展用 |
| 6 | `face_collect_dialog` 启动后**自动启动摄像头** (`_init_ui` 调 start(0)) | 设计如此 (让学生预览) | 验收时观察, 不要在没摄像头的机器跑 |
| 7 | `closeEvent` `wait(3000)` 等 worker 退出 | 3s 上限, 极端 dlib 卡死会超时 | 正常 OK |
| 8 | `LabAccessLogDao.log_attempt` 不记录 face_image 路径 (总是 None) | UI 暂未实装 | 后续刷脸采集时实装 |
| 9 | `attendancerecord` 删 user 时不级联 (RESTRICT) | 默认安全 | 测试 fixture 倒序删 |
| 10 | `login` 失败不区分 "用户不存在" / "密码错" | 防止枚举攻击 | 设计如此 |

## 3. 真正需要做的后续工作 (W6+ 计划)

### 3.1 课程大作业交付 (课程要求)

| # | 工作 | 工作量 | 备注 |
|---|---|---|---|
| 1 | 课程报告 PDF (15 页) | 半天 | 含架构图/ER图/业务流程/测试报告/打包指南 |
| 2 | 答辩 PPT (15-20 页) | 半天 | 摘报告精华, 加 demo 视频截图 |
| 3 | 演示视频 (3-5 分钟) | 1 小时 | 录屏: 注册 → 登录 → 学生刷脸 → 教师发考勤 → 报表 |
| 4 | 参考文献清单 .txt | 10 分钟 | 引用 PyQt5 / dlib / SQLAlchemy / face_recognition / bcrypt 等 |
| 5 | 个人报告 .pdf (每人) | 1 小时 | 模块分工 + 个人总结 |
| 6 | 提交物打包 .zip (组长学号) | 10 分钟 | src/ + dist/ + README + 报告 + PPT + 视频 + requirements.txt |

### 3.2 可选优化 (你之前说不动 / 不急)

| # | 优化 | 工作量 | 备注 |
|---|---|---|---|
| 1 | admin_window 4 Tab 懒加载 | 1-2 小时 | 当前 4 Tab `__init__` 立即查 DB + 渲染图表, 改懒加载 |
| 2 | 错误信息 i18n 化 | 半天 | 当前中文 hardcode, 抽常量 |
| 3 | pytest fixture 重构 (减少 cleanup 重复) | 1 小时 | conftest.py 加 session 级 fixture |
| 4 | 加入日志脱敏 (用户名/邮箱) | 30 分钟 | `log.info(f"用户 {username} 登录")` 已不算敏感, 但如加密码 / 身份证需脱敏 |
| 5 | 加入性能监控 (慢查询日志) | 1 小时 | SQLAlchemy events 钩子 |

### 3.3 真不建议做的 (P3 留档)

- W5 Mac/Linux 打包 (课程不要)
- 真实业务项目化 (加 Web/移动端)
- 商业级 dlib 替代 (InsightFace/ArcFace)

## 4. 项目当前最终状态 (W11 收口)

```
W7-W11 累计修了 32 项:
- 11 死 import + 2 死方法
- 1 排序 bug (MySQL 同秒时间戳 tie-break)
- 1 测试污染 (autouse fixture purge smk_ student)
- 1 closeEvent 资源泄漏 (3 主窗口)
- 1 注册字段长度校验 (5 字段)
- 3 UI 真 bug (CameraWidget bool lock / face_collect 不 accept / 双摄像头冲突)
- 2 dlib / matplotlib 资源 (figure 内存 / dlib 下载超时)
- 1 log/print 不一致
- 7 int/float/env 转换 try/except
- + 死注释清理 + 项目整理 (删 3 老文档 + reference/ + smoke_face.py)

测试: 82/82 稳态
Smoke: 4 个 (full_flow / real_face / ui_qtest / e2e) 全过
PyInstaller: 380 MB onedir, 双击 exe 起
GitHub: 22 commit 推上 (W2 → W11)
```

## 5. 给下一位接手者的话

1. **新功能先看 `docs/ARCHITECTURE.md`** (4 层依赖) + **`docs/DATABASE.md`** (12 张表)
2. **新测试先看 `docs/SMOKE_TESTS.md`** (4 smoke 怎么跑 + 验收点)
3. **打包先看 `docs/PACKAGING.md`** + `build.spec`
4. **真要看代码** 从 `src/main.py` 入口, 跟 `src/services/` 业务逻辑
5. **遇到真 bug** 在这里加一行, 不要口头说, 写下来

---

**老实说**: 我**真**不知道还有没有 bug. 前 4 次说"差不多了"被你抓到 32 个. 现在列的"未扫领域"是**实际跑代码扫不到**的 (真人/真摄像头/真用户/真生产). 课程验收前**自己跑一次 dev 模式**比再让我扫更有效.
