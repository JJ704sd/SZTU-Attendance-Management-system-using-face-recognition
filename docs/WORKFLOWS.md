# 三大典型业务流程

## 流程 1：学生人脸注册

```
[PyQt5 采集窗口] 打开摄像头
    │
    ├─ 循环抓帧 (OpenCV VideoCapture.read)
    │      │
    │      └─ face_helper.face_locations 检测
    │            │
    │            ├─ 0 张脸 → 显示提示 "请正对摄像头"
    │            └─ ≥1 张脸 → 计数 +1
    │
    ├─ 累计采集 30 张（多角度：正脸/左/右/微笑/戴眼镜）
    │      │
    │      └─ face_helper.face_encodings 提取 128 维向量
    │
    ├─ 保存原始图像到 ./dataset/face_images/{user_id}/01.jpg ~ 30.jpg
    │
    ├─ 向量序列化为 bytes，写入 face_encoding 表（每张一条，便于后续重训）
    │
    └─ 提示 "注册成功"，关闭采集窗口
```

**关键点**：
- 30 张（参考项目是 50 张，平衡识别率与用户体验）
- 至少 1 张戴眼镜、1 张侧脸、1 张微笑
- 连续 10 帧无人脸则超时退出
- 进度条 UI 反馈，避免用户以为卡死

## 流程 2：课堂/实验课考勤

```
[教师端] 创建考勤任务
    ├─ 选择课程（自动带出课程类型：理论/实验）
    ├─ 选择教室
    ├─ 设置起止时间（默认 45 分钟，可改）
    └─ [开始考勤] → attendance_task 表插入一条，status='open'

[签到阶段] 学生到达教室
    │
    ├─ 摄像头开启（教室电脑或学生自带）
    │      │
    │      └─ 实时抓帧 (每 200ms 一帧)
    │
    ├─ 检测人脸 → 编码 → 与所有 student 角色的 face_encoding 比对
    │      │
    │      └─ 欧氏距离 < 0.45 视为同一人，取距离最小者
    │
    ├─ 查 attendance_record：该 student_id + task_id 是否已有记录
    │      │
    │      ├─ 已有 → 跳过
    │      └─ 无 → 插入
    │            │
    │            ├─ sign_in_time <= start_time + 10min → status='present'
    │            └─ sign_in_time >  start_time + 10min → status='late'
    │
    └─ 持续识别直到 end_time

[收尾阶段] 任务 end_time 到达
    ├─ 任务 status 置 'closed'
    ├─ 遍历课程学生名单，对未签到者
    │      ├─ 有 leave_request 审批通过 → status='leave'
    │      └─ 无 → status='absent'
    └─ 教师端弹 "考勤完成" 通知
```

**代签防御**：
- 连续 3 帧识别为同一人才确认
- 阈值 0.45 现场可调（演示时可调到 0.6 看误识，再调回 0.45 看正确）
- 同一任务同一学生只记一次

## 流程 3：实验室准入（差异化亮点）

```
[学生到达实验室门口] 摄像头开启
    │
    ├─ 检测人脸 → 识别身份 → 得到 user_id
    │
    ├─ 查询 user 表：role='student' 且 student_id 有效
    │
    ├─ 查询该实验室的 safety_level（1-5）
    │
    ├─ 查询 lab_training：该 user_id + lab_id + 培训类型
    │      │
    │      ├─ 不存在记录
    │      │      └─ 拒绝：reason="未完成{培训类型}安全培训"
    │      │
    │      ├─ 存在但 expiry_date < today
    │      │      └─ 拒绝：reason="安全培训已过期，请重新培训"
    │      │
    │      └─ 存在且有效
    │            │
    │            ├─ 培训类型与 safety_level 不匹配
    │            │      └─ 拒绝：reason="培训类型不匹配该实验室等级"
    │            │
    │            ├─ safety_level >= 4 且 score < 90
    │            │      └─ 拒绝：reason="高等级实验室要求分数≥90"
    │            │
    │            └─ 全部通过
    │                  └─ 放行：granted=1
    │
    └─ 无论结果都写入 lab_access_log（审计追溯）
```

**安全等级规则**：

| 等级 | 示例 | 前置要求 |
|---|---|---|
| 1 | 普通机房/嵌入式实验室 | 无 |
| 2 | 生物医学仪器实验室 | 设备类培训 score≥80 |
| 3 | 生物医学检测实验室 | 生物类培训 score≥80 |
| 4 | 化学/生化实验室 | 化学类培训 score≥85 |
| 5 | 辐射/特殊实验室 | 辐射类培训 score≥90 + 教师审批 |

**演示效果**：
- 注册 1 个学生 + 录入 1 条培训记录 → 准入通过
- 把培训记录改成过期 → 准入拒绝
- 改培训分数 < 90 但实验室 level=5 → 准入拒绝
- 现场能展示 3 种通过/拒绝分支（加分亮点）

## 流程 4（辅助）：报表生成

```
[教师/管理员端] 选择报表类型 + 时间范围
    │
    ├─ 学生出勤率排行（柱状图）
    │      └─ SQL: GROUP BY student_id, AVG(status IN ('present','late'))
    │
    ├─ 班级出勤率趋势（折线图）
    │      └─ SQL: GROUP BY DATE(sign_in_time), course_id
    │
    ├─ 实验室使用率热力图
    │      └─ SQL: GROUP BY lab_id, HOUR(access_time)
    │
    └─ 缺勤预警名单（表格）
           └─ SQL: 出勤率 < 80% 的学生
```
