# 参考项目：Patelrahul4884/Attendance-Management-system-using-face-recognition

> 本目录保存了**仅供架构参考**的原始实现代码，**不属于本项目的运行代码**。
> 本项目主代码位于仓库根目录的 [`src/`](../../src/)。

## 来源

- 仓库：https://github.com/Patelrahul4884/Attendance-Management-system-using-face-recognition
- 角色：为本项目提供**早期架构灵感**和**功能模块划分**的参考

## 本目录包含的文件

| 文件 | 原项目中的作用 | 本项目中的对应实现 |
|---|---|---|
| `attendance_service.py` | 考勤任务 + 签到 | [`src/services/attendance_service.py`](../../src/services/attendance_service.py) |
| `face_service.py` | 摄像头采集 + LBPH 训练识别 | [`src/services/face_service.py`](../../src/services/face_service.py)（W3 接入）+ [`src/utils/face_helper.py`](../../src/utils/face_helper.py) |
| `lab_access_service.py` | 实验室准入核验 | [`src/services/lab_access_service.py`](../../src/services/lab_access_service.py)（W4 接入） |
| `report_service.py` | 报表输出 | [`src/services/report_service.py`](../../src/services/report_service.py)（W4 接入） |
| `requirements.txt` | 原项目依赖清单 | **弃用**，本项目用 [`requirements.txt`](../../requirements.txt) |

## 与原项目的主要差异

| 维度 | 原项目 | 本项目 |
|---|---|---|
| UI | Tkinter | PyQt5 |
| 识别算法 | OpenCV LBPH（Local Binary Patterns Histograms） | dlib HOG 检测 + 128 维 ResNet 向量 |
| 存储 | CSV 文件 | MySQL 8.0 + SQLAlchemy ORM |
| 角色 | 仅学生 | 学生 / 教师 / 实验室管理员 |
| 场景 | 单一课堂考勤 | 课堂 + 实验课 + 实验室准入 |
| 图表 | 无 | matplotlib 可视化 |
| 部署 | 单文件脚本 | 分层架构（DAO / Service / UI） |
| 密码 | 明文 | bcrypt 哈希 |

## 为什么保留这些文件

1. **教学存档**：作为课程设计报告「参考项目分析」一节的引用材料
2. **代码对照**：便于教师/助教对比"原方案"与"改进方案"
3. **演进追溯**：保留本项目从"参考"到"重写"的演进痕迹

**注意**：这些文件不会被本项目 import，仅作为静态参考。
