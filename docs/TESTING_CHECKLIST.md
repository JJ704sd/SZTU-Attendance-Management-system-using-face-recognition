# 亲自测试清单（手机端扫码 + 3 种签到方式）

> 完整跑通 13 周迭代的所有核心功能, 重点验 W13+ 数字码/二维码签到
> 和 W14 多端登录签到 (手机扫码 → 浏览器签到 → 教师端实时反馈)。
> 
> **预计时间**: 30-40 分钟 (首次启动等 dlib 模型下载 5-10 分钟)
> **测试环境**: 1 台电脑 (Win10/11) + 1 部手机 (同 WiFi)

## 0. 启动前检查 (1 分钟)

```powershell
# 1. MySQL 在跑
net start mysql
# 或 服务管理器 → MySQL → 启动

# 2. venv 激活 (项目根目录)
cd D:\Attendance-Management-system-using-face-recognition
.\.venv\Scripts\Activate.ps1

# 3. 验证 13 张表都在 (跨机适配 fix 已修, 应输出 13)
python -c "import sys; sys.path.insert(0, r'$(pwd)'); from src.db import init_db, Base; init_db(); print(f'建表数: {len(Base.metadata.tables)}')"
# 期望: 建表数: 13
```

## 1. 启动 GUI (首次 5-10 分钟, 后续 2 秒)

```powershell
# ⚠️ 必须在项目根目录跑
python -m src.main
```

**首次启动自动发生**:
1. `init_db()` 建表 (13 张, 含 task_signin_code)
2. dlib 模型 120MB 下载 (首次, 断网会失败)
3. 弹登录窗口

**启动成功标志** — `app.log` 应有:
```
W5: 文件日志已启用 -> D:\...\app.log
=== 应用启动 ===
init_db: 开始导入 models
init_db: models 导入完成, 调 create_all
init_db: create_all 完成
数据库初始化完成
人脸编码缓存预热完成: N 个用户
dlib 模型路径 OK: sp=shape_predictor_68_face_landmarks.dat (95MB), fr=dlib_face_recognition_resnet_model_v1.dat (21MB)
```

## 2. 准备测试账号和数据 (2 分钟)

| 角色 | 用户名 | 密码 | 怎么建 |
|---|---|---|---|
| 教师 A (主) | `teacher01` | `123456` | `python scripts\seed_demo_data.py` |
| 教师 B (对比) | `teacher001` | `123456` | seed 已自动建 (W4 演示) |
| 学生 A | `test001` | `123456` | pytest 已建, 没就 `python -c "..."` 手建 |
| 学生 B | `test002` | `123456` | 同上 |
| 管理员 | `labadmin01` | `123456` | seed 已自动建 |

教师 `teacher001` 已经预置了 BME201 课程 + 2 个 open 任务 (W4)。

## 3. 核心测试 1: 刷脸签到 (10 分钟, 需摄像头)

**流程**: 教师发起任务 → 学生录入人脸 → 学生刷脸签到 → 教师看到

1. **学生录入人脸** (W3 Phase 5, 关键!)
   - 登录 `test001 / 123456`
   - 学生端 → 第 1 Tab「人脸注册」→ 打开摄像头 → 等采集 30 张 → 完成
   - 状态: "✅ 已采集 30 张人脸" / "✅ 人脸编码入库成功"
   - **若失败**: 摄像头被占用 / 隐私设置 → 见故障 T6

2. **教师发起任务**
   - 登录 `teacher01 / 123456`
   - 教师端 → 第 1 Tab「发起考勤」→ 点「＋ 发起新考勤」
   - 选课程 BME201 → 选教室 → 开始时间"现在"→ 结束时间"5 分钟后"→ 确定
   - 任务 ID 记住 (例 #1234)

3. **学生刷脸签到**
   - 登录 `test001 / 123456`
   - 学生端 → 第 2 Tab「我的签到」→ 选刚创建的任务 → 切换「📷 刷脸」子 Tab
   - 摄像头开 → 露脸 → 自动识别 → 状态"✅ 出勤"
   - 期望 status=present, signin_method='face'

4. **教师端验证**
   - 教师端 → 第 2 Tab「历史考勤」→ 选中刚那个任务 → 「查看签到详情」
   - 期望: 1 行记录, 状态 present, 方式 face

## 4. 核心测试 2: 数字码签到 (W13+, 3 分钟, **最易复现 P0 bug**)

**关键**: 这条专门验我刚修的 2 个 P0 bug (init_db 跑 migration + db.py 加 import)

1. **教师生成数字码**
   - 登录 `teacher01 / 123456`, 第 1 Tab「发起考勤」
   - 确认有 open 任务 (顶部"⏰ 任务 #XXXX 进行中"标签)
   - 点「🎲 数字签到」按钮
   - **期望**: 弹窗出来, 4 位数字码 (蓝色大字 + 虚线框) + 倒计时进度条 60s
   - **若弹窗报错**: 见故障 T2 (qrcode 包) / T3 (task_signin_code 表)

2. **学生输入码签到**
   - 登录 `test002 / 123456` (用新学生, 避免和刷脸那条冲突)
   - 学生端 → 第 2 Tab「我的签到」→ 选同一任务 → 切换「🔢 数字码」子 Tab
   - 把 4 位码敲进输入框 → 回车 / 点「签到」
   - **期望**: 状态"✅ 出勤" (or "⚠️ 迟到" 若超过开始时间 10 分钟)
   - **若失败**: 弹"❌ 签到码无效或已过期" → 重生成码, 60s 内输完

3. **教师端验证**
   - 关闭 + 重开码弹窗 (点 🔄)
   - 历史考勤 → 选任务 → 查看签到详情
   - 期望: 2 行记录 (test001 face + test002 digit)

4. **重复签到拦截**
   - 同一 test002 再敲一次码 → 期望 "❌ 签到码无效或已过期" (UNIQUE 拦截)

## 5. 核心测试 3: 二维码签到 (W13+, 3 分钟)

1. **教师生成二维码**
   - 登录 `teacher01 / 123456`, 第 1 Tab
   - 点「📱 二维码签到」按钮
   - **期望**: 弹窗 250x250 二维码图片 (灰白方块) + 倒计时 60s
   - **若显示"⚠️ 渲染失败"**: qrcode 包没装 → `pip install 'qrcode[pil]>=7.4'`

2. **学生用电脑摄像头扫** (W3-style, 不用手机)
   - 登录 `test003 / 123456` (再一个新学生, 避免冲突)
   - 学生端 → 第 2 Tab「我的签到」→ 选同一任务 → 切换「📱 二维码」子 Tab
   - 打开摄像头 → 把摄像头对准电脑屏幕上的二维码 → 点「开始扫描」
   - **期望**: 1-2 秒内识别, 状态"✅ 出勤"

3. **历史考勤验证**
   - 教师端 → 历史 → 选任务 → 详情
   - 期望: 3 行 (face + digit + qr, signin_method 字段不同)

## 6. 核心测试 4: **手机扫码** (W14 多端登录, 8 分钟, 重点)

> **这是 W14+ 的核心新功能, 必测**。学生用手机浏览器扫码, 不用装 app。

### 6.1 教师端启 H5 服务

1. 登录 `teacher01`, 第 1 Tab「发起考勤」
2. 点「📱 二维码签到」按钮
3. **关键**: 弹窗**顶部**会显示 H5 URL, 类似:
   ```
   📱 签到链接: http://192.168.x.x:5180/signin/1234/abc...
   ```
   (LAN IP 是 `src/utils/network.get_lan_ip()` 自动探的)
4. **记下这个 URL** (含 IP + task + token)

### 6.2 手机扫码

1. 打开手机相机 (或微信扫一扫)
2. 对准电脑屏幕上的二维码
3. 弹出"在浏览器打开?" → 选浏览器
4. 浏览器跳到 `http://192.168.x.x:5180/signin/...`

### 6.3 期望 H5 页面

- 顶部: "📱 智能考勤 — 多端签到"
- 中间: 任务信息 (课程 / 时间 / 倒计时 60s)
- 底部: 登录表单 (用户名 + 密码) + 提交按钮
- 倒计时归零: 自动刷新 token (W15+ 修法: polling)

### 6.4 提交签到

- 输 `test004 / 123456` (新学生, 没录人脸也行 — H5 不需要摄像头)
- 点"提交签到"
- 期望: 绿框"✅ 签到成功: present"

### 6.5 教师端实时反馈

- 教师电脑那边**不要操作**, 看历史考勤 Tab
- 等几秒, 刷新列表 → 应看到 test004 多了一行 signin_method=qr
- **W14 关键点**: H5 polling `/api/signin/latest` 3 秒一次, 验证教师端 token 跟 H5 同步
- **W15+ 修法**: 删了 `tok != token` 闭包校验, 全走 DB 实时校验

### 6.6 故障排除

| 现象 | 原因 | 解决 |
|---|---|---|
| 手机扫码没反应 / 链接 404 | 端口 5180 被占 | 关掉占用进程 / 重启教师端 |
| 链接打不开 | 手机跟电脑不同 WiFi | 同一 WiFi, 或电脑防火墙开 5180 |
| H5 显示"token 无效" | 教师端在扫码后点过 🔄 刷码 | 这是预期 — H5 polling 会自动拿新 token |
| 提交后教师端看不到 | H5 polling 间隔 3s | 等 3-5s, 手动刷新教师端列表 |

**Windows 防火墙开端口 (若手机连不上)**:
```powershell
# 管理员 PowerShell
New-NetFirewallRule -DisplayName "AttendanceSigninWeb" -Direction Inbound -LocalPort 5180 -Protocol TCP -Action Allow
```

## 7. 核心测试 5: 教师端关闭任务 + 自动缺勤 (2 分钟)

1. 教师端 → 第 2 Tab「历史考勤」→ 选中任务
2. 点「结束选中任务」→ 确认
3. 状态变成"⚫ 已结束"
4. 等 5 秒, 再点「查看签到详情」
5. 期望: 全班学生都在, 已签的 present/late, 没签的 absent, 请过假的 leave

## 8. 核心测试 6: 学生请假 (W6, 3 分钟)

1. 登录 `test005 / 123456` (新学生)
2. 学生端 → 第 4 Tab「我的请假」→ 「＋ 申请请假」→ 选任务 → 填理由 → 提交
3. 切到教师 `teacher01` → 历史考勤 → 「📝 待审批请假」→ 选中 → 通过 / 拒绝
4. 切回学生 → 状态: 已通过 / 已拒绝
5. 教师端 → 关闭任务 → 该学生 status='leave' (不是 absent)

## 9. 核心测试 7: 管理员人脸管理 (W12, 3 分钟)

1. 登录 `labadmin01 / 123456`
2. 第 5 Tab「人脸管理」→ 选 test001 → 「查看人脸数」→ 期望 ≥ 30
3. 「清空该用户人脸」→ 确认 → test001 人脸数 = 0
4. test001 重登 → 第 1 Tab 重新采集人脸 → 应能正常采集

## 10. 跑自动化测试 (验证环境 OK, 1 分钟)

```powershell
pytest tests/ -q
# 期望: 188 passed in ~55s, 7 warnings (websockets 库 deprecation, 跟我们无关)

python scripts\smoke_signin_methods.py
# 期望: [OK] smoke_signin_methods.py 通过

python scripts\smoke_full_regression.py
# 期望: === 总计: ok=29  fail=0  skip=0 ===
# (test001 需先存在 — 上面的 seed 步骤已建)
```

## 故障排除速查

| ID | 症状 | 修法 |
|---|---|---|
| T1 | 弹"无法连接或初始化数据库" | `net start mysql` + 查 .env DB_PASSWORD |
| T2 | 二维码弹窗显示"⚠️ 渲染失败: No module named 'qrcode'" | `pip install 'qrcode[pil]>=7.4'` |
| T3 | 数字码/二维码签到报"Table 'task_signin_code' doesn't exist" | 跨机适配 fix 已修; 手动跑 `python scripts\init_db.py` |
| T4 | dlib 模型下载卡住 | 重启程序续传; 借一个 `models\*.dat` 拷到本地 |
| T5 | PowerShell 中文输出乱码 | 不影响功能; 改用 Windows Terminal / cmd |
| T6 | 摄像头打不开 | 关 QQ/微信/Zoom; 隐私设置允许桌面应用 |
| T7 | `git push` 失败 | `git -c http.proxy= -c https.proxy= push -u origin main` |
| T8 | 手机连不上 H5 | 同 WiFi; 防火墙开 5180 端口 (见 6.6) |
| T9 | 多 GUI 进程抢资源 (180 端口冲突) | `kill_all_python.bat` 一次清干净 |
| T10 | `cmd /c` 报"不是内部或外部命令" (.bat 中文注释) | .bat 全 ASCII (W15+ 修过) |

## 完整通过标志

- [ ] pytest 188/188 全过
- [ ] 7 个 smoke 端到端脚本全过
- [ ] 刷脸签到 1 条 (face)
- [ ] 数字码签到 1 条 (digit, 60s 内)
- [ ] 电脑摄像头二维码签到 1 条 (qr)
- [ ] **手机扫码 H5 签到 1 条 (qr, 走 W14 signin_web)**
- [ ] 教师关闭任务后, 没签到的学生自动 absent
- [ ] 学生请假审批后, 关闭任务时变 leave
- [ ] 管理员人脸管理能清空 / 重新采集

---

**所有勾都打了就 OK 交付。**
**有勾不上 / 跑不通的, 群里吼一声, 我来帮你看。**
