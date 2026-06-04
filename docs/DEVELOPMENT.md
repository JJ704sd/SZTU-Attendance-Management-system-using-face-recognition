# 开发者上手指南

> 目标：让一个新成员在 30 分钟内把项目跑起来，并写一个 PR。

## 1. 准备开发环境

### 1.1 系统要求

- **OS**：Windows 10/11、macOS 12+、Ubuntu 20.04+ 任一
- **Python**：3.11+（推荐 3.12 / 3.13）
- **MySQL**：8.0+（本地或 Docker）
- **磁盘**：至少 2 GB 可用（dlib 模型约 120 MB + 虚拟环境 + 项目代码）

### 1.2 克隆并安装依赖

```bash
git clone https://github.com/JJ704sd/SZTU-Attendance-Management-system-using-face-recognition.git
cd SZTU-Attendance-Management-system-using-face-recognition

# 推荐：创建虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# （可选）如需 dlib 替代安装选项，参考 requirements-dlib.txt
```

### 1.3 数据库准备

```bash
# 1. 启动本地 MySQL，确认 3306 端口可连
# 2. 复制 .env.example 为 .env，填入你的 MySQL 密码
cp .env.example .env       # Windows: copy .env.example .env

# 3. 一键建库 + 建表
python scripts/init_db.py
```

### 1.4 启动应用

```bash
# 推荐（自动把项目根目录加进 sys.path）
python -m src.main

# 等价方式
bash scripts/run_dev.sh        # Linux/macOS
scripts\run_dev.bat            # Windows
```

启动后会自动弹出登录窗口。**测试账号**：

| 用户名 | 密码 | 角色 |
|---|---|---|
| `test001` | `123456` | 学生 |
| `teacher01` | `123456` | 教师（教 BME201） |

## 2. 项目结构

详见 [STRUCTURE.md](STRUCTURE.md)。一句话总结：

```
ui/        表现层（PyQt5 窗口）
services/  业务逻辑（auth / attendance / face / lab_access / report）
dao/       数据访问（SQLAlchemy）
models/    ORM 模型（10 张表）
db.py      engine + session
utils/     通用工具（crypto / face_helper）
tests/     单元测试
docs/      设计文档
```

## 3. 写第一个功能

按 TDD 流程：

### 3.1 写一个失败的测试

```python
# tests/test_my_service.py
def test_my_feature():
    from src.services.my_service import MyService
    s = MyService()
    result = s.do_something("input")
    assert result == "expected"
```

```bash
pytest tests/test_my_service.py -v
# Expected: FAIL (ModuleNotFoundError)
```

### 3.2 写最小实现

```python
# src/services/my_service.py
class MyService:
    def do_something(self, x: str) -> str:
        return "expected"
```

### 3.3 测试通过

```bash
pytest tests/test_my_service.py -v
# Expected: PASS
```

### 3.4 提交

```bash
git checkout -b feat/my-feature
git add .
git commit -m "feat: add my feature"
git push -u origin feat/my-feature
# 在 GitHub 提 PR
```

## 4. 代码风格

- **行宽**：120 字符
- **命名**：
  - 类名 `PascalCase`
  - 函数/变量 `snake_case`
  - 常量 `UPPER_SNAKE_CASE`
  - 私有方法 `_leading_underscore`
- **import 顺序**：标准库 → 第三方 → 项目内（用 `from src.xxx import yyy`）
- **类型注解**：服务层和工具层必须有；UI 层可省略
- **docstring**：模块级 + 公共方法用三引号

## 5. 调试技巧

### 5.1 数据库连不上

```python
# 在 Python REPL 里测试
from src.config import Config
print(Config.database_url().replace(Config.DB_PASSWORD, "***"))
# 然后用 mysql 客户端连同样的 URL
```

### 5.2 dlib 装不上

```bash
# 备选 1（强烈推荐）
pip install dlib-bin==20.0.1

# 备选 2（从源码编译）
pip install cmake
# Windows: 安装 Visual Studio Build Tools，勾选 C++ build tools
pip install dlib
```

### 5.3 PyQt5 offscreen 在 Windows 上崩

```bash
# 错误表现：触发 QMessageBox 时崩溃
# 解决：在带显示器的本地终端直接跑，不要加 QT_QPA_PLATFORM=offscreen
python -m src.main
```

### 5.4 测试失败

```bash
# 详细输出
pytest tests/ -v --tb=long

# 跑单个
pytest tests/test_auth_service.py::test_register_and_login_success -v
```

## 6. 提交规范（commit message）

```
<type>(<scope>): <subject>

<body>

<footer>
```

**type**：

- `feat` 新功能
- `fix` 修 bug
- `docs` 文档
- `style` 格式（不改逻辑）
- `refactor` 重构
- `test` 加测试
- `chore` 构建/工具/CI

**示例**：

```
feat(auth): add password strength validation

- require at least 8 chars + 1 digit + 1 letter
- update tests
- close #12
```

## 7. 常见任务清单

| 任务 | 关键文件 |
|---|---|
| 加一张新表 | `db/schema.sql` + `src/models/<entity>.py` + `src/dao/<entity>_dao.py` |
| 加一个新角色 | `src/models/user.py` 中 `role` 枚举 + `src/ui/<role>_window.py` |
| 加一个登录后跳转的主窗口 | 修改 `src/ui/login_window.py::_open_role_window()` |
| 改密码强度规则 | `src/services/auth_service.py::USERNAME_RE` / `register()` |
| 改人脸匹配阈值 | `.env` 中 `FACE_MATCH_THRESHOLD` |
| 加一个新业务服务 | `src/services/<feature>_service.py` + `tests/test_<feature>_service.py` |
