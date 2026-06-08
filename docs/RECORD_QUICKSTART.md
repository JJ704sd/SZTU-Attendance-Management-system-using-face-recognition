#演示视频录制 - 操作清单（精简版）

>完整脚本看 [`DEMO_RECORDING.md`](DEMO_RECORDING.md)
> 这个清单是**精简版**，按顺序执行即可完成5 分钟 demo视频

---

##1.录制前（一次性）

```powershell
#1. 清测试残留 + seed演示数据
cd D:\Attendance-Management-system-using-face-recognition
.venv\Scripts\python.exe scripts\cleanup_test_users.py
.venv\Scripts\python.exe scripts\seed_demo_data.py

#2. 关通知 / 清桌面 /调分辨率1920x1080
#3.摄像头开 + 正脸打光
```

---

##2.启动录屏（后台）

```powershell
#启动 ffmpeg 后台录屏（最长10 分钟自动停）
Start-Process -FilePath ".venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe" -ArgumentList "-f","gdigrab","-framerate","30","-i","desktop","-c:v","libx264","-preset","medium","-crf","23","-t","600","-y","docs/demo_raw.mp4","-movflags","+faststart" -WindowStyle Hidden

#验证录屏启动
Get-Process -Name "ffmpeg*" | Select-Object Name,Id,StartTime
```

---

##3.启动项目 GUI

```powershell
Start-Process -FilePath ".venv\Scripts\python.exe" -ArgumentList "-m","src.main" -WorkingDirectory "D:\Attendance-Management-system-using-face-recognition"

# 等3 秒让登录窗弹出
Start-Sleep -Seconds3
```

---

##4.按8步操作

| Step | 操作 |重点 |
|---|---|---|
|1 |登录窗展示 | 等3秒让画面稳定 |
|2 | 注册 demo_student | 用户名/密码/姓名/学号/角色填好 |
|3 | 人脸采集 | **坐过去摄像头**，采30 张 |
|4 | 教师发起考勤 | teacher01登录→课程 BME201→教室 A101 |
|5 | 学生刷脸签到 | demo_student登录→**坐过去摄像头** |
|6 | 教师查看签到 | teacher01→历史考勤→双击任务 |
|7 |管理员人脸管理 | labadmin01→Tab5删 demo_student |
|8 |总结 |切到 README.md念几句 |

---

##5.优雅停止 ffmpeg（关键！）

```powershell
# ⚠️ 不要用 Stop-Process / taskkill /F（会损坏 mp4）
# ✅ 用 taskkill 不带 /F，ffmpeg收到 WM_CLOSE优雅退出
taskkill /IM ffmpeg-win-x86_64-v7.1.exe
# 如果报错找不到进程，再试：
Get-Process -Name "ffmpeg*" | ForEach-Object { taskkill /PID $_.Id }
```

---

##6.烧字幕输出 demo.mp4

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

---

##7.验收

```powershell
Get-Item docs/demo.mp4 | Select-Object Name,Length,LastWriteTime
#期望:~30-50 MB,mp4
```

---

##常见问题

| 问题 |解决 |
|---|---|
| Stop-Process后文件 moov atom not found | **永远不要用 Stop-Process**!用 taskkill /IM(不带/F) |
| PowerShell 把 -crf23解析错 | 用上面的 Python -c 命令调 ffmpeg |
|截图工具启动不了 | 用 ffmpeg 命令行方案,不需要截图工具 |
|烧字幕命令失败 | 看 stderr,可能是 SRT路径或编码问题 |

---

##输出物

最终交付:
- `docs/demo.mp4` -5 分钟演示视频(烧字幕后)
- `docs/demo_raw.mp4` -原始录制(可保留,可重剪)
- `docs/demo_narration.srt` -SRT字幕源文件
- `docs/demo_narration.md` -旁白稿纯文本
