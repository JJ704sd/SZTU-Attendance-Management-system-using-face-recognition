#演示视频录制脚本（DEMO_RECORDING.md）

> **项目**:智能考勤与实验室准入系统（PyQt5 + dlib + MySQL8.0）
> **课设**: 深圳技术大学健康与环境工程学院「数据库原理」2025-2026-2
> **截止**:2026-06-20
> **写于**:2026-06-08
> **作者**: Mavis（自动生成）+团队校对

---

##0.拍摄目标

录制一份 **4-5 分钟** 的业务闭环演示视频，覆盖：
-3角色登录路由
- 学生人脸注册（采集30 张）
- 教师发起考勤任务
- 学生刷脸签到
- 教师查看签到详情
-管理员人脸管理
-总结页

输出 `docs/demo.mp4`，1920×1080，30fps，~150 MB，可用于：
-老师验收（按 W12 plan Phase3截止6-18）
-答辩备份
-提交物 zip（按 W12 plan Phase6截止6-20）

---

##1.录制工具

### 🥇首选：PowerPoint录屏（系统自带 / 学生基本都装了 Office）

**零装、零时长限制、操作最简单**。Win 系统自带，**不需要下载任何第三方软件**。

| 项 | 操作 |
|---|---|
|启动 |打开 PowerPoint → 新建空白演示文稿 |
| 进入 | 「插入」选项卡 →右侧「屏幕录制」按钮 |
|选区 | 点「选择区域」拖框选全屏（默认全屏即可） |
| 开始 | 点「录制」按钮 / 热键 `Win+Shift+R` |
|停止 | 点浮动工具条「停止」按钮 |
|导出 | 右键视频 →「另存为媒体」→存 mp4 到 `docs/demo_raw.mp4` |

**优点**：无时长限制、可选全屏/窗口/区域、输出 mp4、零装  
**缺点**：需装 Office（学生电脑基本都装了）

### 🥈备选：Win11截图工具（完全零装）

如果没装 Office：

| 项 | 操作 |
|---|---|
|启动 | 开始菜单搜"截图工具"→打开 |
| 进入 | 点「+ 新建」下拉 →选「录制」（Win1122H2+才有） |
|选区 |拖框选全屏 |
| 开始 | 点「开始」按钮 |
|停止 | 点「停止」→ 自动保存 mp4 |
|路径 | `视频 →屏幕录制` 文件夹 |

**坑**：单段 **~3 分钟**限制（demo4-5 分钟要分2段后期 FFmpeg拼接）

### 🥉 不推荐：Xbox Game Bar（`Win+G`）

**坑**：
- ❌ 不能录桌面本身
- ❌ 不能录文件资源管理器
- ❌切换窗口会断（中途切到 terminal /浏览器会黑屏）

PyQt5 应用窗口能录，但录制流程里要切到控制台看 log就会断。不推荐。

###备选：OBS Studio（专业但要装）

| 项 | 推荐设置 |
|---|---|
| 下载 | https://obsproject.com/ |
| 版本 |30.0+ |
| 安装 | Windows 默认全勾 |
|启动 |打开 OBS → 「工具」→「录制设置」 |

**OBS 配置**：
```
场景:
 + "Demo 全屏" - 单显示器全屏捕获 (1920x1080)
 + "Demo +摄像头画中画" -显示器 +摄像头（可选）

来源 (Sources):
 + "显示器捕获" (Display Capture) —选主显示器
 + "音频输入采集" (Audio Input Capture) —麦克风（如果以后要配音）
 + "音频输出采集" (Audio Output Capture) —桌面音频（关掉，避免录到杂音）

设置 (Settings) → 输出 (Output):
 +录像格式: mp4
 +编码器: x264 (软件) 或 NVENC (硬件, 有 N 卡)
 +码率:5000 kbps
 + 分辨率:1920x1080
 +帧率:30 fps

设置 (Settings) →视频 (Video):
 +基础分辨率:1920x1080
 + 输出分辨率:1920x1080
```

**热键**：
- `Ctrl+Shift+R` → 开始/停止录制（默认）
- 或在「设置 → 热键」自定义

###备选：Win11 Xbox Game Bar（省事）

- `Win+G`打开 Game Bar
- 点捕获按钮（或 `Win+Alt+R` 直接录）
-优点：免装；缺点：不能选窗口 / 不能改码率 / 不能接外接麦克风

###备选：FFmpeg（脚本化）

```bash
#录屏命令（OBS 起不来时备选）
ffmpeg -f gdigrab -framerate30 -i desktop ^
 -c:v libx264 -preset fast -b:v5000k ^
 -pix_fmt yuv420p ^
 docs/demo_raw.mp4
# Ctrl+C停止
```

---

##2.录制前 Checklist（必跑）

###2.1 环境自检（推荐做）

```powershell
# 在项目根目录
.venv\Scripts\python.exe -c "from src.utils.face_helper import ensure_models; print('OK')"
.venv\Scripts\python.exe -c "from src.db import init_db; init_db(); print('OK')"
```

###2.2 数据准备（一键 seed + 清场）

```powershell
# 清掉测试残留 +演示账号（保留 demo_student / teacher01 / labadmin01 / admin01）
.venv\Scripts\python.exe scripts\cleanup_test_users.py

# Seed演示数据：teacher01 的课程 BME201 +教室 A101 +考勤任务
.venv\Scripts\python.exe scripts\seed_demo_data.py

#验证 seed成功
.venv\Scripts\python.exe -c "from src.db import session_scope; from src.models.attendance import AttendanceTask; print('任务数:', len(session_scope().query(AttendanceTask).all()))"
```

期望输出：`任务数:1`

###2.3演示账号（按 CLAUDE.md + W12 fixture保留）

|账号 |密码 |角色 |用途 |
|---|---|---|---|
| `demo_student` | `123456` | student |刷脸签到 |
| `teacher01` | `123456` | teacher |发起考勤 + 查看签到 |
| `labadmin01` | `123456` | lab_admin | 人脸管理 |
| `admin01` | `123456` | lab_admin | 人脸管理（备用） |

> ⚠️ 如果某个账号不在，先在 GUI 注册窗手动建一个再录

###2.4视觉清场

- [] 关闭浏览器 /微信 / IDE（避免弹通知）
- [] 关闭 Windows通知（设置 → 系统 →通知 → 关）
- [] 桌面壁纸换成纯色 / 项目 LOGO（避免敏感信息）
- [] 把屏幕分辨率调成1920×1080（录制尺寸一致）
- [] PyCharm / VSCode 等 IDE 全关（不留历史文件暴露）
- [] 时间显示关（避免时钟跳）

###2.5摄像头与灯光

- [] 摄像头：物理摄像头或笔记本内置都行，**先在「相机」应用里确认能开**
- [] 灯光：正脸打光（不要逆光），背景纯色最佳
- [] **关闭其他用摄像头的程序**（Zoom / Teams /钉钉）

###2.6 GUI启动测试

```powershell
# 项目根目录
python -m src.main
```

期望看到：
-登录窗弹出（深藏青色 + 主按钮蓝）
- 控制台 log：`=== 应用启动 ===` → `数据库初始化完成` → `人脸编码缓存预热完成: N 个用户` → `dlib 模型路径 OK`
- **第一次启动会下载 dlib 模型**（2 个 .dat 各 ~95 MB），确保提前下完

---

##3.录制步骤（4:30 标准版）

> **节奏**：每个步骤给旁白稿留 ~5-10s缓冲，操作太快/太慢都重录
> **标记**：🎬 = 开始录这一步 / ⏹ =停一下说旁白 / ✅ = 这步完成

### ⏱ 分段方案（Win11截图工具方案必看）

截图工具单段 **~3 分钟**限制，4-5 分钟 demo 必须分 **2段**录。

**段 A (~2:30)** -启动 + 学生：
- Step1启动 GUI（0:00-0:30）
- Step2 学生注册（0:30-1:30）
- Step3 人脸采集（1:30-2:15）
-缓冲黑场（2:15-2:30）

**段 B (~2:30)** - 教师 +总结：
- Step4 教师发考勤（2:30-3:15）
- Step5 学生刷脸签到（3:15-4:00）
- Step6 教师查看（4:00-4:15）
- Step7管理员人脸管理（4:15-4:45）
- Step8总结（4:45-5:00）

**段间过渡技巧**：
-段 A结尾：最小化 PyQt5窗口 →桌面状态 → 等2s → 点停止
-段 B开头：从桌面 →重新最大化 PyQt5窗口 → 开始 Step4
- 这样两段衔接看起来像"切镜头"，不突兀
-后期 FFmpeg 加 `xfade` 转场会更丝滑（见后处理）

### Step1 —启动 GUI +登录窗展示（0:00-0:30）

```
🎬 [开始录制] 
✅启动: python -m src.main
⏹旁白: "这是智能考勤与实验室准入系统, 基于 PyQt5 + dlib + MySQL"
✅登录窗显示（停留3s 让画面稳定）
⏹旁白: "支持三种角色登录: 学生、教师、实验室管理员"
```

### Step2 — 学生注册流程（0:30-1:30）

```
✅ 点 "注册" → 进 register_window
✅填表:
 用户名: demo_student
密码:123456
姓名:演示学生
 学号:20230101
角色: 学生
✅ 点 "提交注册" →提示 "注册成功"
⏹旁白: "密码用 bcrypt12 rounds哈希,不会明文存储"
✅退出注册窗 → 回登录窗
✅填 demo_student /123456 →登录
⏹旁白: "登录后按 role字段自动路由到学生窗口"
```

### Step3 — 学生人脸注册（1:30-2:15）

```
✅ StudentWindow弹出（Tab1 默认显示）
⏹旁白: "Tab1 是人脸注册,摄像头开启后会采集30 张多角度照片"
✅ 点 "📷 开始采集" →弹 FaceCollectDialog
✅摄像头预览出现（让画面显示人脸2s确认能识别）
⏹旁白: "用 dlib HOG 检测人脸位置, CNN提取128维特征向量"
✅进度条增长 → 等采到30 张
⏹旁白: "30 张是单轮目标,包含正脸、侧脸、微笑、戴眼镜等多种角度"
✅提示 "采集完成" → 关 dialog
```

> ⚠️ 这一步是**视频最易卡壳的环节**：
> -摄像头没开 → 检查 `cv2.VideoCapture(0)` 后端（MSMF优先）
> -进度条不动 → 检查 `face_helper.face_locations` 返回（可能脸太小 /逆光）
> -30 张只采几张 → 检查 worker锁是否独占（参考 W12 fix）
>
>建议**先录一遍试拍**，确认流畅再录正式版

### Step4 — 教师发起考勤（2:15-3:00）

```
✅退出 demo_student账号
✅登录窗输入 teacher01 /123456 / 教师 →登录
⏹旁白: "教师 Tab1发起考勤, 自动列出教师名下的课程"
✅ 点 "发起考勤"按钮 →弹 CreateTaskDialog
✅课程下拉选 "BME201 生物医学工程导论"
✅教室下拉选 "A101"
✅ 开始时间: 当前时间 +5min
✅结束时间: 当前时间 +30min
✅ 点 "开始考勤" →任务 status='open'，提示成功
⏹旁白: "考勤任务在 attendance_task 表插入一条 open状态记录"
```

### Step5 — 学生刷脸签到（3:00-3:45）

```
✅退出 teacher01
✅登录 demo_student → 进 StudentWindow
✅切到 Tab2 "刷脸签到"
✅任务下拉选中刚才教师发的任务
⏹旁白: "系统遍历所有学生的 face_encoding, 用欧氏距离比对"
✅ 点 "开始识别" →摄像头开启
✅ 正脸对准摄像头（2-3s）
✅状态变绿 "✅签到成功，匹配距离 ~0.35"
⏹旁白: "签到时间 <=任务开始+10min判 present,之后判 late"
```

### Step6 — 教师查看签到（3:45-4:15）

```
✅退出 demo_student
✅登录 teacher01 → 进 TeacherWindow
✅切到 Tab2 "历史考勤"
✅找到刚才的任务 → 双击 →弹 TaskDetailDialog
✅看到 demo_student状态 = "✅ 出勤" +匹配距离
⏹旁白: "教师可以查看每位学生的签到详情, 含时间、距离、状态"
```

### Step7 —管理员人脸管理（4:15-4:45）

```
✅退出 teacher01
✅登录 labadmin01 → 进 AdminWindow
✅切到 Tab5 "👤 人脸管理"
⏹旁白: "管理员 Tab5 可以查看所有注册人脸, 一键删除某个用户的所有数据"
✅列表里找到 demo_student（30 张）
✅ 点 "🗑 删除" →二次确认 → busy cursor → 删除完成
```

### Step8 —总结页（4:45-5:00）

```
✅切到 README.md（用 VSCode / notepad打开）
⏹旁白（最后一段）:
 "项目总计12 张表、106 个单元测试、4 个 smoke脚本,
修复44 个 bug, PyInstaller打包380 MB 可双击启动"
⏹ [结束录制]
```

---

##4.旁白稿（纯文本）

完整版见 `docs/demo_narration.md`，按时间戳分段，方便：
- 你照着念（如果以后要配音）
-剪映 / Pr 直接导入做字幕

---

##5.字幕文件

SRT格式见 `docs/demo_narration.srt`，直接拖进剪映 / Premiere 自动同步时间。

---

##6. 后处理

###6.1 FFmpeg拼接（如分段录制）

####6.1.1基础拼接（Win11截图工具方案，最常用）

```bash
# concat.txt写入两段文件路径
cat > concat.txt <<EOF
file 'segment_A.mp4'
file 'segment_B.mp4'
EOF

#拼接（重编码兼容性最好，避免codec不一致报错）
ffmpeg -f concat -safe0 -i concat.txt ^
 -c:v libx264 -crf23 -preset slow ^
 -c:a aac -b:a128k ^
 docs/demo_raw.mp4
```

> ⚠️ 不要用 `-c copy`，截图工具和某些编码器输出格式可能有差异，copy 会导致拼接失败 /音画不同步。重编码稳一点。

####6.1.2 加xfade转场（让段间衔接更丝滑）

```bash
# 两段之间加0.5s淡入淡出（需知道段A 时长，例如150s）
ffmpeg -i segment_A.mp4 -i segment_B.mp4 ^
 -filter_complex "xfade=transition=fade:duration=0.5:offset=150" ^
 -c:v libx264 -crf23 ^
 docs/demo_raw.mp4
```

> 用之前先查段 A 时长：`ffprobe segment_A.mp4 | grep Duration`，把 `offset`改成实际秒数。

####6.1.34段拼接（备用，如果需要分更多段）

```bash
cat > concat.txt <<EOF
file 'segment_01.mp4'
file 'segment_02.mp4'
file 'segment_03.mp4'
file 'segment_04.mp4'
EOF

ffmpeg -f concat -safe0 -i concat.txt ^
 -c:v libx264 -crf23 -preset slow ^
 -c:a aac -b:a128k ^
 docs/demo_raw.mp4
```

###6.2 加字幕（硬烧）

```bash
# SRT字幕硬烧进视频（不可关闭）
ffmpeg -i demo_raw.mp4 -vf "subtitles=demo_narration.srt" ^
 -c:v libx264 -preset fast -crf23 ^
 -c:a copy ^
 docs/demo.mp4
```

###6.3软字幕（可选切换）

```bash
#软字幕（播放器可关）
ffmpeg -i demo_raw.mp4 -i demo_narration.srt ^
 -c:v copy -c:a copy -c:s mov_text ^
 docs/demo.mp4
```

###6.4压缩（小于200 MB）

```bash
# CRF23视觉无损，文件减小到 ~150 MB
ffmpeg -i demo_raw.mp4 -c:v libx264 -crf23 -preset slow -c:a aac -b:a128k docs/demo.mp4
```

###6.5 加片头片尾（可选）

用剪映 / Premiere：
- 片头（0:00-0:05）：项目名 +课设 +团队
- 片尾（4:55-5:00）：GitHub链接 /致谢

---

##7.验收清单（输出前自检）

| # | 检查项 |期望 |
|---|---|---|
|1 |视频时长 |4:30-5:00 |
|2 | 分辨率 |1920×1080 |
|3 | 文件大小 | <200 MB |
|4 |完整业务流 |登录→注册→录脸→发考勤→签到→查看→管理 全跑通 |
|5 |旁白 /字幕 | 与画面时间对齐 |
|6 | 无明显卡顿 / 黑屏 | 全程流畅 |
|7 | 无敏感信息（密码除外） |桌面 /浏览器 / IDE 已清空 |
|8 |字幕文件 |同步准确 |

---

##8.应急 Plan B

###8.1摄像头失败

- **症状**: FaceCollectDialog 黑屏 /30 张只采几张
- **应急**:录屏时**手动**演示登录 + 教师端流程，跳过学生录脸 /签到
- **替代素材**: 用 `scripts/smoke_real_face.py`跑一遍截屏作为录脸证据

###8.2 MySQL 连不上

- **症状**:启动后 `数据库错误`弹窗
- **应急**: 检查 `.env` 中 `DB_PASSWORD`，确认 MySQL 服务在跑
- **录制前**: `python -c "from src.db import session_scope; print('OK')"`验证

###8.3 dlib 模型没下完

- **症状**:第一次启动卡在「下载模型」超过2 分钟
- **应急**: 等下载完再录（断网就放弃 Plan B）
- **预防**:录制前手动跑一遍 `python -m src.main` 让模型下完

---

##9. 输出物清单

```
docs/
├── demo.mp4 ←4-5 分钟主视频（最终交付）
├── demo_raw.mp4 ←录制原始素材（保留，可重剪）
├── demo_narration.md ←旁白稿
├── demo_narration.srt ←字幕文件
└── DEMO_RECORDING.md ← 本文件（录制脚本）
```

---

##10. 参考

- W12 plan Phase3: [`docs/superpowers/plans/2026-06-07-W12-p0-fixes-and-deliverables.md`](2026-06-07-W12-p0-fixes-and-deliverables.md)
-端到端流程参考: [`docs/MANUAL_E2E.md`](MANUAL_E2E.md)
-演示数据 seed: [`scripts/seed_demo_data.py`](../scripts/seed_demo_data.py)
-单元测试统计:106/106（`tests/`）
-打包指南: [`docs/PACKAGING.md`](PACKAGING.md)
