# 手动 E2E 验收清单

> 配合 `python -m src.main` 走完 5 步，**亲手**验证 W3 Phase 5 学生端到端能跑通。
> smoke_face.py 已自动验过采集+识别链路；本清单聚焦**真实摄像头 + 真实 UI** 的最后一公里。

## 前置

1. MySQL 8.0 已启动（127.0.0.1:3306，密码在 `.env`）
2. 已跑过 `python -m src.db init_db` 建表
3. 已跑过 `python scripts/smoke_face.py`，`demo_student` 账号已存在
4. **本机有 USB 摄像头**（笔记本自带或外接），且未被其他程序占用
5. venv 已装好依赖

```bash
# 一次性环境
pip install -r requirements.txt
python scripts/init_db.py
python scripts/smoke_face.py    # 注册 demo_student
python -m src.main              # 启动 GUI
```

## 5 步清单

### Step 1 — 注册 student 账号

> `demo_student` 已由 smoke_face.py 创建，可**直接登录**。如要手动建一个，流程如下：

1. 启动 GUI，登录窗点"注册新账号"
2. 填：
   - 用户名: `student_a` (任意)
   - 密码: `123456`
   - 真实姓名: `同学A`
   - 角色: 学生
   - 学号: `2024001`
3. 点"创建" → 看到"注册成功"

### Step 2 — 学生登录 + 人脸注册

1. 登录窗：用户名 `demo_student` / 密码 `123456` / 角色"学生" → 登录
2. 进入学生端，默认 Tab 1 "人脸注册"
3. 点"打开摄像头" → 实时预览（看到人脸有绿框）
4. 点"开始采集" → 弹采集对话框
5. **缓慢转头**（正脸/左/右/微笑/戴眼镜），进度条从 0 走到 30
6. 看到"成功采集 30 张编码" → dialog accept
7. Tab 1 状态变绿："已注册 30 张 ✓ 可去「刷脸签到」"

> 💡 如果进度条卡住：让脸正对镜头 + 光线充足；超过 30 帧无脸会超时退出。

### Step 3 — 教师端发起考勤

1. 退出当前学生端（右上"退出登录"）
2. 重新登录：用户名 `teacher01` / 密码 `123456` / 角色"教师"
   - 如未建教师账号，先在登录窗注册：`teacher01` / 123456 / 真实姓名"老师" / 角色"教师"
3. 进入教师端 Tab 1 "发起考勤"
4. 点"＋ 发起新考勤" → 弹 CreateTaskDialog
5. 课程：选任一已授课程（**注意：必须先用 DB 或测试数据建过 course 行；首次跑会显示"暂无可授课程"**）
6. 教室：选任一教室
7. 时间：默认当前时间 + 45 分钟，**改成 10 分钟内开始**（否则 sign_in_by_face 会被判定迟到）
8. 点"创建" → 看到"任务 #N 已创建"

> ⚠️ 首次跑没有 course / classroom 数据。临时方案：
> ```sql
> INSERT INTO course (course_code, course_name, course_type, teacher_id, ...)
>   VALUES ('BME201', '生物医学工程导论', '理论', <teacher01 的 user_id>, ...);
> INSERT INTO classroom (name, location, has_camera) VALUES ('A101', '教学楼A栋', 1);
> ```

### Step 4 — 学生端刷脸签到

1. 退出教师端，重新登录 `demo_student` / `123456` / 学生
2. 切到 Tab 2 "刷脸签到"
3. 任务下拉：选刚才创建的 open 任务
4. 点"打开摄像头" → 实时预览
5. 点"开始签到" → 状态变"签到中..."
6. **正对摄像头**（500ms 抓一帧） → 看到状态变绿"签到成功！HH:MM:SS - 状态: present"
7. 弹"签到成功"对话框 → 确定

> 💡 偶尔会先识别到他人（陌生脸不在 cache 里，距离 > 阈值），多等一两秒即可。

### Step 5 — 教师端验证签到记录

1. 退出学生端，重新登录 `teacher01` / 教师
2. Tab 2 "历史考勤" → 选中刚才那个任务
3. 点"查看签到详情" → 弹 TaskDetailDialog
4. **看到 `demo_student` 状态 = ✅ 出勤** + 匹配距离（约 0.3-0.4）+ 签到时间

🎉 端到端通了。

---

## 不通过怎么办？

| 现象 | 排查 |
|---|---|
| 启动 GUI 弹"数据库错误" | 检查 `.env` 里 `DB_PASSWORD`；MySQL 服务是否启动 |
| 摄像头打不开 | 设备管理器看摄像头；其他程序（Zoom/Teams）是否占用 |
| 进度条卡死 30 帧 | 光线太暗 / 脸偏离画面 / 戴口罩（dlib 口罩脸识别率低） |
| 签到一直"识别中..." | `demo_student` 的编码没存上（Step 2 失败）→ 看 `dataset/face_images/{user_id}/` 有 30 个 jpg 没 |
| 签到时弹"已签到" | 同任务已签过，刷新任务下拉换一个 |
| 距离特别大（>0.6） | 光线/角度差异大；多采几轮提高识别率 |
| 教师端没课程可选 | DB 里 course 表为空，先 INSERT 几条（见 Step 3 警告） |

## 不在范围内的功能

- ❌ **管理员端**（W4 接入）
- ❌ **课程出勤率报表**（W4 matplotlib）
- ❌ **课程选课表**（W4 加 course_enrollment；当前 close_task_and_mark_absent 简化为"role=student 的所有用户"）
- ❌ **PyInstaller 打包**（W5）
