#演示视频录制 - 按时间线一步步照做

> 每个步骤给出精确的键位、文本、点击位置。照着做就行,不用想。
>
> 如果某步出错,看「应急方案」小节。

---

##0.前置（一次性,5 分钟）

###0.1打开 PowerShell

```
Win+X → Windows PowerShell
```

###0.2进入项目目录

```powershell
cd D:\Attendance-Management-system-using-face-recognition
```

###0.3清测试残留 + seed演示数据

```powershell
.venv\Scripts\python.exe scripts\cleanup_test_users.py
.venv\Scripts\python.exe scripts\seed_demo_data.py
```

###0.4视觉清场

- [] 关闭微信/浏览器/IDE
- [] 桌面壁纸换成纯色（避免敏感信息）
- [] 屏幕分辨率设成 **1920×1080**
- [] 时间显示关
- [] 摄像头开（**正脸打光**,背景纯色最佳）

###0.5环境自检（可选,出问题再跑）

```powershell
#验证 dlib 模型就绪
.venv\Scripts\python.exe -c "from src.utils.face_helper import ensure_models; print('dlib OK')"

#验证 MySQL 连通
Get-Service MySQL80 | Select-Object Name,Status
```

---

##1.启动后台录屏（1 秒）

```powershell
Start-Process -FilePath ".venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe" -ArgumentList "-f","gdigrab","-framerate","30","-i","desktop","-c:v","libx264","-preset","medium","-crf","23","-t","600","-y","docs/demo_raw.mp4","-movflags","+faststart" -WindowStyle Hidden
```

**验证**：
```powershell
Get-Process -Name "ffmpeg*" | Select-Object Name,Id,StartTime
#期望看到1 行:PID + StartTime
```

---

##2.启动 GUI（3 秒）

```powershell
Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m","src.main" -WorkingDirectory "D:\Attendance-Management-system-using-face-recognition"
Start-Sleep -Seconds3
```

**验证**：登录窗弹出（标题"智能考勤与实验室准入系统"）

---

##3.按8步操作 GUI

###Step1 -登录窗展示（0:00-0:30）

| 操作 |动作 |
|---|---|
|鼠标 |切到登录窗（Alt+Tab 或点任务栏图标）|
|等待 |3 秒,让画面稳定 |
| ❌ 不需要操作 | 只是展示 |

---

###Step2 - 注册 demo_student（0:30-1:30）

1. 点击 **「注册」按钮**（在登录窗底部）
2. 进入「注册」对话框后,按以下顺序填写：

|字段 | 输入 |
|---|---|
| 用户名 | `demo_student` |
|密码 | `123456` |
|姓名 | `演示学生` |
| 学号 | `20230101` |
|角色下拉 |选「学生」 |

3. 点击 **「提交注册」**
4.看到提示「注册成功」 →关闭注册窗
5.回到登录窗,确认输入框已有 `demo_student` / `123456` / 学生
6. 点击 **「登录」**

---

###Step3 - 人脸采集（1:30-2:15）

> ⚠️ **这一步必须人到摄像头前!**

1. 进入学生窗口后,**默认显示 Tab1「人脸注册」**
2. 点击 **「📷 开始采集」**按钮
3.弹窗「人脸采集」对话框
4. **坐过去摄像头前**,正脸对准
5. 系统自动检测 +提取特征,进度条会增长
6. 等进度到 **30 张**,提示「采集完成」
7.关闭对话框

**应急**：
-进度条不动 → 检查 `face_helper.face_locations` 是否返空(可能脸太小/逆光)
-提示「采集超时」 → 系统自动退出,可重新点开始

---

###Step4 - 教师发起考勤（2:15-3:00）

1.退出学生账号：**窗口右上角 X关闭**（学生窗口关闭后会回登录窗）
2. 在登录窗：
 - 用户名：`teacher01`
 -密码：`123456`
 -角色：教师
3. 点击 **「登录」** → 进入教师窗口
4. 默认显示 **Tab1「发起考勤」**
5. 点击 **「发起考勤」**按钮
6. 在弹出的「创建考勤任务」对话框：

|字段 | 选择/输入 |
|---|---|
|课程下拉 | **BME201 生物医学工程导论** |
|教室下拉 | **A101** |
| 开始时间 | **当前时间 +5 分钟** |
|结束时间 | **当前时间 +30 分钟** |

7. 点击 **「开始考勤」**
8.看到提示「任务创建成功」

---

###Step5 - 学生刷脸签到（3:00-3:45）

> ⚠️ **这一步必须人到摄像头前!**

1.关闭教师窗口 →回到登录窗
2.登录：
 - 用户名：`demo_student`
 -密码：`123456`
 -角色：学生
3. 进入学生窗口 → **切到 Tab2「刷脸签到」**
4.任务下拉 →选刚才教师发的任务（BME201）
5. 点击 **「开始识别」**
6. **坐到摄像头前**,正脸对准 ~10 秒
7.状态变绿：「✅签到成功,匹配距离 ~0.35」

---

###Step6 - 教师查看签到详情（3:45-4:15）

1.关闭学生窗口 →回到登录窗
2.登录 `teacher01` / `123456` / 教师
3. 进入教师窗口 → **切到 Tab2「历史考勤」**
4.列表中找到刚才 BME201 的任务（按时间倒序第一个）
5. **双击**该任务 →弹出「任务详情」对话框
6.看到 `demo_student`状态 = **「✅ 出勤」** +匹配距离 +签到时间
7.关闭详情窗

---

###Step7 -管理员人脸管理（4:15-4:45）

1.关闭教师窗口 →回到登录窗
2.登录：
 - 用户名：`labadmin01`
 -密码：`123456`
 -角色：实验室管理员
3. 进入管理员窗口 → **切到 Tab5「👤 人脸管理」**
4.列表中找到 `demo_student`（30 张）
5. 点击该行 → **「🗑 删除」按钮**
6.二次确认弹窗 → 点 **「确定」**
7. busy cursor 转一下 → 删除完成
8. demo_student 从列表消失

---

###Step8 -总结（4:45-5:00）

1.关闭管理员窗口
2.打开 VSCode/记事本,加载项目根目录的 `README.md`
3.滚动到「项目概述」段,让画面稳定10 秒

---

##4.优雅停止 ffmpeg（关键!）

```powershell
# ✅正确方式:taskkill 不带 /F
taskkill /IM ffmpeg-win-x86_64-v7.1.exe

# 如果命令报错找不到进程,用这个备用:
Get-Process -Name "ffmpeg*" | ForEach-Object { taskkill /PID $_.Id }
```

**❌ 不要用**（会损坏 mp4）：
```powershell
Stop-Process -Name "ffmpeg*" -Force
taskkill /IM ffmpeg-win-x86_64-v7.1.exe /F
```

**验证停止成功**：
```powershell
Get-Process -Name "ffmpeg*" -ErrorAction SilentlyContinue
#期望:无输出
```

**验证文件存在**：
```powershell
Get-Item docs/demo_raw.mp4 | Select-Object Name,Length,LastWriteTime
#期望:看到文件名 + ~30-50 MB
```

---

##5.烧字幕输出 demo.mp4（2-3 分钟）

在 PowerShell跑下面这段（**直接整段复制粘贴**）：

```powershell
.venv\Scripts\python.exe -c "
import subprocess
from pathlib import Path
ffmpeg = str(Path('.venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe').resolve())
cmd = [
 ffmpeg, '-y',
 '-i', 'docs/demo_raw.mp4',
 '-vf', 'subtitles=docs/demo_narration.srt',
 '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
 '-c:a', 'aac', '-b:a', '128k',
 'docs/demo.mp4',
]
subprocess.run(cmd)
print('done. output: docs/demo.mp4')
"
```

**期望输出**：
```
... (ffmpeg progress)
done. output: docs/demo.mp4
```

---

##6.验收

```powershell
Get-Item docs/demo.mp4 | Select-Object Name,Length,LastWriteTime
```

**期望**：
- 文件名: `demo.mp4`
- 大小:30-80 MB
- 修改时间:刚才

---

##应急方案

###Q1: ffmpeg 一启动就退出
**症状**: `Get-Process -Name "ffmpeg*"` 没输出

**解决**:
1. 检查 ffmpeg路径是否正确: `Test-Path ".venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"`
2. 如果不存在,跑: `.venv\Scripts\pip.exe install imageio-ffmpeg -i https://pypi.tuna.tsinghua.edu.cn/simple`

###Q2: GUI启动后报错"数据库错误"
**症状**:弹窗「无法连接或初始化数据库」

**解决**:
1. 检查 `.env` 中 `DB_PASSWORD` 是否正确
2. 检查 MySQL 服务: `Get-Service MySQL80`
3. 如果 MySQL 没运行: `Start-Service MySQL80`

###Q3: dlib 模型没下载完
**症状**:启动卡在「下载模型」超过2 分钟

**解决**: 等下载完。模型在 `models/`目录,首次启动会从 GitHub 下载 ~190 MB。

###Q4: 人脸采集进度不动
**症状**: Step3进度条一直0/30

**解决**:
1. 检查摄像头是否被其他程序占用(Zoom/Teams/钉钉)
2.重新正脸对准,光线充足
3.关闭防火墙/代理(避免 dlib 下载失败)

###Q5:烧字幕失败（exit code异常）
**症状**: ffmpeg报错「moov atom not found」或「Invalid data」

**原因**: demo_raw.mp4损坏(被强制 kill 过)

**解决**:
1. 检查文件大小:`Get-Item docs/demo_raw.mp4`
2. 如果 <1 MB 或0字节 → **必须重录**
3. 重录时**确保**用 `taskkill /IM`不用 `Stop-Process -Force`

###Q6: PowerShell 把 `-crf23`解析错
**症状**: ffmpeg报错「Unrecognized option 'crf23'」

**解决**:永远用上面的 Python -c 命令调 ffmpeg,不要直接 PowerShell调。

---

##输出物清单

最终交付:
- `docs/demo.mp4` ← **5 分钟演示视频(烧字幕)**
- `docs/demo_raw.mp4` ←原始录制(可重剪)
- `docs/demo_narration.srt` ← SRT字幕源文件
- `docs/demo_narration.md` ←旁白稿纯文本

完整流程参考:
- [`DEMO_RECORDING.md`](DEMO_RECORDING.md) ←完整录制脚本(工具对比 + Checklist)
- [`RECORD_QUICKSTART.md`](RECORD_QUICKSTART.md) ←精简版清单
