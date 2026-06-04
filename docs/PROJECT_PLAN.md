# 项目实现规划

## 1. 项目定位

**场景**：本系统服务于深圳技术大学健康与环境工程学院，覆盖两大本科专业（生物医学工程 / 智能医学工程）下设的 5 个方向（纳米医学技术、生物医学仪器、生物医学检测、智能医疗仪器、智能医疗信息）。

**解决痛点**：
- 学院实训/实验课占比高（生物医学传感与检测、嵌入式系统、医学成像等），传统点名耗时且易代签
- 实验室存在分级安全准入要求（生物、化学、辐射、设备类），人工核验不严
- 出勤数据与实验室使用率数据割裂，难以做教学评估

**与参考项目（Patelrahul4884）的差异化**：

| 维度 | 参考项目 | 本系统 |
|---|---|---|
| UI | Tkinter 简陋 | PyQt5 桌面应用 |
| 识别 | OpenCV LBPH | dlib 128 维向量（自封装核心函数） |
| 存储 | CSV 文件 | MySQL 关系数据库 |
| 角色 | 仅学生 | 学生 / 教师 / 实验室管理员 |
| 场景 | 课堂考勤 | 课堂 + 实验课 + 实验室准入 |
| 报表 | 表格 | matplotlib 可视化 |

## 2. 系统总体架构

采用经典**分层架构 + 业务模块化**，本地部署。

```
┌─────────────────────────────────────────────────────┐
│  表现层 (Presentation)                              │
│  PyQt5 窗口：登录 / 学生端 / 教师端 / 管理员端      │
│  matplotlib 嵌入：出勤率 / 实验室使用率图表         │
├─────────────────────────────────────────────────────┤
│  业务逻辑层 (Business Logic)                        │
│  ┌──────┬──────┬──────┬──────┬──────┐              │
│  │ 认证 │ 人脸 │ 考勤 │ 实验室│ 报表 │              │
│  │ 服务 │ 服务 │ 服务 │ 准入 │ 服务 │              │
│  └──────┴──────┴──────┴──────┴──────┘              │
├─────────────────────────────────────────────────────┤
│  数据访问层 (DAL)   — SQLAlchemy ORM               │
├─────────────────────────────────────────────────────┤
│  数据层 (MySQL 8.0)                                 │
│  + 摄像头 / 图像文件存储 (./dataset/face_images/)  │
└─────────────────────────────────────────────────────┘
```

**部署形态**：单机应用（开发期），后期可拆 client-server（教师端/管理员端可走 Web，这里受工作量约束不做）。

## 3. 技术栈细化（含选型理由）

| 层 | 选型 | 版本 | 理由 |
|---|---|---|---|
| 语言 | Python | 3.9+ | 与参考项目一致，库生态最丰富 |
| UI | PyQt5 | 5.15 | 比 Tkinter 强得多，组员易上手 |
| 人脸检测 | dlib HOG | 20.0.1 (dlib-bin) | 预编译 wheel，避开 cmake 编译 |
| 人脸识别 | dlib ResNet | 20.0.1 (dlib-bin) | 128-D 向量，欧氏距离匹配，比 LBPH 准 |
| 摄像头 | OpenCV | 4.8 | 视频流采集与显示 |
| ORM | SQLAlchemy | 2.0 | 简化 SQL，避免手写拼接 |
| 数据库 | MySQL | 8.0 | 满足课程要求，比 SQLite 演示效果好 |
| 驱动 | PyMySQL | 1.1 | SQLAlchemy MySQL 驱动 |
| 图表 | matplotlib | 3.7 | 出勤率/热力图 |
| 密码 | bcrypt | 4.1 | 密码哈希（不能明文） |
| 打包 | PyInstaller | 6.0 | 生成 .exe（满足"可执行文件"要求） |

**为什么不选 Java/Swing**：dlib 在 Python 下是几行代码，Java 需 JNI 调 OpenCV 或用 SeetaFace6，5 人组下工作量爆炸。

**为什么不依赖 face_recognition**：face_recognition 1.3.0 的 dlib 子依赖在 cp313 上无官方预编译 wheel；本项目自写 4 个核心函数（`face_locations` / `face_encodings` / `face_distance` / `compare_faces`）实现等价 API，依赖最少。

## 4. 模块划分

```
src/
├── main.py                  # 入口
├── config.py                # 配置（DB 连接、阈值、路径）
├── models/                  # SQLAlchemy 模型
│   ├── user.py
│   ├── face.py
│   ├── course.py
│   ├── attendance.py
│   └── lab.py
├── dao/                     # 数据访问层
├── services/                # 业务逻辑
│   ├── auth_service.py
│   ├── face_service.py      # 采集/训练/识别
│   ├── attendance_service.py
│   ├── lab_access_service.py
│   └── report_service.py
├── ui/                      # PyQt5 窗口
│   ├── login_window.py
│   ├── student_window.py
│   ├── teacher_window.py
│   ├── admin_window.py
│   └── widgets/             # 自定义控件
├── utils/
│   ├── camera.py            # 摄像头封装
│   ├── charts.py            # 图表生成
│   └── crypto.py            # 密码哈希
└── assets/                  # 头像、图标
```

**核心模块职责**：

- **face_service**：人脸采集（多角度拍 30 张）、编码入库、实时识别返回 (user_id, confidence)
- **lab_access_service**：根据学生 user_id + 实验室 lab_id 查询安全培训是否有效，决定放行
- **attendance_service**：考勤任务管理、迟到判定、缺勤标记、请假审批
- **report_service**：学生出勤率、班级出勤率、实验室使用率、缺勤预警

## 5. 关键算法选型对比

| 算法 | 准确率 | 速度 | 抗光照 | 库依赖 | 选型 |
|---|---|---|---|---|---|
| OpenCV LBPH（参考项目） | 中 | 快 | 差 | OpenCV | ✗ |
| dlib ResNet（本项目） | 高 | 中 | 中 | dlib-bin | ✓ 主选 |
| ArcFace/InsightFace | 极高 | 慢 | 强 | onnxruntime | △ 备选 |
| MediaPipe Face Mesh | 中 | 极快 | 中 | mediapipe | ✗ 仅检测 |

**主选 dlib-bin 原因**：5 人组能 hold 住，文档丰富，演示效果足够；用 dlib-bin 预编译 wheel 避开 Windows + Python 3.13 上的 cmake 编译坑。
**距离阈值 0.45** 是工程经验值，可演示时现场调参演示效果（加分项）。

## 6. 风险点与备选方案

| 风险 | 影响 | 备选 |
|---|---|---|
| dlib 编译失败（Windows 常见） | 高 | 改用预编译 wheel `pip install dlib-bin` |
| 摄像头权限/无摄像头 | 中 | 提供图片上传签到作为兜底 |
| dlib 误识 | 中 | 提高阈值到 0.4 + 二次确认弹窗 |
| MySQL 服务起不来 | 中 | 一键切到 SQLite（SQLAlchemy 改一行 URL） |
| 5 人协作 git 冲突 | 低 | 每人独立 feature 分支 + 每日整合 |

详细 ER 图和 DDL 见 [docs/DATABASE.md](DATABASE.md)。
业务流程见 [docs/WORKFLOWS.md](WORKFLOWS.md)。
分工与时间线见 [docs/TEAM_AND_TIMELINE.md](TEAM_AND_TIMELINE.md)。
