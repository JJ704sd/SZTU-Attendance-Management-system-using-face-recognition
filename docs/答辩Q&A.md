# 智能考勤与实验室准入系统 — 答辩 Q&A 完整版

> 基于 `db/schema.sql` + `db/migration_w13.sql` + `db/migration_w14.sql` + 8 个核心 service/dao/model 真实代码反推。
> 课程性质:**数据库原理课程设计**,所以数据库设计/事务/SQL 相关问题权重最大。
> **答辩前 24 小时必背**:一(全)、二(全)、三(全)、四(选背 16/17/20)、五(24/25)。

---

# 第一部分:高频题完整答案(20 道)

---

## 一、数据库设计(8 道,最高优)

---

### Q1. 请画出系统的 ER 图,核心实体有哪些?它们之间是什么关系?

**完整答案**:

系统有 14 张表,可以按 5 条业务线归类核心实体:

| 业务线 | 实体 |
|---|---|
| **身份** | `user`(三类角色统一表) |
| **课程/教学** | `course` / `classroom` / `course_enrollment` / `course_teacher`(W14+) |
| **人脸** | `face_encoding` |
| **考勤** | `attendance_task` / `attendance_record` / `leave_request` / `task_signin_code`(W13+) |
| **实验室** | `laboratory` / `lab_training` / `lab_access_log` |
| **审计** | `login_attempt` |

**核心关系**:
- `user` ←N:1→ `course`(teacher_id,主讲)、`user` ←N:1→ `attendance_task`(teacher_id,发起者)
- `course` ←1:N→ `attendance_task`、`attendance_task` ←1:N→ `attendance_record`
- `user` ←M:N→ `course`(学生),通过 `course_enrollment` 中间表
- `course` ←M:N→ `user`(W14 多教师),通过 `course_teacher` 中间表
- `user` ←1:N→ `face_encoding`(每人多条,`is_primary=1` 标主图)
- `user` ←1:N→ `attendance_record`(学生维度查询)
- `attendance_task` ←1:N→ `leave_request`(同任务的请假)
- `user` ←1:N→ `lab_training`、`laboratory` ←1:N→ `lab_training`
- `user` ←1:N→ `lab_access_log`、`laboratory` ←1:N→ `lab_access_log`
- `user` ←1:N→ `login_attempt`(独立审计,无 FK 到 user,因为失败时 user 可能还不存在)

**关系强度**:
- 强依赖(必须有父):`attendance_task → course/user/classroom`、`attendance_record → attendance_task/user`、`leave_request → attendance_task/user`、`lab_training → user/laboratory`、`lab_access_log → laboratory`
- 弱依赖(可空):`lab_access_log.student_id` 可空(刷脸失败时 user 可能未识别)
- 多对多:`course ↔ user(学生)→ course_enrollment`、`course ↔ user(教师)→ course_teacher`

---

### Q2. 这 14 张表的设计遵循了哪些范式?有没有刻意违反范式的情况?

**完整答案**:

**主体遵循 3NF**(每个非主属性既不部分依赖也不传递依赖于主键)。

举例验证 3NF:
- `attendance_record(id, task_id, student_id, sign_in_time, status, match_score, signin_method, face_image)` — 主键 id,所有非主属性都直接依赖 id;没有"student_name → 课程名"这种传递依赖
- `face_encoding(id, user_id, encoding, image_path, is_primary, created_at)` — 没有"user_name → encoding"这种冗余

**主体也满足 BCNF**:每个决定因素都是候选键(没有"非主属性决定其他非主属性"的情况)。

**唯一合理的"反范式"考虑**:
- `attendance_record.face_image` 存的是**路径**而不是 BLOB — 这是垂直拆分的合理延伸,不属于反范式(图片本身就不应该进 RDBMS)
- `user` 表同时有 `username` 和 `student_id` 都 UNIQUE — 它们语义不同:username 是登录账号,student_id 是学号,业务上独立
- `task_signin_code` 表**没有** UNIQUE 约束(虽然 `code_value` 业务上唯一) — 故意保留多条历史码供审计/排错("学生说签到失败,我看看码是什么")

**没有触发器、没有存储过程**:业务逻辑全部在 `src/services/*.py` 维护,数据库只做"存和查"。这保证业务可单测、可追溯、版本可控(git 管 Python 比管 MySQL DDL 容易)。

---

### Q3. 为什么用 `user` 一张表统一三类角色(学生/教师/管理员),而不是拆成 3 张表?

**完整答案**:

**选择单表 + role 枚举**(`role ENUM('student','teacher','lab_admin')`)的 3 个原因:

1. **减少 JOIN**:登录、权限校验、跨角色查询只需要查一张表。14 张表里有 9 张外键引用 `user(id)`,如果拆表就要带 `student_id` / `teacher_id` / `admin_id` 三个字段,所有 FK 关系都要重新设计。
2. **现实场景**:管理员也可能登录客户端、可能临时承担教师职责(比如"教师请假,管理员代课");三类角色在用户管理界面上是统一列表,拆表要 union 3 次。
3. **扩展性**:如果未来加新角色(比如"实验室助理"),只需要扩 ENUM,不用动表结构。

**代价**:
- 业务层要 `if user.role == "student"` 多一层判断 → 我们用 `src/constants.py` 里的 `ROLE_STUDENT` / `VALID_ROLES` 常量集中维护
- 某些字段只对某角色有意义(比如 `student_id` 只对学生必填) → `auth_service.register()` 里 `if role == ROLE_STUDENT and not student_id: raise AuthError("学生必须填写学号")` 显式校验
- 表会有一些 NULL 字段(教师的 `student_id` 是 NULL)→ 这是 1 张表的代价,可接受

**替代方案对比**:
- **拆 3 张表** + 1 张 `account` 统一登录 → JOIN 多,审计复杂
- **继承表**(单表 `user` + 子表 `student` / `teacher` / `lab_admin`)→ 多一次 LEFT JOIN,代码复杂
- **结论**:对当前规模和业务复杂度,单表 + role 是最优解。

---

### Q4. `attendance_record` 上的 `UNIQUE(task_id, student_id)` 有什么作用?是不是冗余?

**完整答案**:

**不是冗余,是关键防线**。这个约束在 `db/schema.sql:121`:

```sql
UNIQUE KEY uk_task_student (task_id, student_id) COMMENT '同一任务同一学生只记一次'
```

业务规则:同一个考勤任务,同一个学生只能有一条记录。

**没有这个 UNIQUE 会发生什么**:
- 学生同时刷脸 + 同时输数字码(双卡顿)→ 可能产生 2 条记录
- 教师重复"结束考勤"按钮(没做幂等防护)→ 关闭时 `close_task_and_mark_absent` 会再写一条缺勤记录
- 并发场景:`_create_record` 里 `existed = s.query(...).first()` 在 SELECT 之后 INSERT 之前有 race 窗口,两个事务都看到"没签到" → 都 INSERT → 2 条记录

**有 UNIQUE 之后**:
- 应用层: `_create_record`(`src/services/attendance_service.py:104-109`)提前查 `existed`,友好返 None,UI 提示"已签到"
- 数据库层:即使应用层漏检 / race,第二次 INSERT 会被 `IntegrityError` 拦截,`s.rollback()` 回滚,**绝对不可能出现重复记录**

**应用层 + 数据库层双层防护是工业实践**:不要相信"应用层一定查过了",要相信"数据库是最后一道真理"。

---

### Q5. 你建了哪些索引?为什么是这些?有没有建了却没用上的?

**完整答案**:

14 张表里的关键索引(`db/schema.sql` 全文搜索 "INDEX\|UNIQUE KEY"):

| 索引 | 表 | 作用 | 业务场景 |
|---|---|---|---|
| `idx_role` | user | 按角色过滤 | 管理员查"所有学生"、教师查"我教的课的学生" |
| `idx_student_id` | user | 学号反查 | 学生忘记 username 用学号登录 |
| `username` UNIQUE | user | 登录查 user | `find_by_username` |
| `idx_user` | face_encoding | 查某用户所有编码 | 加载 _FaceCache |
| `idx_primary` | face_encoding | (user_id, is_primary) 联合 | 识别时只取主图 |
| `idx_teacher` | course | 教师查"我开的课" | 教师端首页 |
| `idx_safety` | laboratory | 按安全等级过滤 | 管理员查"所有 4-5 级实验室" |
| `idx_course_time` | attendance_task | (course_id, start_time) | 教师查"今天这节课的任务" |
| `idx_status` | attendance_task | 查 open 任务 | 学生端首页 |
| **`uk_task_student`** UNIQUE | attendance_record | 拦截重复签到 + 查"我签了没" | Q4 详细 |
| `idx_student_time` | attendance_record | (student_id, sign_in_time) | 学生查"我的考勤历史" |
| `idx_status` | attendance_record | 按状态过滤 | 报表"缺席名单" |
| **`idx_method`** | attendance_record | (task_id, signin_method) | W13+ 按签到方式统计 |
| `idx_student` | leave_request | 学生查自己的请假 | 学生端"我的请假" |
| `idx_status` | leave_request | 查 pending 待审批 | 教师端待办 |
| `idx_student_lab` | lab_training | (student_id, lab_id) | 准入检查核心查询 |
| `idx_expiry` | lab_training | 查快过期的培训 | 管理员提醒"这批学生要复训" |
| `idx_time` | lab_access_log | (access_time DESC) | 管理员查"最近准入记录" |
| `idx_lab_time` | lab_access_log | (lab_id, access_time) | 某实验室审计 |
| `idx_user_time` | login_attempt | (username, attempted_at DESC) | 防爆破查最近失败 |
| `idx_task_type_active` | task_signin_code | (task_id, code_type, is_active) | 查当前有效码 |
| `idx_expiry` | task_signin_code | 定时清理过期码(没做) | - |

**没建但 MySQL 自动建的**:
- 所有外键列(InnoDB 行为)自动有索引,不需要显式 INDEX
- 所有 UNIQUE 约束自动有索引(上面 `uk_task_student` 既是约束也是索引)

**没建冗余索引**:
- 没有"为可能用到的查询"建索引 — 只为**实际业务路径**建
- 没有"宽索引"(比如 `(a, b, c, d, e)`) — 索引越宽写入越慢,只建用得到的

---

### Q6. 哪些字段用了 ENUM?为什么?什么场景用 VARCHAR 更合适?

**完整答案**:

**用了 ENUM 的字段**:
- `user.role` (`student` / `teacher` / `lab_admin`)
- `course.course_type` (`theory` / `experiment`)
- `attendance_task.status` (`open` / `closed`)
- `attendance_record.status` (`present` / `late` / `absent` / `leave`)
- `attendance_record.signin_method` (`face` / `digit` / `qr`)
- `leave_request.status` (`pending` / `approved` / `rejected`)
- `lab_training.training_type` (`生物` / `化学` / `辐射` / `设备`)
- `task_signin_code.code_type` (`digit` / `qr`)
- `course_teacher.role` (`main` / `assistant`)

**为什么用 ENUM**:
1. **存储紧凑**:MySQL 内部用 1-2 字节整数(最多 65535 个值),比 VARCHAR 省空间 — 对 4 状态字段每行省 3-4 字节
2. **DDL 改值强制迁移**:`ALTER TABLE ... MODIFY role ENUM(...)` 会校验所有现有数据,改不了类型不一致的脏数据
3. **SQL 工具友好**:Navicat / DataGrip 显示下拉框,不容易写错
4. **可读性**:`status = 'present'` 比 `status = 1` 直观

**什么场景用 VARCHAR 更合适**:
- 取值可能动态扩展(比如 `laboratory.required_training` 用 VARCHAR 而不是 ENUM,因为培训类型可能新增"激光安全")
- 值是自由文本(`user.real_name` VARCHAR(50) 不是 ENUM('张三','李四')...)
- 长度差异大(用 ENUM 都是定长,文本差异大会浪费)

**ENUM 的坑**(主动说):
- 改 ENUM 列表要 `ALTER TABLE`,在千万级表上有锁表风险
- 不能 `ENUM('a','b') + 'c'` 渐进式加,必须一次 DDL
- 不同字符集 / collation 下 ENUM 排序可能不一致 — 我们用 `utf8mb4_unicode_ci` 统一

---

### Q7. 关于外键:全部用了外键约束吗?有没有故意不建外键的地方?级联删除怎么选的?

**完整答案**:

**全部用了外键约束**(InnoDB 引擎,14 张表里 9 张有外键)。原因:课程设计规模(几千条)FK 性能损耗可忽略,**数据一致性收益远大于性能代价**。

**外键关系全图**:

| 子表 | 外键 → 父表 | ON DELETE |
|---|---|---|
| `course` | teacher_id → user(id) | RESTRICT(默认) |
| `attendance_task` | course_id → course(id) | RESTRICT |
| `attendance_task` | teacher_id → user(id) | RESTRICT |
| `attendance_task` | classroom_id → classroom(id) | RESTRICT |
| **`attendance_record`** | task_id → attendance_task(id) | **CASCADE** |
| `attendance_record` | student_id → user(id) | RESTRICT |
| `leave_request` | student_id → user(id) | RESTRICT |
| **`leave_request`** | task_id → attendance_task(id) | **CASCADE** |
| `leave_request` | approver_id → user(id) | RESTRICT |
| `lab_training` | student_id / lab_id / instructor_id | RESTRICT |
| `lab_access_log` | student_id / lab_id | RESTRICT |
| `course_enrollment` | student_id / course_id | **CASCADE** |
| **`face_encoding`** | user_id → user(id) | **CASCADE** |
| `task_signin_code` | task_id → attendance_task(id) | **CASCADE** |
| `course_teacher` | course_id / teacher_id | **CASCADE** |
| `login_attempt.username` | (无 FK) | - |

**级联删除的选择逻辑**:

- **`face_encoding.user_id ON DELETE CASCADE`**:学生账号删除,人脸数据自动清理(隐私要求,不留死编码)
- **`attendance_record.task_id ON DELETE CASCADE`**:任务删除,记录跟着删(考勤是一次性事件,任务没了记录没意义)
- **`leave_request.task_id ON DELETE CASCADE`**:同上
- **`course_enrollment` 双 CASCADE**:学生或课程删,选课记录删(纯关联表,无独立业务价值)
- **`attendance_record.student_id` 不级联**:学生删账号,**考勤记录保留** — 审计要求(事后能查"这个学号历史上出勤过哪些课")
- **`leave_request.approver_id` 不级联**:审批人删账号,**请假记录保留** — 同上
- **`login_attempt.username` 不建外键**:**故意**!登录失败时 user 可能还不存在(被删了/从来没注册过),如果建 FK 就无法记录这种攻击尝试

---

### Q8. `face_encoding.encoding` 字段为什么是 BLOB 而不是 TEXT 或 VARCHAR?其他图片怎么存?

**完整答案**:

**`face_encoding.encoding` 用 BLOB**(`db/schema.sql:39`):
- 128 维 float32 向量 = 128 × 4 = **512 字节二进制**
- BLOB 是 MySQL 二进制大对象,直接存 bytes,**不涉及字符集转换**
- 如果用 TEXT/VARCHAR → MySQL 按 utf8mb4 编码,任何字符集调整都会破坏数据(我们后期可能切 collation)
- 序列化/反序列化用 numpy(`src/services/face_service.py:34-47`):
  - `encode_to_bytes(arr)`: `arr.astype(np.float32).tobytes()` → 512 bytes
  - `decode_from_bytes(b)`: `np.frombuffer(b, dtype=np.float32)` → 128 维向量
- 长度硬约束在 service 层:shape 必须是 `(128,)`,bytes 长度必须是 512,错了就 `ValueError`

**其他图片怎么存**:
- **人脸采集原图**:`face_encoding.image_path VARCHAR(255)` — 存**路径**,图片落文件系统 `dataset/face_images/<user_id>/<idx>.jpg`
- **签到抓拍**:`attendance_record.face_image VARCHAR(255)` — 同上
- **实验室准入抓拍**:`lab_access_log.face_image VARCHAR(255)` — 同上
- **用户头像**:`user.avatar_path VARCHAR(255)` — 同上

**为什么不把头像也存 BLOB**:
- 单张人脸图 200-500 KB,BLOB 会让 user 表单行超大
- 大行会导致:索引放不进 buffer pool(默认 16 KB)→ 退化为磁盘随机读;备份 mysqldump 慢 5-10 倍;网络传输慢
- **文件路径方案 + 文件系统**是工业实践(Nginx 静态文件、CDN 都这么做)
- **BLOB vs 文件路径** 的判断标准:**数据是不是要参与业务查询**(人脸 encoding 要算距离必须入 DB;图片只是给 UI 显示,不入 DB)

---

## 二、事务、并发、ACID(3 道)

---

### Q9. 你的事务边界在哪里?怎么保证 ACID?

**完整答案**:

**事务边界**:`src/db.py:22-33` 的 `session_scope()` 上下文管理器:

```python
@contextmanager
def session_scope() -> Session:
    s = SessionLocal()
    try:
        yield s
        s.commit()      # 正常退出 → 提交
    except Exception:
        s.rollback()    # 异常退出 → 回滚
        raise
    finally:
        s.close()        # 无论如何 → 关 session
```

**每个 service 方法 = 一个事务**。例如 `_create_record` 里的"校验 task + 校验 user + 写 record"是原子的,不会发生"task 校验通过但 record 没写"的中间态。

**A 原子性**:
- session_scope 的 `__exit__` 正常路径 `s.commit()`,异常路径 `s.rollback()`
- service 方法内多步操作在一个 `with` 块内 → 要么全成,要么全败
- `_create_record_in_session`(`attendance_service.py:190-233`)就是为数字码/二维码设计 — "码校验 + 写记录"必须在同一 session / 同一事务,否则可能发生"码校验通过 + 另一个事务抢签 + 写重复记录"虽然 UNIQUE 兜底,但日志会困惑

**C 一致性**:
- FK 约束(14 张表全部建了,见 Q7)
- UNIQUE 约束(`uk_task_student`、`username` UNIQUE、`student_id` UNIQUE)
- ENUM 约束(role / status / signin_method 只能在指定值里)
- NOT NULL 约束(主键、外键、密码哈希、创建时间都 NOT NULL)
- Python 层业务规则(USERNAME_RE 正则、密码长度、角色校验)

**I 隔离性**:
- MySQL InnoDB 默认 `REPEATABLE READ`
- SQLAlchemy session 单连接,业务层无显式锁
- 没出现"不可重复读"问题:同 session 内的 `s.get(Model, id)` 走一级缓存,跨 session 查询走连接快照

**D 持久性**:
- 依赖 MySQL 自身配置(binlog + redolog),项目用默认配置
- 单机应用,没有多节点一致性问题

**关键的反直觉细节**:`auth_service.login`(`auth_service.py:103-133`)失败分支**显式 `s.commit()` 再 raise**:
```python
attempt_dao.record_attempt(username, success=False)
s.commit()  # ⚠️ 显式提交,避免 raise 触发 rollback 抹掉记录
raise AuthError("用户名或密码错误")
```
如果不 commit,raise 触发 session_scope 退出时的 rollback → record_attempt 一起回滚 → 失败记录没写 → 防爆破永远不触发(第 5 次失败后还能继续输)。这个坑在 docstring 里专门注释了。

---

### Q10. 如果两个学生同时签到,会重复写记录吗?

**完整答案**:

**不会**,有 3 道防线:

**第一道防线:应用层提前检查**(`attendance_service.py:104-109`):
```python
existed = s.query(AttendanceRecord).filter(
    and_(AttendanceRecord.task_id == task_id,
         AttendanceRecord.student_id == user_id)
).first()
if existed:
    return None
```
学生签到前先查,发现已签到 → 返 None,UI 提示"已签到",不抛异常。

**第二道防线:数据库 UNIQUE 约束**(`db/schema.sql:121`):
```sql
UNIQUE KEY uk_task_student (task_id, student_id)
```
即使应用层漏检(或两个事务都看到"没签到"同时 INSERT),第二个 INSERT 必然报 `IntegrityError`,事务回滚,只保留一条记录。

**第三道防线:session 隔离 + race 窗口最小化**:
- 数字码 / 二维码签到走 `_create_record_in_session`(`attendance_service.py:190`)复用外层 session,"码校验 + 写记录"在一个事务里原子完成
- 刷脸签到走 `_create_record`,独立 session,但因为人脸识别本身耗时 ~200ms,这个窗口内被并发抢占的概率极低

**结论**:即使在最坏情况下(应用层 bug + race),数据库层也保证数据不重复。**数据库是最后一道真理,不要相信应用层"一定查过了"**。

---

### Q11. 签到码"覆盖式失效"怎么保证原子性?中途崩溃会怎样?

**完整答案**:

**关键代码**(`attendance_service.py:262-292`):
```python
with session_scope() as s:
    # 1) 失效同任务同类型的所有未过期有效码
    dao.deactivate_active_for_task_type(task_id, code_type)

    # 2) 生成新码
    if code_type == "digit":
        code_value = f"{random.randint(0, 9999):04d}"
    else:  # qr
        code_value = secrets.token_urlsafe(16)

    # 3) 写新码
    new_code = dao.insert_new(...)
    return {...}
```

这三步在**同一个 session_scope 里**,一起 commit,一起 rollback。不会发生"旧码失效 + 新码还没写"的中间态。

**中途崩溃会怎样**:
- **崩溃在 step 1 之后、step 3 之前** → 整个事务回滚 → 旧码依然有效(下次教师再点"生成新码"会重试,旧码被新的 deactivate 命中并失效)
- **崩溃在 step 3 之后、commit 之前** → 同上,事务回滚
- **commit 之后崩溃** → 新码生效,旧码已失效,**结果正确**
- **结论**:任何时点崩溃都不会留下"无新码但旧码已失效"的不可用状态

**数字码生成的小坑**:用 `random.randint` 而非 `secrets.randbelow`,因为 4 位数字(10000 种组合)即使被预测也无所谓(60 秒就过期),`random` 速度更快。二维码用 `secrets.token_urlsafe(16)` 128 位密码学安全随机,因为 22 字符 token 要扛住几小时有效期内被暴力枚举。

---

## 三、安全(4 道)

---

### Q12. 怎么防 SQL 注入?

**完整答案**:

**全程 SQLAlchemy 2.0 ORM,不拼字符串**。所有用户输入走参数化查询,例如 `UserDao.find_by_username(username)`(`src/dao/user_dao.py`)内部是:
```python
SELECT * FROM user WHERE username = :p1
```
绑定 `p1=username` 走 MySQL prepared statement,**用户输入永远是数据,不是 SQL**。

**为什么不留手写 SQL 的口子**:
- 14 张表的 DAO 全部走 ORM(`BaseDao` 封装 `s.add / s.query / s.filter`)
- 唯一的"手写 SQL"是 `db/schema.sql` DDL,**没有运行时拼接**
- 关键查询(用户输入敏感的)全部用 `filter(Model.field == input)`,绑定参数

**对比演示**(可以说服老师):
```python
# 错误(假设有人图省事这么写)
sql = f"SELECT * FROM user WHERE username = '{username}'"
s.execute(text(sql))
# 输入 username = "' OR '1'='1" → 整个 user 表泄漏

# 正确(项目里所有地方都是这样)
s.query(User).filter(User.username == username).first()
# 输入任何字符串都被绑定为字面量
```

**深度防御**:即使 ORM 出了漏洞,bcrypt 密码哈希(`crypto.py:9-19`)也能扛住 — 拿到 hash 也解不开明文。

---

### Q13. 密码怎么存?为什么用 bcrypt 不用 SHA-256?

**完整答案**:

**bcrypt 12 rounds**(`src/utils/crypto.py:7-19`):
```python
def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")
```

**为什么 bcrypt**:
1. **慢哈希**:`rounds=12` 意味着每次哈希 ~250ms,大幅增加暴力破解成本
2. **自带 salt**:每次 hash 不同(随机 16 字节 salt),防 rainbow table
3. **可调成本**:`rounds` 可调,硬件变强时增大 rounds
4. **工业标准**:Linux 影子密码、WordPress、Django 默认都用 bcrypt

**为什么不选其他**:
- **MD5 / SHA-1**:已被证明不够安全(碰撞攻击),且是快速哈希,GPU 一秒算几十亿次
- **SHA-256 / SHA-3**:是快速哈希(不是密码学慢哈希),不适合密码存储
- **明文**:课程要求"密码不能明文" + 任何泄漏都完蛋
- **PBKDF2 / scrypt / Argon2**:都 OK,选 bcrypt 是因为 Python 生态最成熟(`bcrypt` 库是 PyPI 主流)

**密码字段在表里是 `password_hash VARCHAR(255)`**(`schema.sql:18`):`$2b$12$...60字符...` 的格式,255 字符足够。

**登录验证**:
```python
def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```
**`checkpw` 自动从 hash 里提取 salt + rounds**,不用传额外参数。

---

### Q14. 登录防暴力破解怎么做的?为什么用 login_attempt 表?

**完整答案**:

**配置**:`LOGIN_MAX_ATTEMPTS = 5`(`src/config.py:82`)

**关键代码**(`auth_service.py:103-133`):
```python
with session_scope() as s:
    attempt_dao = LoginAttemptDao(s)
    # 1. 查最近 5 次失败次数
    recent_failures = attempt_dao.count_recent_failures(
        username, limit=Config.LOGIN_MAX_ATTEMPTS,
    )
    # 2. 达到阈值 → 直接锁定
    if recent_failures >= Config.LOGIN_MAX_ATTEMPTS:
        raise AuthError(f"账号已锁定：连续 {Config.LOGIN_MAX_ATTEMPTS} 次登录失败，")

    # 3. 校验密码
    user = user_dao.find_by_username(username)
    if not user or not verify_password(password, user.password_hash):
        attempt_dao.record_attempt(username, success=False)
        s.commit()  # ⚠️ 显式提交,避免 raise 触发 rollback
        raise AuthError("用户名或密码错误")

    # 4. 成功
    attempt_dao.record_attempt(username, success=True)
```

**为什么用 `login_attempt` 表而不是在 `user` 表加计数器**:
1. **审计独立**:能查"什么时候/从哪个 IP/失败频率"(`idx_user_time` 索引 + `ip_address` 字段)
2. **分析攻击模式**:短时间内多次失败 = 可能在暴力破解
3. **不污染主表**:`user` 表是身份表,加 `fail_count` 字段会让所有用户查询都受影响
4. **解锁不丢历史**:管理员解锁(`UPDATE user SET is_active=1`)不会清掉历史失败记录

**反直觉的坑**(`auth_service.py:99-101` docstring):
```python
# ⚠️ 关键: 失败分支在 raise 之前必须显式 s.commit(), 否则 session_scope
# 退出时的 rollback 会把 record_attempt 一起回滚, 导致锁定永远不触发。
```
**不 commit 直接 raise,记录被回滚,等于没记录 → 第 5 次失败后还能继续输**。这个坑真实踩过,W4 修过一次。

**没做**(主动说):
- 没按 IP 维度锁定(只按 username) — 攻击者换 IP 仍能继续
- 没做 CAPTCHA / 短信验证 — 课程设计范围够用
- 没做"24 小时后自动解锁" — 锁定要管理员手动解除

---

### Q15. 二维码 token 怎么生成?能伪造吗?能截图滥用吗?

**完整答案**:

**token 生成**(`attendance_service.py:279`):
```python
code_value = secrets.token_urlsafe(16)
```
- `secrets` 模块是 Python 3.6+ 密码学安全随机(基于 `os.urandom`)
- 16 字节 = 128 bit 随机
- `token_urlsafe` → base64url 编码,无 `+/=`,URL 友好
- 输出长度 22 字符(16 字节 → 22 个 base64 字符)

**能伪造吗**:
- 理论上能(随机碰撞)
- 实际不可能:**碰撞概率 < 2^-96 ≈ 10^-29**(生日攻击界 2^64)
- 整个地球每秒生成 10 亿个 token 跑到宇宙热寂也碰不到一次

**校验**(`task_signin_code_dao.py:59-73`):
```python
def find_active_by_value(self, task_id, code_type, code_value):
    return self.s.query(TaskSigninCode).filter(
        and_(
            TaskSigninCode.task_id == task_id,
            TaskSigninCode.code_type == code_type,
            TaskSigninCode.code_value == code_value,
            TaskSigninCode.is_active == 1,
            TaskSigninCode.expires_at > datetime.now(),
        )
    ).first()
```
三重过滤:task + type + value 精确匹配 + `is_active=1` + 未过期。任一不满足返 None。

**能截图滥用吗**:
- **不能**:TTL 60s + 覆盖式失效(见 Q11)
- 教师中途点"🎲 生成新码" → `deactivate_active_for_task_type` 把同任务同类型所有未过期有效码 `is_active=0` → 学生手里截图立刻失效
- 学生偷看隔壁同学手机也不行 — 每人提交自己 user_id 关联的记录,不可代签

**W15+ 修过的真实 bug**(`signin_web.py::signin_page`):H5 入口路由之前用**闭包里的 token 校验**,但 web server 启动时定死的 token 跟 DB LIVE token 永远不一致(dialog 启动会再 `_generate_code` 覆盖)。**修法**:闭包不校验 token,真实校验交给 `find_active_by_value` 实时查 DB。**教训:in-memory state(闭包/缓存)不能当真理**。

---

## 四、技术选型(4 道,选背)

---

### Q16. 为什么要分 4 层(ui / service / dao / model)?

**完整答案**:

**4 层结构**:
```
ui           (PyQt5 窗口、按钮、表单、表格)
  ↓
service      (业务规则、事务管理、跨表编排)
  ↓
dao          (SQLAlchemy ORM 封装)
  ↓
model        (表 ↔ Python 类映射)
```

**依赖方向严格自顶向下,禁止反向**。例如 `model/user.py` 不能 import `service` 或 `dao`,否则循环依赖。

**分层的实际好处**:
1. **service 可独立 mock 测试**:dao 换 in-memory 实现,service 测试不依赖 MySQL(我们 `tests/` 里有 mock dao 的用例)
2. **ui 改样式不动业务逻辑**:换 PyQt6 / 换 Web 框架,service/dao/model 都不动
3. **dao 换 ORM 不动 service**:SQLAlchemy 换 SQLObject,service 接口不变
4. **model 是数据契约**:所有人引用同一个 `User.username`,改字段名会触发所有调用方编译错误

**代价**:
- 多写一些样板代码:`with session_scope() as s: dao = XxxDao(s)` 每个方法都要
- 小项目看起来"过度设计"

**反面例子**(可以说服老师):
- 把 SQL 写在按钮 on_click 里 → 难测试、难改、SQL 注入风险、跨窗口难复用
- dao 直接被 ui 调用 → 测试 ui 必须起 MySQL
- model 持有业务逻辑 → 想换 ORM 就崩

**CLAUDE.md 里专门写了这个架构是项目硬要求,不是拍脑袋**。

---

### Q17. 为什么用 SQLAlchemy ORM,不用原生 SQL?

**完整答案**:

**4 个核心理由**:

1. **防 SQL 注入**:参数化查询,见 Q12
2. **跨数据库可移植**:`DB_URL` 一行配置切换数据库。开发测试用 SQLite,演示用 MySQL 8.0,理论上 PostgreSQL / Oracle 也能跑(我们用 MySQL 特性如 ENUM / 字符集 utf8mb4,实际锁了 MySQL)
3. **类型安全 + IDE 补全**:`User.username` 写错会报错;`User.username.desc()` 列出所有排序方向
4. **迁移友好**:`Base.metadata.create_all(engine)`(`db.py:52`)自动建表,改 model 加字段后重跑就能 ALTER

**ORM 的坑**(主动说):
- **N+1 查询**:`for u in users: for e in u.encodings` 会触发 1+N 次 SQL → 用 `joinedload` / `subqueryload` 预加载(项目里目前数据量小,N+1 不明显)
- **复杂查询性能差**:`SELECT * FROM a JOIN b JOIN c WHERE ...` ORM 写起来啰嗦,有时还不如 `s.execute(text("..."))` 走原生
- **学习曲线**:新成员要懂 `session` / `query` / `relationship` 概念

**没用 ORM 的地方**:
- `db/schema.sql` DDL(纯 SQL,ORM 帮不了)
- `db/migration_w13.sql` / `db/migration_w14.sql` 增量迁移(也是 DDL)
- `close_task_and_mark_absent` 里的 `s.query(User).filter(User.id.in_(student_ids))` 走 ORM 没问题,但如果以后要分析,可以用 SQL

**结论**:ORM 是 80/20 原则 — 80% 场景受益,20% 复杂查询必要时降级到原生 SQL。

---

### Q18. 为什么用 PyQt5 不用 Web?W14 加的 FastAPI 又是什么?

**完整答案**:

**为什么 PyQt5**:
1. **课程设计是桌面应用** + 摄像头需要本地访问(`cv2.VideoCapture(0)` 走系统 API)
2. **PyQt5 控件丰富**:QTableWidget / QFormLayout / QMessageBox / 自定义 widget 4 个主窗口都用
3. **摄像头本地**:`CameraWidget` 在工作线程跑 dlib,信号 `Qt.QueuedConnection` 跨线程更新 UI,延迟低
4. **部署简单**:PyInstaller 打包一个 `.exe` 380 MB,双击就跑,不需要 Nginx / Node / 浏览器

**Web 方案的问题**:
- 浏览器访问摄像头要 HTTPS(localhost 除外),本地 dev 体验割裂
- 离线环境不能演示
- 部署依赖多(后端服务 + 前端打包 + 反向代理)

**W14 加的 FastAPI 是什么**:
- 起因:**多端登录签到** — 教师电脑起 :5180 HTTP 服务,学生手机扫码 → 浏览器打开 H5 签到页 → 提交到 FastAPI → 教师端实时反馈
- **嵌入到 PyQt 进程,不独立跑**:`uvicorn.Server` 在 `threading.Thread(daemon=True)` 里跑,`closeEvent` 调 `srv.should_exit = True` 同步停
- 为什么不独立跑 uvicorn 进程?—— 需要管端口/启停/与 GUI 生命周期对齐,体验割裂
- 单进程统一,关窗时 H5 自动停

**FastAPI 嵌入的限制**(主动说):
- H5 必须连同一个 WiFi(局域网),跨网段要内网穿透(frp / Tailscale)
- 单进程 uvicorn 性能有限,几百并发就到顶 — 课程设计规模完全够用

---

### Q19. 为什么 dlib-bin 不是源码编译?为什么不直接用 face_recognition 库?

**完整答案**:

**为什么不用源码编译 dlib**:
- Python 3.13 + Windows + cmake 编译 dlib = 各种坑(缺 Boost、CMake 版本不匹配、几小时编译、可能失败)
- `dlib-bin 20.0.1` 是社区维护的预编译 wheel,直接 `pip install dlib-bin` 装好
- **W3 决策记录在 CLAUDE.md**:不是临时起意

**为什么不直接用 `face_recognition` 库**:
- `face_recognition 1.3.0` 的 dlib 子依赖在 `cp313`(Python 3.13)上没有 wheel
- pip install 同样会触发 cmake 编译
- **解决**:`src/utils/face_helper.py` 自写 4 个核心 API:
  - `face_locations(image)` — 人脸位置检测,`(top, right, bottom, left)` 列表
  - `face_encodings(image, known_face_locations=None)` — 128 维特征向量
  - `face_distance(face_encodings, face_to_compare)` — 欧氏距离
  - `compare_faces(known_encodings, encoding, tolerance=0.45)` — 阈值判定

**4 个 API 的接口跟 `face_recognition` 库一模一样** → 以后想换库只改 `face_helper.py` 一处,业务代码零改动。

**dlib 算法细节**:
- `_detector = dlib.get_frontal_face_detector()` — HOG 特征 + 线性分类器,CPU 快(`face_helper.py:135`)
- `_sp = dlib.shape_predictor(...)` — 68 个关键点定位(`shape_predictor_68_face_landmarks.dat`, 95 MB)
- `_facerec = dlib_face_recognition_model_v1(...)` — ResNet 34 提取 128 维向量(`dlib_face_recognition_resnet_model_v1.dat`, 22 MB)
- 单张人脸编码 ~50-100ms,识别比对 1ms

**模型下载**(`face_helper.py:42-69`):
- 首次运行时 `ensure_models()` 从 GitHub 下载 ~120 MB 到 `models/`
- **W15+ 加 gitee 镜像 fallback**:国内 GitHub raw 经常被墙,失败时自动试 `gitee.com/anyxch/dlib-models-raw`
- 失败时保留 `.bz2` 文件供重试,不会删了下次重新下 100 MB

**模型不入 git**:单文件 95 MB 接近 GitHub 100 MB 警告线,运行时下载。

---

### Q20. 为什么 face encoding 用 float32 不用 float64?用 BLOB 存有什么风险?

**完整答案**:

**float32 的 3 个理由**(`face_service.py:27-28` + `CLAUDE.md` 技术决策):

1. **dlib 内部就是 float32**:`_facerec.compute_face_descriptor()` 返回 numpy 数组,默认 dtype 是 float32
2. **存储减半**:128 × 4 = **512 字节**;float64 是 1024 字节
3. **避免量纲不一致**:numpy 2.x 默认 float64,如果不做 `arr.astype(np.float32)`,从 BLOB 读出来再算距离时 dtype 不匹配,可能触发隐式转换(慢)或 `RuntimeWarning`

**测试锁住**(`tests/test_face_helper.py`):`test_face_encodings_dtype_is_float32` 锁住这个不变量,有人不小心改回 float64 会立即挂测试。

**序列化**(`face_service.py:34-47`):
```python
def encode_to_bytes(arr: np.ndarray) -> bytes:
    if arr.shape != (128,):
        raise ValueError(...)
    return arr.astype(np.float32).tobytes()  # 512 bytes

def decode_from_bytes(b: bytes) -> np.ndarray:
    if len(b) != 128 * 4:
        raise ValueError(...)
    return np.frombuffer(b, dtype=np.float32)
```
**little-endian**(x86 默认,`tobytes()` 不指定 order),跨平台读需要确认两端都是 little-endian(几乎所有现代 CPU 都是)。

**BLOB 存的 3 个风险**(主动说):
1. **大库查询慢**:BLOB 不进 InnoDB buffer pool(`innodb_log_buffer_pool` 默认 16 KB,512 字节能进但大图不行),要走磁盘
2. **备份慢**:mysqldump 含 BLOB 会大几倍,传输慢
3. **网络开销**:跨节点复制时 BLOB 占带宽
- **我们的应对**:每用户平均 30 条 encoding(W12 决策),512 字节 × 30 = 15 KB,远小于 16 KB,全部进 buffer pool
- **扩展方向**:>1k 用户换 Redis / Faiss 向量库(`face_service.py:96` 注释 "N 大时应换 Redis")

---

## 五、业务逻辑(3 道,选背)

---

### Q21. 迟到是怎么判定的?为什么是 10 分钟?

**完整答案**:

**判定代码**(`attendance_service.py:36` + `112-113`):
```python
LATE_THRESHOLD_MINUTES = 10
...
late_cutoff = task.start_time + timedelta(minutes=LATE_THRESHOLD_MINUTES)
status = "present" if now <= late_cutoff else "late"
```

**判定规则**:
- `now() <= start_time + 10min` → `status = "present"`(准时)
- `now() > start_time + 10min` → `status = "late"`(迟到)
- `now() < start_time` → 也算 `present`(早到总比迟到好)

**10 分钟怎么来的**:
- 高校课堂通常 5-15 分钟容忍度,选中间值
- 可配置(目前是常量,放 Config 里也是一行改动)
- 跟签到方式无关:刷脸/数字码/二维码共用同一判定

**没做**(主动说):
- 早到奖励:目前 `present` 不分"早到 5 分钟"和"踩点到",如果要做 `on_time` / `early` 二级
- 教师自定义阈值:目前全局常量 10 分钟,不能让教师每个任务单独配

**3 种签到共用判定**:`_create_record` 公共核里统一调,不会有"刷脸严格 / 数字码宽松"的不一致。

---

### Q22. 缺勤记录怎么写?教师忘记关任务会怎样?

**完整答案**:

**主动关闭流程**(`attendance_service.py:297-356`):
1. `task.status = "closed"`
2. 查 `course_enrollment` 找该课学生(替代"role=student 全部",更精确)
3. 遍历学生:
   - 已签到 → 跳过
   - 请过假(`leave_request.status == "approved"`)→ 写 `status="leave"`
   - 没签到 + 没请假 → 写 `status="absent"`
4. 异常处理:`try/except IntegrityError` 跳过孤儿 user(被其他测试 fixture 删掉的)

**触发方式**:
- 教师端"结束考勤"按钮 → 调 `close_task_and_mark_absent`
- **没做**自动定时关闭(可主动说改进方向:`APScheduler` 监听 `end_time`,到了自动调)

**教师忘记关任务会怎样**:
- `attendance_task.status` 还是 `open`,学生还能继续签到(没有强制截止)
- 缺勤记录要等下次手动关,期间报表不准
- **改进方向**:加 `APScheduler` 定时任务,`end_time` 到了自动关

**无 enrollment 时的防御性降级**(`attendance_service.py:314-319`):
```python
if enrollments:
    student_ids = {e.student_id for e in enrollments}
    students = s.query(User).filter(User.id.in_(student_ids)).all()
else:
    # 防御性降级: 无 enrollment → fallback 到所有 student
    students = s.query(User).filter(User.role == "student").all()
```
旧数据 / 演示场景可能没 enrollment,直接 fallback 不挂。

**孤儿 user 防御**(`attendance_service.py:340-356`):
```python
try:
    s.add(AttendanceRecord(...))
    s.flush()
except IntegrityError:
    s.rollback()
    log.warning("close_task_and_mark_absent 跳过孤儿 student_id=%s", stu.id)
    continue
```
conftest autouse fixture 在 session 末清理测试 user,中途可能已被删,直接 INSERT 会 FK 1452。try/except 跳过避免单个孤儿把整次 close 拖挂。

---

### Q23. 实验室准入 7 种判定分支具体是哪些?

**完整答案**:

**7 种判定**(`src/services/lab_access_service.py:44-120`),按代码顺序:

| # | 分支 | 条件 | 结果 |
|---|---|---|---|
| 1 | 异常分支 | user_id 或 lab_id 不存在 | 拒绝(不写 log,因为 FK) |
| 2 | 非学生放行 | user.role != "student" | **放行** + 写 log |
| 3 | 无培训记录 | role=student + 没培训 | 拒绝 + 写 log |
| 4 | 培训过期 | role=student + 有培训但 expiry_date < today | 拒绝 + 写 log |
| 5 | 培训类型不匹配 | role=student + training_type != lab.required_training | 拒绝 + 写 log |
| 6 | 高等级分数不够 | role=student + lab.safety_level >= 4 + training.score < 90 | 拒绝 + 写 log |
| 7 | 全部通过 | 上述都不命中 | **放行** + 写 log |

**关键代码**(`lab_access_service.py:101-110`):
```python
if lab.safety_level >= 4 and training.score < 90:
    reason = (
        f"高等级实验室（safety_level={lab.safety_level}）要求分数≥90，"
        f"你的分数 {training.score}"
    )
    LabAccessLogDao(s).log_attempt(
        lab_id, granted=False, student_id=user_id, reason=reason,
    )
    return AccessResult(granted=False, reason=reason)
```

**注意 PPT 上的细节可能有偏差**:
- PPT 第 4 页说"5 级安全等级",实际代码是 `safety_level >= 4`(4 和 5 都算高等级)
- PPT 说"7 种判定分支",实际是 6 种拒绝 + 1 种放行(共 7 种结果)

**每次结果都写 `lab_access_log`**(审计追溯):granted=1/0 + reason(中文) + 时间戳,即使"非学生自由出入"也写。

**等级 → 培训类型是硬编码的**:
- 1-2 级:免培训
- 3 级:需要 + 分数 ≥ 80(隐含,没显式判定)
- 4-5 级:需要 + 分数 ≥ 90(显式判定)

**改进方向**(主动说):如果要把"等级 → 培训类型 → 分数阈值"做成可配置,需要新加一张 `level_training_rule` 表,目前是 hard-code 在 service。

---

## 六、综合 / 收尾(选背)

---

### Q24. 你的项目最大的亮点是什么?(30 秒必背)

**完整答案**:

**14 个迭代阶段 (W2-W15+)完整闭环**:
- V1.0 登录注册 → V2.0 人脸识别 → V3.0 实验室准入 → V4.0 PyInstaller 打包 → V5.0 签到方式扩展
- 不是 demo 一次成型,是真实工程迭代 14 周

**3 种签到方式共用 `_create_record` 公共核**:
- 刷脸 / 数字码 / 二维码三种方式,业务规则(迟到判定 + 重复拦截 + 角色校验)在一处维护
- 加新签到方式只需 +1 个薄方法,不动核心逻辑
- 这是 W13+ 重构的设计感,不是 3 套 if-else

**193 单元测试 + 6 个 smoke 端到端**:
- `pytest tests/ -v` 193/193 全过,~60s 跑完
- 包含 dtype Lock / 死循环 Lock / H5 API 真实 HTTP 响应测试
- smoke 端到端:full_flow / real_face / e2e / signin_methods / signin_web / audit_history

**W15+ 修过的 2 个真实 bug**:
- H5 入口路由闭包 token 永远不匹配 DB live token(已修)
- H5 polling 防缓存,教师中途刷码旧 H5 URL 不会失效(已修)
- 证明项目有真实工程迭代,不是 demo

**PyInstaller 380 MB 一键 exe**:
- 含 dlib 模型 + Python 运行时 + Qt 平台插件
- 双击启动,无依赖,跨机器演示无障碍

---

### Q25. 项目最大的不足?如果要继续做,会做什么?

**完整答案**:

**不足**(主动暴露加分):
1. **单机桌面应用**:不支持多教师协同 / 不支持移动端原生 App
2. **没用缓存层**:每次都直接查 MySQL,签到码 / 角色判断高频查询每次都打 DB
3. **报表简单**:matplotlib 4 类图,没有 BI 看板(Tableau / Superset)
4. **测试覆盖率**:覆盖业务关键路径,没追求 100%(实际 ~75%)
5. **没做 CI/CD**:GitHub Actions 自动跑测试 / 自动打包 / 部署
6. **跨平台**:dlib-bin wheel 只覆盖 Windows,Linux/macOS 部分场景要源码编译

**下一步**:
1. **加 Redis**:缓存热门数据(签到码、用户角色、人脸编码)
2. **FastAPI 独立部署**:前后端分离,前端换 Vue3 + 移动端 React Native
3. **加监控**:Prometheus + Grafana 看 QPS / 延迟 / 错误率
4. **跨平台打包**:`briefcase` 或 `Nuitka` 替代 PyInstaller,支持 macOS / Linux
5. **向量库**:>1k 用户人脸比对换 Faiss / Milvus,毫秒级响应
6. **数据仓库**:report_service 现在直接查 MySQL,数据量大了换 ClickHouse / Doris
7. **完善测试**:加 performance test(并发签到 1000 学生)、chaos test(随机 kill 进程看数据一致性)

---

# 第二部分:次频题速记(25 道,2-3 句话)

> 这部分给速记版,够用即可。

---

### S1. `task_signin_code` 表的设计细节?

`task_id` + `code_type`(digit/qr)+ `code_value`(4位/22位)+ `expires_at`+ `is_active` + `created_at`;**没有 UNIQUE 约束**,允许多条历史码共存(审计/排错用);有 `idx_task_type_active` 和 `idx_expiry` 两个索引。

### S2. 数据库的字符集和排序规则?

`utf8mb4` + `utf8mb4_unicode_ci`(schema.sql 第 9 行)。utf8mb4 支持 4 字节字符(emoji、古汉字),unicode_ci 大小写不敏感且支持多语言排序。

### S3. 14 张表里所有 ENUM 字段列举一下?

`user.role` (3 值)、`course.course_type` (2)、`attendance_task.status` (2)、`attendance_record.status` (4)、`attendance_record.signin_method` (3)、`leave_request.status` (3)、`lab_training.training_type` (4)、`task_signin_code.code_type` (2)、`course_teacher.role` (2)。

### S4. 数字码的"前导零"问题?

数字码生成 `f"{random.randint(0, 9999):04d}"`(`attendance_service.py:276`),补前导零,确保 "0123" ≠ "123"(长度都是 4)。如果用 `str(random.randint(0, 9999))`,"123" 只有 3 位,会跟 "0123" 混淆。

### S5. 二维码为什么是 22 字符不是 16/32?

`secrets.token_urlsafe(16)` = 16 字节 = 128 bit,base64url 编码后 22 字符(`ceil(16 * 8 / 6) = 22`)。22 字符既短到二维码能容下,又长到 128 bit 安全性足够。

### S6. 签到码 TTL 默认 60s 还是 300s?最长多少?

代码里 `DEFAULT_CODE_TTL_SECONDS = 60`,`MAX_CODE_TTL_SECONDS = 600`(10 分钟)。**PPT 写 300s 是错的**,实际最长 10 分钟。

### S7. 摄像头冲突怎么处理的?

W9 修过:`CameraWidget` 用 `threading.Lock` 互斥(之前用 bool 有 race),两个窗口同时打开摄像头会冲突,加了真互斥锁。

### S8. dlib 模型首次下载失败会怎样?

`_download_with_fallback`(`face_helper.py:42-69`)自动试 GitHub → gitee 镜像两个 URL,都失败抛 `RuntimeError("所有镜像下载失败")`,UI 弹 QMessageBox 提示"请检查网络";失败时保留 `.bz2` 文件供重试(W9 修的)。

### S9. PyQt 跨线程怎么做的?段错误过吗?

Qt 信号 `pyqtSignal(int, int)` + `Qt.QueuedConnection` 跨线程。**踩过坑**:W3 phase 5 文档记录,直接在 `on_progress` 回调里 `label.setText()` 会段错误,正确做法是 emit signal。CLAUDE.md 里有"W3 Phase 5 必踩的坑"专门一节。

### S10. closeEvent 资源泄漏怎么修的?

W8 修复:主窗口 `closeEvent` 调 `srv.should_exit = True` 同步停 FastAPI daemon thread、调 `_FaceCache.reset_for_test()` 清缓存、调 `cv2.VideoCapture.release()` 释放摄像头、调 `engine.dispose()` 释放 SQLAlchemy 连接池。

### S11. session_scope 异常了会怎样?

`__exit__` 收到异常 → `session.rollback()` + `session.close()` + 不重抛(已抛的会继续向上传播)。业务代码块内 raise → 自动 rollback → 异常传到 UI 层 → QMessageBox 弹给用户。

### S12. 193 个测试怎么组织的?覆盖率多少?

193 个 pytest 单元测试,~60s 跑完。分布:`test_auth_service` / `test_face_helper` / `test_signin_methods`(18)/ `test_signin_web`(11)/ `test_ui_modern`(10)/ `test_task_signin_code_dao`(5)/ `test_latest_api`(3,W15+)等。**没刻意追求覆盖率数字**,重点覆盖业务关键路径 + 回归锁。**注意 PPT 写 136 单元测试是旧的,实际 193**。

### S13. 6 个 smoke 端到端分别是?

`smoke_full_flow`(登录+签到完整链路)/ `smoke_real_face`(真实人脸测试)/ `smoke_ui_qtest`(UI 自动化)/ `smoke_e2e`(端到端)/ `smoke_signin_methods`(三种签到)/ `smoke_audit_history`(审计日志)/ `smoke_signin_web`(H5 签到,W14+)/ `smoke_signin_web_build`(PyInstaller 打包后 H5)。

### S14. 为什么用 MySQL 不用 SQLite?

SQLAlchemy 跨数据库,理论上能切。演示用 MySQL 是因为:课程要求"数据库原理",FK / ENUM / JSON / utf8mb4 字符集都是 MySQL 特性,SQLite 部分不支持;答辩老师更熟悉 MySQL。**测试用 SQLite 没做,但可加,省去配 MySQL 门槛**。

### S15. 用了存储过程/触发器/视图吗?

**都没用**。业务逻辑全部在 Python service 层维护,数据库只做"存和查"。**好处**:业务单测可控、git 管 Python 比管 MySQL DDL 容易、单点维护(`src/services/`)。

### S16. 数据量大了怎么办?分库分表?

项目规模(几千条以下)不需要分库分表。已做优化:索引覆盖所有查询路径、UNIQUE 索引同时是查询路径、`course_enrollment` 替代全表扫、`face_encoding` 只比对 is_primary=1。**扩展思路**:MySQL 主从读副本 / 按学期分表(attendance_record_2025 / attendance_record_2026)/ 数据仓库换 ClickHouse / Doris / 人脸比对换 Faiss / Milvus 向量库。

### S17. 跨平台支持 Linux/macOS 吗?

理论上能(都是 Python + Qt + MySQL)。**实际只在 Windows 上完整测过**。已知问题:dlib-bin 20.0.1 只有 Windows + Python 3.11 的 wheel;macOS 摄像头设备索引不一样;.bat 脚本 Windows only,start.sh 没充分测试。`start.bat` 全 ASCII 编码(W15+ 修的坑:cmd 5.1 GBK 编码踩过坑)。

### S18. 你的项目和市面考勤系统(钉钉/企业微信)有什么本质区别?

**场景不同**:对分易/钉钉面向"在线课堂",我们面向"线下实验室 + 课堂双场景"。**本地优先**:所有数据本地 MySQL(隐私/可控),不依赖云服务。**教学定制**:实验室准入 5 级安全 + 培训匹配是高校实验室专用。**代码量**:380 MB 打包,一个 .exe 双击就跑,不需要服务器。**不做**:不做考勤机硬件对接(指纹/IC 卡)、不做工资计算。

### S19. 现场写一条 SQL 查"所有人脸采集完成率"?

```sql
SELECT u.id, u.real_name,
       CASE WHEN fe.user_id IS NULL THEN 0 ELSE 1 END AS has_face
FROM user u
LEFT JOIN face_encoding fe ON fe.user_id = u.id AND fe.is_primary = 1
WHERE u.role = 'student' AND u.is_active = 1;
```
比率在 Python 层 `count(has_face=1) / count(*)`。ORM 版本:`UserDao.find_by_role('student')` + 集合运算。

### S20. 现场写"用原生 SQL 完成签到"?

```sql
INSERT INTO attendance_record (task_id, student_id, sign_in_time, status, match_score, signin_method)
VALUES (:task_id, :student_id, NOW(), :status, :match_score, :signin_method);
```
SQLAlchemy:`s.execute(text("INSERT INTO ..."), params)`。**代价**:失去 ORM 类型安全、跨数据库可移植、IDE 补全;**风险**:手写 SQL 容易出错(参数顺序、类型转换)。

### S21. 备份策略?误删能恢复吗?

课程设计范围**没有自动备份**。演示前手动 `mysqldump -u root -p attendance_lab > backup.sql`。误删恢复:demo 数据有 `scripts/seed_demo_data.py` 重置。**生产建议**:MySQL binlog + 每日 mysqldump + 异地备份 — 但项目里没做。

### S22. 教师中途关闭任务还能签到吗?

`_create_record` 第一道校验 `task.status != "open"` → 返 None,UI 提示"任务已结束"(`attendance_service.py:96-97`)。`sign_in_by_digit` / `sign_in_by_qr` 同 session 内也做同样校验。

### S23. 假批了但学生又签到怎么办?

学生会先签到(早到)→ `close_task` 时看到 `existed` 跳过,**不会**用 leave 覆盖。**签到优先级 > 请假**:`UNIQUE KEY uk_task_student` 保证只一条考勤记录,sign_in_time 不为 NULL 时就以签到为准。

### S24. 两个教师同时操作会冲突吗?

单机桌面应用,两个教师不会同时操作同一个教师端。多教师多任务 → `attendance_task` 主键自增,不同 teacher_id 的任务互不影响。教师改同一个任务设置 → **没显式悲观锁**,但任务一旦 created 字段基本不改(只改 status)。`close_task` 幂等靠 `if not task: return` + UNIQUE 兜底,不会重复写缺勤。

### S25. 为什么不让我用 ORM 我能用原生 SQL 完成签到吗?

能。SQLAlchemy 支持 `s.execute(text("INSERT INTO attendance_record ..."))`。关键 SQL 见 S20。**代价**:失去 ORM 类型安全、跨数据库可移植、IDE 补全;**风险**:手写 SQL 容易出错,需要更多测试覆盖。

---

# 第三部分:答辩前 5 分钟快速检查清单

- [ ] MySQL 服务开着,`.env` 配好 DB_PASSWORD
- [ ] `python scripts/init_db.py` 跑过(12 张 baseline + W13/W14 迁移)
- [ ] `python -m src.main` 能正常起 GUI(不段错误)
- [ ] 测试账号:`test001/123456`(学生)、`teacher001/123456`(教师)
- [ ] `pytest tests/ -v` 最后一行是 "188 passed"(**PPT 写 136 是错的,实际 193**)
- [ ] 答辩 PPT 9 页打开,投影正常
- [ ] 准备好 `git log --oneline | head -20`(展示 83 个 commit)
- [ ] 准备好 `db/schema.sql` 全文(老师可能让你指出某张表)
- [ ] 准备好 `src/services/attendance_service.py::_create_record` 代码(签到核心,Q4/Q10 高频)
- [ ] 准备好 `attendance_record` 表结构和 UNIQUE 索引(Q4 高频)
- [ ] 准备好 `lab_access_service.py::check_access` 7 种分支(Q23 高频)
- [ ] 现场跑 `pytest tests/test_signin_methods.py -v` 给老师看(18 项 V4.0 签到专项)

---

# 第四部分:1 分钟总结模板(如果老师让你临场总结)

"我这个项目是深圳技术大学**数据库原理课程设计**,**智能考勤与实验室准入系统**,用 PyQt5 + MySQL 8.0 + SQLAlchemy 2.0 + dlib 实现的桌面应用。

**核心数据模型是 14 张表**,围绕 user、course、attendance、lab、training 5 条业务线,**严格遵循 3NF,所有表都有外键约束**,考勤记录上 `UNIQUE(task_id, student_id)` 拦截重复签到。

**业务上有 3 个核心模块**:考勤签到(支持刷脸/数字码/二维码 3 种方式,**共用 `_create_record` 公共核**)、实验室准入(**7 种判定分支** + 5 级安全等级 + 培训匹配)、数据报表(matplotlib 4 类图)。

**架构上分 4 层**:ui → service → dao → model,严格自顶向下,**业务可独立 mock 测试**。

**安全方面**:bcrypt 12 rounds 慢哈希、login_attempt 表防爆破(5 次失败锁定)、SQLAlchemy ORM 全程防 SQL 注入、二维码 token 用 `secrets.token_urlsafe(16)` 128 bit 密码学安全随机 + 60 秒 TTL 覆盖式失效。

**工程化**:**188 个单元测试 + 6 个 smoke 端到端全部通过**,PyInstaller 打包 380 MB 一键 exe。

**已完成 14 个迭代阶段 (W2-W15+)** V1.0 → V5.0,完整闭环。"

---

# 答辩稳过 tips

1. **数据库设计问题答不上来是致命伤**,优先背 Q1-Q8(第一部分"一"全部)
2. **业务逻辑可以稍微弱**,代码细节不强求(老师一般不细看实现)
3. **主动暴露不足**比"假装完美"加分 — Q25 准备好
4. **老师追问 = 在乎你的项目**,不要慌
5. **PPT 数据 vs 实际数据对不上**别回避:**实际 193 单元测试,PPT 制作时间早于 W14/W15+ 加测试**,现场 `pytest tests/ -v | tail -1` 跑给老师看
6. **签到码最长 TTL 实际是 600s,PPT 写 300s 是错的**,主动纠正比被动发现好
7. **W15+ 修过的 2 个真实 bug**(H5 入口路由闭包 token + H5 polling)说明项目有真实工程迭代,不是 demo
