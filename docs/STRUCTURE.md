# 项目结构说明

> 本文档是**仓库目录树的总览**，每个目录/文件的作用都写明。
> 新加入的成员读这一份就能快速定位代码。

## 目录树

```
Attendance-Management-system-using-face-recognition/
├── README.md                 # 项目门面：简介、文档导航、快速开始
├── QUICKSTART.md             # 5 分钟跑起来
├── LICENSE                   # MIT 协议
├── .env.example              # 数据库等环境变量模板（不含真实密码）
├── .gitignore                # Git 忽略规则（.env、模型权重、数据集等）
├── requirements.txt          # 主依赖（PyQt5、SQLAlchemy、bcrypt、dlib-bin、opencv…）
├── requirements-dlib.txt     # dlib 替代安装选项
│
├── db/                       # 数据库
│   └── schema.sql            # MySQL 完整 DDL（10 张表，utf8mb4）
│
├── docs/                     # 设计文档
│   ├── PROJECT_PLAN.md       # 架构 / 技术栈 / 模块 / 风险
│   ├── DATABASE.md           # ER 图 + 11 张表设计说明
│   ├── WORKFLOWS.md          # 三大业务流程
│   ├── TEAM_AND_TIMELINE.md  # 5 人分工 + 6 周时间线
│   ├── STRUCTURE.md          # ← 本文件
│   ├── ARCHITECTURE.md       # 分层架构、模块依赖、数据流
│   └── DEVELOPMENT.md        # 开发者上手指南
│
├── reference/                # 外部参考代码（不参与运行）
│   └── patelrahul4884/       # 原项目参考实现
│       ├── README.md
│       ├── attendance_service.py
│       ├── face_service.py
│       ├── lab_access_service.py
│       ├── report_service.py
│       └── requirements.txt
│
├── src/                      # ← 本项目主代码
│   ├── main.py               # 应用入口
│   ├── config.py             # 全局配置（读 .env）
│   ├── db.py                 # SQLAlchemy engine / session / Base
│   ├── __init__.py
│   ├── models/               # ORM 模型（10 张表的 Python 类）
│   │   ├── user.py
│   │   ├── face.py
│   │   ├── course.py
│   │   ├── attendance.py
│   │   └── lab.py
│   ├── dao/                  # 数据访问层
│   │   ├── base.py
│   │   ├── user_dao.py
│   │   ├── course_dao.py
│   │   ├── classroom_dao.py
│   │   └── attendance_dao.py
│   ├── services/             # 业务逻辑层
│   │   ├── auth_service.py
│   │   └── attendance_service.py
│   ├── ui/                   # PyQt5 表现层
│   │   ├── login_window.py
│   │   ├── register_window.py
│   │   ├── student_window.py
│   │   ├── teacher_window.py
│   │   ├── admin_window.py
│   │   └── widgets/          # 自定义对话框
│   │       ├── create_task_dialog.py
│   │       └── task_detail_dialog.py
│   ├── utils/                # 工具模块
│   │   ├── crypto.py         # bcrypt 哈希
│   │   └── face_helper.py    # dlib 封装（face_locations / encodings / distance）
│   └── assets/               # 图标、头像等静态资源
│
├── tests/                    # 单元测试
│   ├── conftest.py
│   ├── test_auth_service.py  # 10 个测试，覆盖注册/登录/改密
│   └── test_face_helper.py   # 7 个测试，覆盖人脸工具函数
│
├── scripts/                  # 运维脚本
│   ├── init_db.py            # 一键执行 db/schema.sql
│   ├── run_dev.sh            # Linux/macOS 启动
│   └── run_dev.bat           # Windows 启动
│
└── models/                   # dlib 模型权重（git 忽略，运行时自动下载）
    ├── shape_predictor_68_face_landmarks.dat    # 95 MB
    └── dlib_face_recognition_resnet_model_v1.dat # 21 MB
```

## 关键路径

| 想做什么 | 去哪里看 |
|---|---|
| 改数据库表 | `db/schema.sql` + `src/models/*.py` |
| 加一个 DAO 方法 | `src/dao/base_dao.py` 继承 + `src/dao/<entity>_dao.py` |
| 加一个业务服务 | `src/services/<feature>_service.py` |
| 加一个 UI 窗口 | `src/ui/<role>_window.py` |
| 加一个对话框 | `src/ui/widgets/<feature>_dialog.py` |
| 改人脸识别参数 | `src/utils/face_helper.py` + `.env` 中 `FACE_MATCH_THRESHOLD` |
| 改登录/注册逻辑 | `src/services/auth_service.py` |
| 加单元测试 | `tests/test_<module>.py` |
| 写设计文档 | `docs/*.md` |

## 哪些是运行时产物（**不入 git**）

- `.env`（含真实密码）
- `models/*.dat`（dlib 模型权重，运行时由 `ensure_models()` 下载）
- `dataset/`（人脸采集图片，运行时由 `face_service` 写入）
- `__pycache__/`
- `build/`, `dist/`（PyInstaller 打包产物）
- `.pytest_cache/`, `.coverage`, `htmlcov/`
