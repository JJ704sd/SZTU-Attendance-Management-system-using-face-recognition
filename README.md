# 智能考勤与实验室准入系统

> 深圳技术大学 · 健康与环境工程学院 · 数据库原理课程设计
> 题目：考勤系统（加分项：人脸识别自动考勤）

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)](https://pypi.org/project/PyQt5/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange)](https://www.mysql.com/)
[![dlib-bin](https://img.shields.io/badge/dlib--bin-20.0.1-yellow)](https://pypi.org/project/dlib-bin/)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple)](LICENSE)

## 项目简介

服务于深圳技术大学健康与环境工程学院两大本科专业（生物医学工程 / 智能医学工程）下设的 5 个方向，覆盖：

- 📚 **课堂/实验课考勤**（教师发起 → 学生刷脸签到 → 自动统计出勤/迟到/缺勤/请假）
- 🔒 **实验室分级安全准入**（刷脸 + 安全培训核验 → 自动判定放行/拒绝）
- 📊 **考勤与实验室使用率报表**（matplotlib 可视化）

## 差异化于参考项目

| 维度 | 参考项目（Patelrahul4884） | 本系统 |
|---|---|---|
| UI | Tkinter 简陋 | PyQt5 桌面应用（Fusion 风格） |
| 识别 | OpenCV LBPH | dlib 128-D ResNet 向量 + 欧氏距离 |
| 存储 | CSV 文件 | MySQL 8.0 + SQLAlchemy 2.0 ORM |
| 角色 | 仅学生 | 学生 / 教师 / 实验室管理员 |
| 场景 | 单一课堂考勤 | 课堂 + 实验课 + 实验室准入 |
| 报表 | 表格 | matplotlib 可视化 |
| 架构 | 单文件脚本 | 分层（UI / Service / DAO / Model） |
| 密码 | 明文 | bcrypt 哈希 |

## 文档导航

| 路径 | 内容 | 读者 |
|---|---|---|
| [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) | 项目实现规划（架构、技术栈、模块、风险） | 所有人 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 分层架构、模块依赖、关键数据流 | 后端开发 |
| [docs/STRUCTURE.md](docs/STRUCTURE.md) | 仓库目录树总览 | 新成员 |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 30 分钟上手指南 + 调试技巧 | 开发者 |
| [docs/DATABASE.md](docs/DATABASE.md) | ER 图 + 10 张表设计说明 | 后端 / DBA |
| [docs/WORKFLOWS.md](docs/WORKFLOWS.md) | 三大典型业务流程 | 产品 / 测试 |
| [docs/TEAM_AND_TIMELINE.md](docs/TEAM_AND_TIMELINE.md) | 5 人分工 + 6 周时间线 | 团队负责人 |
| [db/schema.sql](db/schema.sql) | 数据库完整 DDL（可直接执行） | DBA |
| [reference/patelrahul4884/](reference/patelrahul4884/) | 原项目参考实现（仅供对照） | 写报告时引用 |
| [QUICKSTART.md](QUICKSTART.md) | 5 分钟跑起来 | 想看效果的人 |

## 技术栈

| 层 | 选型 | 版本 | 备注 |
|---|---|---|---|
| 语言 | Python | 3.11+ | 已在 3.13 验证 |
| UI | PyQt5 | 5.15 | Fusion 风格 |
| 人脸检测 | dlib HOG | 20.0.1 (dlib-bin) | cp313 预编译 wheel，避开 cmake 编译 |
| 人脸识别 | dlib ResNet | 20.0.1 (dlib-bin) | 128 维向量，欧氏距离 |
| 摄像头 | OpenCV | 4.13 | 视频流采集与显示 |
| ORM | SQLAlchemy | 2.0 | 防 SQL 注入 + 跨数据库可移植 |
| 数据库 | MySQL | 8.0 | utf8mb4 字符集 |
| 驱动 | PyMySQL | 1.1 | SQLAlchemy MySQL 驱动 |
| 图表 | matplotlib | 3.8 | 出勤率/热力图 |
| 密码 | bcrypt | 5.0 | 加盐慢哈希 |
| 测试 | pytest | 8.x | service / util 全覆盖 |

**为什么不依赖 face_recognition**：face_recognition 1.3.0 的 dlib 子依赖在 cp313 上无官方预编译 wheel；本项目自写 4 个核心函数（`face_locations` / `face_encodings` / `face_distance` / `compare_faces`）实现等价 API，依赖最少。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化数据库（确保 .env 已配置 DB_PASSWORD）
python scripts/init_db.py

# 3. 启动应用
python -m src.main
```

登录后自动下载 dlib 模型（首次约 120 MB，已下则跳过）。

## 测试账号

| 用户名 | 密码 | 角色 | 备注 |
|---|---|---|---|
| `test001` | `123456` | 学生 | 已注册，方向：生物医学仪器 |
| `teacher01` | `123456` | 教师 | 已注册，教 BME201 |

> 实际可用账号以你本地数据库为准；可运行 `python -m pytest tests/test_auth_service.py` 自动创建测试账号。

## 测试

```bash
# 全量测试
pytest tests/ -v

# 单独跑
pytest tests/test_auth_service.py -v
pytest tests/test_face_helper.py -v
```

当前覆盖：**AuthService 10 项 + face_helper 7 项 = 17 项全过**。

## 课程要求对照

| 课程要求 | 满足方式 | 验证 |
|---|---|---|
| 至少 2 种角色 | 学生 / 教师 / 实验室管理员（3 种） | `docs/PROJECT_PLAN.md` §1 |
| 注册/登录/退出 | bcrypt 哈希 + SQLAlchemy session | `tests/test_auth_service.py` |
| 基本 CRUD | 10 张表全部支持（DAO 层） | `src/dao/*.py` |
| 数据库 | MySQL 8.0（utf8mb4） | `db/schema.sql` |
| UI | PyQt5 桌面应用 | `src/ui/*.py` |
| 加分项：人脸识别自动考勤 | dlib 128 维向量 + 实验室准入场景 | `src/utils/face_helper.py` |

## 仓库地址

https://github.com/JJ704sd/SZTU-Attendance-Management-system-using-face-recognition

## License

MIT — 详见 [LICENSE](LICENSE)
