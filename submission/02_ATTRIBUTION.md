# 参考声明 / 第三方资料使用清单

> 本声明遵循"参考网络资料 ≤ 30% 写明出处"的课程要求, 透明列示项目使用的所有第三方库、参考的官方文档、借鉴的开源项目/UX 模式、及**自研分界**。
> 配套文档: `submission/01_DESIGN_PROPOSAL.md` (整体设计) + 项目根目录 `requirements.txt` (完整依赖)

---

## 0. 自研比例声明 (诚实估算)

| 来源类型 | 占比估算 |
|---|---|
| 第三方库 `import` 直接使用 | ~10% |
| API 模式参考官方文档 (SQLAlchemy/FastAPI/PyQt5/dlib) | ~5% |
| 业务模式参考"对分易"等已知 App | ~5% |
| 解决思路参考 stackoverflow / 博客 | ~5% |
| **自研部分** (4 层架构 / 14 张表 / 7 service / 13 widget / 业务逻辑 / 测试 / W14 H5) | **~75%** |

**总参考占比 ≈ 25%** ✓ (课程要求 ≤ 30%)

---

## 1. 第三方库清单 (15 个, 全部 PyPI 开源)

| # | 库 | 版本 | License | 用途 | 项目内使用文件 |
|---|---|---|---|---|---|
| 1 | **PyQt5** | 5.15.x | GPL-3.0 | GUI 框架 (5 主窗口 + 13 widget) | `src/ui/*.py` |
| 2 | **SQLAlchemy** | 2.0.x | MIT | ORM (防 SQL 注入) | `src/dao/*.py` + `src/db.py` |
| 3 | **PyMySQL** | 1.1.x | MIT | MySQL 驱动 | `src/db.py` |
| 4 | **bcrypt** | 4.x | Apache-2.0 | 密码哈希 (替代明文) | `src/utils/crypto.py` |
| 5 | **dlib-bin** | 20.0.1 | Boost-1.0 | 人脸识别 128 维向量 | `src/utils/face_helper.py` |
| 6 | **numpy** | 1.26.x | BSD-3 | 数值计算 + face encoding 存储 | `src/utils/face_helper.py` |
| 7 | **opencv-python** | 4.10.x | Apache-2.0 | 摄像头 + QR 解码 | `src/ui/widgets/camera_widget.py` + `src/ui/widgets/qr_scan_widget.py` |
| 8 | **matplotlib** | 3.10.x | PSF | 4 类统计图表 | `src/utils/charts.py` |
| 9 | **qrcode** | 8.x | BSD | 二维码生成 (PIL 编码 PNG) | `src/services/attendance_service.py` |
| 10 | **Pillow (PIL)** | 10.x | HPND | 图像处理 (PNG 编码) | `src/services/attendance_service.py` |
| 11 | **python-dotenv** | 1.0.x | BSD-3 | .env 加载 | `src/config.py` |
| 12 | **FastAPI** | 0.115.x | MIT | W14 H5 多端签到 | `src/services/signin_web.py` |
| 13 | **uvicorn** | 0.32.x | BSD-3 | ASGI server (嵌入 PyQt 进程) | `src/services/signin_web.py` |
| 14 | **jinja2** | 3.x | BSD-3 | H5 签到页模板 | `src/services/signin_web.py` |
| 15 | **httpx** | 0.27.x | BSD-3 | smoke 脚本的 HTTP 客户端 | `scripts/smoke_*.py` |
| 16 | **PyInstaller** | 6.x | GPL-2.0 | onedir 打包 (380 MB) | `build.spec` |
| 17 | **pytest** | 8.x | MIT | 单元测试 219 项 | `tests/test_*.py` |

**所有 17 个库均通过 `pip install` 从 PyPI 安装, 全部开源 + 商用友好 License (MIT/BSD/Apache/PSF/HPND/Boost)**

---

## 2. 关键 API / 实现模式参考 (4 处, 单独标出)

> 这 4 处是**参考了开源项目的实现思路**, 但**所有代码都是自写**, 命名/返回值结构借鉴, 内部逻辑原创

### 2.1 face_recognition 库 (Adam Geitgey, MIT)
- **官网**: https://github.com/ageitgey/face_recognition
- **借鉴内容**: 4 个核心 API 的**命名 + 返回值结构**
  - `face_locations(image)` → `[(top, right, bottom, left), ...]`
  - `face_encodings(image, known_face_locations=None)` → `[np.ndarray(128), ...]`
  - `face_distance(face_encodings, face_to_compare)` → `np.ndarray` 欧氏距离
  - `compare_faces(face_encodings, face_to_compare, tolerance=0.6)` → `[bool, ...]`
- **自研部分**:
  - 内部用 `dlib.get_frontal_face_detector()` + `dlib.face_recognition_model_v1()` 自行调用
  - `_FaceCache` 全量加载 + numpy 向量化距离计算 (业务用, 库没这个)
  - `face_helper.face_encodings` 统一返 `np.float32` (库返 float64)
  - 我们的 tolerance 0.45 比库默认 0.6 更严 (业务用, 课程实测)
- **借鉴比例**: ~30% (命名 + 返回结构) / 自研 ~70% (业务逻辑 + 缓存 + 类型)
- **课程合规性**: ✓ 库本身 MIT 协议, 借鉴 API 模式属于合理使用

### 2.2 matplotlib 官方 gallery (PSF, BSD-compatible)
- **官网**: https://matplotlib.org/stable/gallery/
- **借鉴内容**: 4 类图表的**样式 + 参数**
  - Bar chart (课程出勤率排行) — 参考 `bar_of_pie`
  - Heatmap (实验室使用率) — 参考 `image_demo`
  - Line chart (出勤趋势) — 参考 `fill_between_demo`
  - Table (缺勤预警) — 参考 `table_demo`
- **自研部分**:
  - 数据查询 (走 service → dao → DB)
  - 颜色 + 字体 + 标题本地化 (中文)
  - PyQt 嵌入 (`FigureCanvasQTAgg`)
  - 4 个 widget 调用入口
- **借鉴比例**: ~80% (样式参数) / 自研 ~20% (数据流 + 本地化 + PyQt 集成)
- **课程合规性**: ✓ matplotlib 文档明确允许参考示例

### 2.3 FastAPI / uvicorn 嵌入 PyQt 进程 (MIT / BSD-3)
- **参考文档**:
  - https://www.uvicorn.org/settings/#running-programmatically
  - https://github.com/tiangolo/fastapi/issues/2243
- **借鉴内容**:
  - `uvicorn.Server(Config(...))` + `threading.Thread(daemon=True)` 嵌入模式
  - `srv.should_exit = True` + `srv.wait_for_shutdown()` 关闭模式
- **自研部分**:
  - 与 PyQt5 事件循环共存 (不冲突)
  - closeEvent 时优雅停服
  - watchdog 子线程 (30s 内 6 次失败才报警, 避免抖动)
  - 端口冲突自动重试 5 次 (5180-5184)
  - get_lan_ip 改阿里 DNS (国内组员可访问, 这是 W15+ 修复)
  - update_token 实时查 DB (W15+ 修 `tok != token` 闭包 bug)
- **借鉴比例**: ~10% (uvicorn 启动模式) / 自研 ~90% (W14 H5 业务 + 跨机适配)
- **课程合规性**: ✓ 文档允许, 业务逻辑自研

### 2.4 对分易 App UX 模式 (闭源产品, 参考 UX 不抄代码)
- **借鉴内容**:
  - 教师生成 4 位数字码 + 60s 倒计时
  - 二维码 + 倒计时同步显示
  - 重复签到拦截 (UNIQUE 兜底)
  - 多端签到 (手机扫码 + 电脑摄像头)
- **自研部分**:
  - 数据库表设计 (`task_signin_code` 14 张表之一)
  - 3 种签到统一公共核 (`_create_record`)
  - 数字码生成 (`{:04d}` 4 位 + 60s 过期)
  - 二维码内容 (base64 token, 不带 URL, 业务可控)
  - 教师端实时反馈 (signin_web watchdog 30s 容错)
- **借鉴比例**: ~5% (UX 模式) / 自研 ~95% (代码实现)
- **课程合规性**: ✓ UX 模式是公开常识, 不涉及代码抄袭

---

## 3. 解决思路参考 (5 个 stackoverflow / 博客)

> 解决**通用工程问题**时参考, 思路公开化, 项目内代码完全自写

| # | 问题 | 参考来源 | 自研实现 |
|---|---|---|---|
| 1 | 跨机 LAN IP 探测 (UDP 半连接) | https://stackoverflow.com/q/166506 | `src/utils/network.py::get_lan_ip()` (W15+ 改阿里 DNS 223.5.5.5) |
| 2 | PyQt5 + FastAPI 嵌入 | https://github.com/tiangolo/fastapi/issues/2243 | `src/services/signin_web.py::SigninWebServer.start()` |
| 3 | dlib 模型下载重试 | https://github.com/davisking/dlib-models/issues/9 | `src/utils/face_helper.py::ensure_models()` (gitee 镜像 fallback) |
| 4 | matplotlib 中文乱码 | https://www.zhihu.com/question/25404709 | `src/utils/charts.py::setup_chinese_font()` |
| 5 | bcrypt 4.x 兼容 | https://github.com/pyca/bcrypt/issues/532 | `src/utils/crypto.py::hash_password()` (passlib 锁版本 1.7.4) |

**借鉴比例**: ~5% (解决思路) / 自研 ~95% (代码实现 + 业务适配)

---

## 4. 自研分界声明 (75%)

### 4.1 全部自研 (无任何第三方代码复用)

| 模块 | 行数估算 | 自研率 |
|---|---|---|
| **4 层架构设计** (ui → service → dao → model) | ~200 | 100% |
| **14 张表 schema** (db/schema.sql + 3 migration) | ~600 SQL | 100% |
| **7 个 service 业务逻辑** (auth/attendance/face/lab/leave/report/signin_web) | ~3000 | 100% |
| **13 个 DAO** (SQLAlchemy 2.0 ORM) | ~1500 | 100% |
| **8 个 ORM model** (User/FaceEncoding/Course/...) | ~600 | 100% |
| **5 主窗口 + 13 widget UI** (PyQt5) | ~5000 | 100% |
| **W14 FastAPI 嵌入 + H5 签到页 + signin_web watchdog** | ~600 | 100% |
| **3 种签到统一公共核 `_create_record`** | ~100 | 100% |
| **跨机可行性 4 P0 修复** (init_db / import_schedule / Python 3.10+ / get_lan_ip) | ~150 | 100% |
| **6 次 bug 审计 (W7-W12, 36 真 bug 修复 + W16 docs/arch/UI 联审)** | ~500 | 100% |
| **219 单元测试 + 10 smoke 端到端** | ~3000 | 100% |
| **5 份文档** (PROJECT_PLAN / ARCHITECTURE / STRUCTURE / DEVELOPMENT / DATABASE) | ~3000 | 100% |

### 4.2 部分自研 (参考 API 模式, 业务逻辑自写)

- **face_helper 4 核心 API** — 参考 face_recognition 命名 + 返回值结构, 内部调用 dlib 自写
- **charts 4 类图表** — 参考 matplotlib gallery 样式 + 参数, 数据流 + 本地化自写
- **signin_web 嵌入** — 参考 uvicorn 启动模式, 业务逻辑自写

### 4.3 工具类参考 (纯工具性质, 非业务)

- **crypto** — bcrypt 标准用法, 几乎 100% 库调用
- **paths** — pathlib 标准库, 100% 自写
- **charts 中文字体** — matplotlib rcParams 配置, 文档公开

---

## 5. 学术诚信声明

1. **本项目所有源代码均为本团队成员原创开发**, 未抄袭任何其他学生作业或商业项目代码
2. **第三方库使用**仅限于 PyPI 公开开源库 (见上表), 全部通过 `pip install -r requirements.txt` 安装
3. **API 模式参考**仅限于开源项目的**公开文档和示例**, 业务逻辑完全自写
4. **UX 模式参考**仅限于"对分易"等已知 App 的**用户交互模式**, 不涉及代码实现
5. **解决思路参考**仅限于 stackoverflow / 博客的**公开技术方案**, 代码实现完全自写
6. **本声明覆盖 100% 项目代码**, 任何不明确引用已**单独标出**
7. **最终交付物** (源码 + 可执行文件 + 文档) 与本声明内容一致, 可在 GitHub 仓库 `https://github.com/JJ704sd/SZTU-Attendance-Management-system-using-face-recognition` 完整追溯

---

## 6. 第三方库详细 License (合规使用)

```
PyQt5         : GPL-3.0          (动态链接, 本项目二进制不强制开源)
SQLAlchemy    : MIT              (商用友好, 保留版权声明即可)
PyMySQL       : MIT              (商用友好)
bcrypt        : Apache-2.0       (商用友好)
dlib-bin      : Boost-1.0        (商用友好)
numpy         : BSD-3-Clause     (商用友好)
opencv-python : Apache-2.0       (商用友好)
matplotlib    : PSF-2.0          (商用友好, 类似 BSD)
qrcode        : BSD-3-Clause     (商用友好)
Pillow        : HPND             (商用友好)
python-dotenv : BSD-3-Clause     (商用友好)
FastAPI       : MIT              (商用友好)
uvicorn       : BSD-3-Clause     (商用友好)
jinja2        : BSD-3-Clause     (商用友好)
httpx         : BSD-3-Clause     (商用友好)
PyInstaller   : GPL-2.0 + 商业例外 (PyInstaller 商业许可可选)
pytest        : MIT              (商用友好)
```

**所有 17 个库均合规使用, 不存在 License 冲突。**

---

## 7. 引用完整性

- **仓库地址**: https://github.com/JJ704sd/SZTU-Attendance-Management-system-using-face-recognition
- **本声明版本**: v1.0, 2026-06-17
- **配套提交物**: `<组长学号>_智能考勤与实验室准入系统_设计方案.zip`
- **课程验收时**, 老师可对照本声明 + 仓库 main (94 commit) + R16 增 11 commit (audit-round16 HEAD, 公式化) 完整追溯

—— 参考声明完毕
