# 快速启动

## 当前状态

✅ Python 3.13 + PyQt5 + SQLAlchemy + bcrypt + PyMySQL 装好
✅ MySQL 8.0.45 连上，建库 `attendance_lab`，10 张表
✅ bcrypt 密码哈希 + 校验
✅ AuthService 注册/登录端到端测试通过（10 项）
✅ LoginWindow / RegisterWindow / TeacherWindow 可启动
✅ dlib-bin 20.0.1 装好，dlib 模型已自动下载（120 MB）
✅ 17/17 单元测试通过

## 5 分钟跑起来

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env（首次）
cp .env.example .env       # Windows: copy .env.example .env
# 编辑 .env，把 DB_PASSWORD 改成你的 MySQL 密码

# 3. 初始化数据库
python scripts/init_db.py

# 4. 启动应用
python -m src.main
```

## 启动 GUI

**推荐方式**（在项目根目录）：

```bash
cd "D:/Attendance-Management-system-using-face-recognition"
python -m src.main
```

**等价方式**（用启动脚本）：

```bash
bash scripts/run_dev.sh        # Linux/macOS
scripts\run_dev.bat            # Windows
```

> ⚠️ 一定要在项目根目录执行，不能 `cd src` 之后再 `python main.py`，那样 `src` 自己找不到自己。
> ⚠️ 不要在 offscreen 模式下触发按钮（Windows PyQt5 offscreen 与 QMessageBox 有已知冲突）。
> 直接在带显示器的本地终端跑就行。

## 测试账号

| 用户名 | 密码 | 角色 | 备注 |
|---|---|---|---|
| `test001` | `123456` | 学生 | 已注册，方向：智能医学工程 |
| `teacher01` | `123456` | 教师 | 已注册，教 BME201 |

> 跑 `pytest tests/test_auth_service.py` 会自动注册大量测试账号，**不影响真实数据**（用户名带随机后缀）。

## 你可以做的验证

### 1. 登录窗口

- 用 `test001/123456` 登录，角色选"学生" → 应该看到"登录成功"提示
- 用 `test001/123456` 登录，角色选"教师" → 应该看到"角色不匹配"提示
- 用错密码 → 应该看到"用户名或密码错误"

### 2. 注册窗口（点登录窗口的"注册新账号"）

- 注册一个 teacher 角色的账号
- 重复用户名/学号 → 应该看到"已存在"提示

### 3. 教师端（teacher01 登录后）

- "发起考勤" → 选课程 + 教室 + 时间段 → 创建任务
- "历史考勤" → 看到刚才创建的任务，状态 = 🟢 进行中
- "结束选中任务" → 系统自动补齐缺勤学生
- "查看签到详情" → 看到每个学生的出勤情况

## 运行测试

```bash
# 全量
pytest tests/ -v

# 单独跑
pytest tests/test_auth_service.py -v
pytest tests/test_face_helper.py -v
```

## 后续要做的

- [ ] W3: face_service（摄像头采集/训练/识别）+ 学生端刷脸签到
- [ ] W4: 实验室管理员端（CRUD 实验室 + 安全培训核验）
- [ ] W4: 报表（matplotlib 嵌入 + 导出 PDF）
- [ ] W5: 联调 + PyInstaller 打包
- [ ] W6: 课程设计报告 + 答辩 PPT

## 已知问题

- dlib 在 Python 3.13 上没有官方预编译 wheel，解决方案：
  1. `pip install dlib-bin`（社区编译版，**已采用**）
  2. 不行再 `pip install cmake` + Visual Studio Build Tools + `pip install dlib`
  3. 还不行就降级 Python 到 3.11（推荐 venv 隔离）
- PyQt5 在 Windows offscreen 模式下触发 QMessageBox 会段错误；直接带显示器跑就行。

## 目录速查

```
src/    主代码（ui / services / dao / models / utils）
db/     schema.sql
docs/   PROJECT_PLAN / ARCHITECTURE / DATABASE / WORKFLOWS / ...
tests/  test_auth_service / test_face_helper
scripts/ init_db / run_dev
reference/patelrahul4884/  原项目参考实现
```

详细结构见 [docs/STRUCTURE.md](docs/STRUCTURE.md)。
