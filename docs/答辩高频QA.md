# 智能考勤与实验室准入系统 — 答辩高频 Q&A(精炼背诵版)

> 基于 `docs/答辩Q&A.md`(完整版 1045 行)抽取,**16 道最高频题**,数据库原理课老师最可能追问的点。
> **背诵顺序**:数据库设计(8)→ 事务(3)→ 安全(4)→ 技术选型(1)。
> **配套**:原 `答辩Q&A.md` 里有完整 20 道 + 25 道次频速记 + 5 分钟检查清单 + 1 分钟总结模板。

---

## 30 秒核心数据卡(老师问"多少 X"时直接报)

| 指标 | 实际值 | 备注 |
|---|---|---|
| 表数量 | **14 张** | baseline 12 + W13+ task_signin_code + W14+ course_teacher;`db/schema.sql` 全文可查 |
| 单元测试 | **219 项** | `pytest tests/ -v` ~67s 跑完,3 warning;**PPT 写 136 是旧的** |
| 签到方式 | **3 种** | 刷脸(face)/ 数字码(digit)/ 二维码(qr),共用 `_create_record` 公共核 |
| 实验室判定分支 | **7 种** | 6 拒绝 + 1 放行;`safety_level >= 4` 算高等级(**PPT 写"5 级"是简化**) |
| 迭代阶段 | **5 个** | V1.0 登录 → V2.0 人脸 → V3.0 准入 → V4.0 打包 → V5.0 签到方式 |
| Git commit | **101+** (audit-round16 HEAD) | `git log --oneline \| head -20` 可现场展示 |
| PyInstaller 打包 | **380 MB** | onedir 模式,含 dlib 模型,双击即跑 |
| 签到码 TTL | 默认 60s / **最长 600s(10 分钟)** | **PPT 写 300s 是错的**,代码 `attendance_service.py:42` |
| bcrypt rounds | **12** | 每次哈希 ~250ms |
| 登录锁定阈值 | **5 次失败** | `LOGIN_MAX_ATTEMPTS = 5` |
| 二维码 token 长度 | **22 字符**(128 bit) | `secrets.token_urlsafe(16)` |
| face encoding 维度 | **128 维 float32** | 512 字节,BLOB 存 |

---

## 第一部分:数据库设计(8 道,最高优 — 必背)

---

### Q1. ER 图怎么画?核心实体和关系?

**5 条业务线 + 14 张表**:
| 业务线 | 实体 |
|---|---|
| 身份 | `user`(三类角色统一表) |
| 课程 | `course` / `classroom` / `course_enrollment` / `course_teacher`(W14+) |
| 人脸 | `face_encoding` |
| 考勤 | `attendance_task` / `attendance_record` / `leave_request` / `task_signin_code`(W13+) |
| 实验室 | `laboratory` / `lab_training` / `lab_access_log` |
| 审计 | `login_attempt` |

**核心关系**:
- 强依赖:`attendance_record → attendance_task` / `leave_request → attendance_task` / `lab_training → user+laboratory`
- 弱依赖:`lab_access_log.student_id` 可空(刷脸失败时 user 还未识别)
- 多对多:`user ↔ course` 双中间表(学生用 `course_enrollment`、W14+ 多教师用 `course_teacher`)

---

### Q2. 遵循了哪些范式?有反范式吗?

**主体 3NF + BCNF**:
- 例 `attendance_record(id, task_id, student_id, sign_in_time, status, match_score, signin_method, face_image)` — 所有非主属性直接依赖 id,无传递依赖
- BCNF:每个决定因素都是候选键,无非主属性决定其他非主属性

**没有触发器/存储过程/视图**:业务逻辑全部在 `src/services/*.py` 维护,数据库只"存和查"。

**唯一"看似反范式"是合理的**:
- `face_encoding.encoding` BLOB 存 128 维向量,不走 RDBMS 文本规则
- `attendance_record.face_image` 存的是**路径**不是 BLOB(图片不进库)
- `task_signin_code` 没 UNIQUE 约束(虽然 `code_value` 业务唯一),故意保留多条历史码供审计

---

### Q3. 为什么用 `user` 单表统一三类角色?

**3 个原因**:
1. **减少 JOIN**:14 张表里 9 张外键引用 `user(id)`,拆 3 表要 3 个 FK 列,所有关系重设计
2. **现实场景**:管理员可能临时承担教师职责(代课);用户管理界面是统一列表
3. **扩展性**:加新角色(如"实验室助理")只扩 ENUM,不动表结构

**代价**:教师 `student_id` 是 NULL,业务层 `if user.role == "student"` 多一层判断(用 `src/constants.py` 集中维护)。

**替代方案对比**:拆 3 表 + 1 张 account 统一登录 → JOIN 多;继承表 → 多一次 LEFT JOIN。**结论:单表 + role ENUM 对当前规模最优**。

---

### Q4. `attendance_record` 的 `UNIQUE(task_id, student_id)` 是不是冗余?

**不是冗余,是关键防线**(`db/schema.sql:121`):
```sql
UNIQUE KEY uk_task_student (task_id, student_id)
```

**没有它会发生的 bug**:
- 学生同时刷脸 + 输数字码(双卡顿)→ 2 条记录
- 教师重复"结束考勤"按钮(没幂等)→ 关闭时再写一条缺勤
- 并发 race:`_create_record` 里 `existed` SELECT 之后 INSERT 之前有窗口,两事务都看到"没签到"

**双层防护**:应用层先查(`attendance_service.py:104-109`)→ 友好返 None 提示"已签到";DB 层 UNIQUE 兜底,即使应用漏检也 `IntegrityError` 拦截。**"数据库是最后一道真理,不要相信应用层一定查过了"**。

---

### Q5. 建了哪些索引?为什么是这些?

| 关键索引 | 表 | 业务场景 |
|---|---|---|
| `username` UNIQUE | user | 登录查 user |
| `idx_role` | user | 管理员查"所有学生" |
| `uk_task_student` UNIQUE | attendance_record | 拦截重复签到 + 查"我签了没" |
| `idx_student_time` | attendance_record | (student_id, sign_in_time) 学生查历史 |
| `idx_method` | attendance_record | (task_id, signin_method) W13+ 按签到方式统计 |
| `idx_safety` | laboratory | 查"所有 4-5 级实验室" |
| `idx_user_time` | login_attempt | (username, attempted_at DESC) 防爆破查最近失败 |
| `idx_task_type_active` | task_signin_code | 查当前有效码 |

**没建冗余索引** — 没有"为可能用到"建,只建实际业务路径。InnoDB 外键列自动有索引,UNIQUE 约束自动是索引。

---

### Q6. 哪些字段用了 ENUM?为什么?

**用了 ENUM 的 9 个字段**:
- `user.role` (3 值) / `course.course_type` (2) / `attendance_task.status` (2)
- `attendance_record.status` (4: present/late/absent/leave) / `signin_method` (3: face/digit/qr)
- `leave_request.status` (3) / `lab_training.training_type` (4) / `task_signin_code.code_type` (2) / `course_teacher.role` (2)

**3 个理由**:
1. **存储紧凑**:MySQL 内部 1-2 字节整数,4 状态字段每行省 3-4 字节
2. **DDL 改值强制迁移**:`ALTER TABLE ... MODIFY role ENUM(...)` 校验所有现数据,改不了脏数据
3. **可读性**:`status='present'` 比 `status=1` 直观

**用 VARCHAR 更合适**:`laboratory.required_training`(培训类型可能扩"激光安全")、自由文本(姓名)。

**ENUM 坑**:改列表要 `ALTER TABLE`,千万级表有锁表风险;不同 collation 下排序可能不一致 — 我们统一 `utf8mb4_unicode_ci`。

---

### Q7. 全部用了外键吗?级联删除怎么选?

**全部用了 FK 约束**(InnoDB,9 张表有外键)。**故意不建 FK 的 1 处**:`login_attempt.username` 不建 FK — 登录失败时 user 可能还不存在(被删了/从来没注册),建 FK 就无法记录攻击尝试。

**CASCADE 选择逻辑**:
- ✅ **CASCADE**:`face_encoding.user_id`(学生删→人脸数据自动清,隐私)、`attendance_record.task_id`(任务删→记录跟着删,考勤是一次性事件)、`course_enrollment` 双 CASCADE(纯关联表)
- ❌ **RESTRICT**:`attendance_record.student_id` 不级联(学生删→考勤记录保留,审计要求"这个学号历史上出勤过哪些课"能查)、`leave_request.approver_id` 同理

---

### Q8. `face_encoding.encoding` 为什么 BLOB 不是 TEXT?图片怎么存?

**encoding 用 BLOB 的 2 个原因**(`db/schema.sql:39`):
- 128 维 float32 向量 = 128 × 4 = **512 字节二进制**
- BLOB 走二进制通道,**不涉及字符集转换**(TEXT/VARCHAR 按 utf8mb4 编码,改 collation 会破坏数据)
- 序列化:`arr.astype(np.float32).tobytes()` ↔ `np.frombuffer(b, dtype=np.float32)`(`face_service.py:34-47`)
- 长度硬约束:shape=(128,),bytes=512,错就 `ValueError`

**图片存路径而不是 BLOB**:
- 4 处图片字段都存 VARCHAR(255) 路径:`face_encoding.image_path` / `attendance_record.face_image` / `lab_access_log.face_image` / `user.avatar_path`
- 落文件系统 `dataset/...` 目录

**为什么不把图片也存 BLOB**:
- 单图 200-500 KB,大行让索引放不进 InnoDB buffer pool(默认 16 KB)→ 退化为磁盘随机读
- 备份 mysqldump 慢 5-10 倍,网络传输慢
- **判断标准**:**数据是不是要参与业务查询**(encoding 要算距离必须入 DB;图片只给 UI 显示,不入 DB)
- **工业实践**:Nginx 静态文件、CDN 都这么做

---

## 第二部分:事务、并发、ACID(3 道 — 必背)

---

### Q9. 事务边界在哪里?怎么保证 ACID?

**事务边界**:`src/db.py:22-33` 的 `session_scope()` 上下文管理器:
```python
@contextmanager
def session_scope():
    s = SessionLocal()
    try:
        yield s
        s.commit()       # 正常退出 → 提交
    except Exception:
        s.rollback()     # 异常退出 → 回滚
    finally:
        s.close()
```
**每个 service 方法 = 一个事务**。

- **A 原子性**:session_scope `__exit__` 正常 commit、异常 rollback;`with` 块内多步操作原子
- **C 一致性**:FK 约束(13 张全建) + UNIQUE 约束 + ENUM 约束 + NOT NULL
- **I 隔离性**:MySQL InnoDB 默认 `REPEATABLE READ`,SQLAlchemy session 单连接
- **D 持久性**:依赖 MySQL binlog + redolog 默认配置

**关键反直觉细节**(`auth_service.py:103-133`):
```python
attempt_dao.record_attempt(username, success=False)
s.commit()  # ⚠️ 显式提交,避免 raise 触发 rollback 抹掉记录
raise AuthError(...)
```
**不显式 commit,record_attempt 被回滚,等于没记录 → 第 5 次失败后还能继续输**。这个坑真实踩过,W4 修过一次。

---

### Q10. 两个学生同时签到,会重复写吗?

**不会,3 道防线**:

**第一道:应用层提前查**(`attendance_service.py:104-109`)
```python
existed = s.query(AttendanceRecord).filter(
    and_(AttendanceRecord.task_id == task_id,
         AttendanceRecord.student_id == user_id)
).first()
if existed:
    return None  # 友好返"已签到"
```

**第二道:DB UNIQUE 约束**(`db/schema.sql:121`)
```sql
UNIQUE KEY uk_task_student (task_id, student_id)
```
即使应用层漏检/并发 race,第二个 INSERT 必然 `IntegrityError`,事务回滚。

**第三道:session 隔离 + race 窗口最小化**:数字码/二维码走 `_create_record_in_session` 复用外层 session 原子完成;刷脸独立 session 但 ~200ms 窗口被抢占概率极低。

**结论**:即使最坏情况(应用 bug + race),数据库层保证数据不重复。

---

### Q11. 签到码"覆盖式失效"怎么保证原子性?中途崩溃呢?

**关键代码**(`attendance_service.py:262-292`):
```python
with session_scope() as s:
    # 1) 失效同任务同类型所有未过期有效码
    dao.deactivate_active_for_task_type(task_id, code_type)
    # 2) 生成新码
    code_value = (f"{random.randint(0, 9999):04d}" if code_type == "digit"
                  else secrets.token_urlsafe(16))
    # 3) 写新码
    new_code = dao.insert_new(...)
```
3 步同 session_scope,一起 commit / 一起 rollback。**不会"旧码失效 + 新码还没写"的中间态**。

**中途崩溃分析**:
- 崩溃在 step 1 之后、commit 之前 → 整个事务回滚 → 旧码依然有效
- commit 之后崩溃 → 新码生效,旧码已失效 → **结果正确**
- **结论**:任何时点崩溃都不会留下"无新码但旧码已失效"的不可用状态

**数字码 vs 二维码生成策略**:
- 数字码 `random.randint`(4 位 10000 组合,60s 就过期,无需密码学强度)
- 二维码 `secrets.token_urlsafe(16)`(128 bit 密码学安全,要扛住几小时有效期)

---

## 第三部分:安全(4 道 — 必背)

---

### Q12. 怎么防 SQL 注入?

**全程 SQLAlchemy 2.0 ORM,不拼字符串**。所有用户输入走参数化查询,例如 `UserDao.find_by_username(username)` 内部是:
```python
SELECT * FROM user WHERE username = :p1
```
绑定 `p1=username` 走 MySQL prepared statement,**用户输入永远是数据,不是 SQL**。

**对比演示**(说服老师):
```python
# 错误(假设有人图省事)
sql = f"SELECT * FROM user WHERE username = '{username}'"
s.execute(text(sql))
# 输入 username = "' OR '1'='1" → 整个 user 表泄漏

# 正确(项目里所有地方)
s.query(User).filter(User.username == username).first()
# 输入任何字符串都被绑定为字面量
```

**为什么不留手写 SQL 的口子**:14 张表 DAO 全走 ORM(`BaseDao` 封装 `s.add/query/filter`),唯一手写 SQL 是 `db/schema.sql` DDL,**没有运行时拼接**。

**深度防御**:即使 ORM 出了漏洞,bcrypt 密码哈希(`crypto.py:9-19`)也能扛住 — 拿到 hash 也解不开。

---

### Q13. 密码怎么存?为什么 bcrypt 不用 SHA-256?

**bcrypt 12 rounds**(`src/utils/crypto.py:7-19`):
```python
def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")
```

**4 个理由选 bcrypt**:
1. **慢哈希**:rounds=12 → 每次哈希 ~250ms,大幅增加暴力破解成本
2. **自带 salt**:每次 hash 不同(随机 16 字节 salt),防 rainbow table
3. **可调成本**:`rounds` 可调,硬件变强时增大
4. **工业标准**:Linux 影子密码、WordPress、Django 默认都 bcrypt

**不选其他的原因**:
- **MD5/SHA-1**:已被碰撞攻击攻破,且快速哈希 GPU 一秒算几十亿次
- **SHA-256/SHA-3**:是快速哈希不是密码学慢哈希
- **PBKDF2/scrypt/Argon2**:都 OK,选 bcrypt 因为 Python 生态最成熟

**登录验证**:`bcrypt.checkpw(plain, hashed)` 自动从 hash 提取 salt + rounds,不用传额外参数。密码字段 `user.password_hash VARCHAR(255)` 存 `$2b$12$...60字符...`。

---

### Q14. 登录防爆破怎么做?为什么用 login_attempt 表?

**配置**:`LOGIN_MAX_ATTEMPTS = 5`(`src/config.py:82`)

**关键代码**(`auth_service.py:103-133`):
```python
with session_scope() as s:
    recent_failures = attempt_dao.count_recent_failures(
        username, limit=Config.LOGIN_MAX_ATTEMPTS,
    )
    if recent_failures >= Config.LOGIN_MAX_ATTEMPTS:
        raise AuthError(f"账号已锁定:连续 {Config.LOGIN_MAX_ATTEMPTS} 次失败")
    user = user_dao.find_by_username(username)
    if not user or not verify_password(password, user.password_hash):
        attempt_dao.record_attempt(username, success=False)
        s.commit()  # ⚠️ 显式提交,避免 raise 触发 rollback
        raise AuthError("用户名或密码错误")
    attempt_dao.record_attempt(username, success=True)
```

**为什么用独立 `login_attempt` 表而不是在 `user` 加计数器**:
1. **审计独立**:能查"什么时候/从哪个 IP/失败频率"(`idx_user_time` 索引)
2. **不污染主表**:`user` 是身份表,加 `fail_count` 字段让所有用户查询受影响
3. **解锁不丢历史**:管理员 `UPDATE user SET is_active=1` 不会清掉历史失败记录
4. **分析攻击模式**:短时间内多次失败 = 可能在暴力破解

**反直觉坑**(`auth_service.py:99-101` docstring):**不 commit 直接 raise,记录被回滚,等于没记录 → 第 5 次失败后还能继续输**。W4 修过。

**没做**(主动说):没按 IP 锁定(攻击者换 IP 仍能继续)、没做 CAPTCHA / 24h 自动解锁 — 课程设计范围够用。

---

### Q15. 二维码 token 怎么生成?能伪造/截图滥用吗?

**token 生成**(`attendance_service.py:279`):
```python
code_value = secrets.token_urlsafe(16)
```
- `secrets` 模块 Python 3.6+ 密码学安全随机(基于 `os.urandom`)
- 16 字节 = **128 bit 随机**
- `token_urlsafe` → base64url 编码,URL 友好
- 输出 **22 字符**(`ceil(16 * 8 / 6) = 22`)

**能伪造吗**:理论上能,实际不可能 — **碰撞概率 < 2^-96 ≈ 10^-29**(生日攻击界 2^64),地球每秒生成 10 亿个跑到宇宙热寂也碰不到。

**校验**(`task_signin_code_dao.py:59-73`):三重过滤 — task + type + value 精确匹配 + `is_active=1` + 未过期。任一不满足返 None。

**能截图滥用吗 — 不能**:
- **TTL 60s** + **覆盖式失效**(Q11):教师中途点"🎲 生成新码" → `deactivate_active_for_task_type` 把同任务同类型所有未过期有效码 `is_active=0` → 学生手里截图立刻失效
- 学生偷看隔壁同学手机也不行 — 每人提交自己 user_id 关联的记录,不可代签

**W15+ 修过的真实 bug**:`signin_web.py::signin_page` 之前用**闭包里的 token 校验**,但 web server 启动时定死的 token 跟 DB LIVE token 永远不一致(dialog 启动会再 `_generate_code` 覆盖)。**修法**:闭包不校验 token,真实校验交给 `find_active_by_value` 实时查 DB。**教训:in-memory state(闭包/缓存)不能当真理**。

---

## 第四部分:技术选型(1 道 — 必背)

---

### Q16. 为什么用 SQLAlchemy ORM,不用原生 SQL?

**4 个核心理由**:
1. **防 SQL 注入**:参数化查询,见 Q12
2. **跨数据库可移植**:`DB_URL` 一行配置切换。开发 SQLite、演示 MySQL 8.0
3. **类型安全 + IDE 补全**:`User.username` 写错报错,`.desc()` 列排序方向
4. **迁移友好**:`Base.metadata.create_all(engine)`(`db.py:52`)自动建表

**ORM 的坑**(主动说):
- **N+1 查询**:`for u in users: for e in u.encodings` 触发 1+N 次 SQL → `joinedload`/`subqueryload` 预加载(项目数据量小,N+1 不明显)
- **复杂查询性能差**:`SELECT * FROM a JOIN b JOIN c WHERE ...` ORM 啰嗦,有时不如 `s.execute(text(...))` 走原生

**没用 ORM 的地方**:`db/schema.sql` DDL(纯 SQL,ORM 帮不了)、`db/migration_w13.sql`/`migration_w14.sql` 增量迁移。

**结论**:ORM 是 80/20 原则 — 80% 场景受益,20% 复杂查询必要时降级到原生 SQL。

---

## 第五部分:5 分钟背诵清单

- [ ] **Q1**:14 张表分 5 条业务线,ER 关系强度(强依赖/弱依赖/多对多)
- [ ] **Q2**:3NF + BCNF,无触发器/存储过程/视图
- [ ] **Q3**:单表 user + role ENUM 的 3 个理由 + 代价
- [ ] **Q4**:`uk_task_student` UNIQUE 拦截重复,3 道防线
- [ ] **Q5**:核心索引表(8 行),不建冗余索引
- [ ] **Q6**:9 个 ENUM 字段,3 个理由,VARCHAR 适用场景
- [ ] **Q7**:全部用 FK,1 处故意不建(login_attempt),CASCADE 选择逻辑
- [ ] **Q8**:BLOB 存 encoding(512 字节)+ 图片存路径 + 判断标准
- [ ] **Q9**:session_scope 4 个 ACID,显式 commit 坑
- [ ] **Q10**:3 道防线(应用查/UNIQUE/session 隔离)
- [ ] **Q11**:覆盖式失效 3 步原子,中途崩溃 4 种场景
- [ ] **Q12**:ORM 参数化,正反对比演示
- [ ] **Q13**:bcrypt 12 rounds 4 个理由,不选 MD5/SHA-256 的原因
- [ ] **Q14**:login_attempt 表 4 个理由,显式 commit 坑
- [ ] **Q15**:128 bit 22 字符 token,3 重过滤校验,截图防滥用
- [ ] **Q16**:ORM 4 个理由 + N+1 坑 + 80/20 原则

---

## 第六部分:3 个真坑提醒(答辩前必扫一眼)

> 这些是 PPT 数据 vs 实际代码的偏差,老师很可能会问。**主动说"我们迭代中发现了真问题并修复"比假装完美加分得多**。

### 坑 1:PPT 第 8 页写"136 单元测试",实际 219

- 实际:219 项,`pytest tests/ -v` ~67s 跑完,3 warning
- PPT 制作时间早于 W14/W15+/W16 加的 80+ 项测试(W14+ signin_web 11 + UI 现代化 10 + W15+ latest API 3 + W16+ _FaceCache 8 等)
- **准备说辞**:现场 `pytest tests/ -v | tail -1` 跑给老师看
- 分布:auth_service / face_helper / signin_methods(18) / signin_web(11) / ui_modern(10) / task_signin_code_dao(5) / latest_api(3,W15+) / face_cache(8,W16+) / styles_modern / charts

### 坑 2:PPT 第 5 页写"TTL 最长 300s",实际 600s(10 分钟)

- 实际:`MAX_CODE_TTL_SECONDS = 600`(`attendance_service.py:42`),`DEFAULT_CODE_TTL_SECONDS = 60`
- **主动纠正**比被动发现好 — 老师看到 PPT 翻代码不一致会问
- 为什么是 10 分钟:数字码 60s 太短(学生卡顿就过期),给 10 分钟兜底

### 坑 3:PPT 第 4 页说"5 级安全等级" + "7 种判定分支"

- 实际:安全等级字段是 `safety_level INT(0-5)`,代码里 `safety_level >= 4` 算高等级(`lab_access_service.py:102`)— **4 和 5 都算**
- 7 种判定 = 6 种拒绝 + 1 种放行(`lab_access_service.py:44-120`),**非学生自由出入也算放行分支**
- 建议说辞:PPT 是简化展示,代码以 `lab_access_service.py` 为准

---

## 第七部分:现场 30 秒总结(如果老师让你临场总结)

> 这是一段**口头模板**,约 1 分钟讲完:

"我这个项目是深圳技术大学**数据库原理课程设计**,**智能考勤与实验室准入系统**,用 PyQt5 + MySQL 8.0 + SQLAlchemy 2.0 + dlib 实现的桌面应用。

**核心数据模型是 14 张表**,围绕 user、course、attendance、lab、training 5 条业务线,**严格遵循 3NF,所有表都有外键约束**,考勤记录上 `UNIQUE(task_id, student_id)` 拦截重复签到。

**业务上有 3 个核心模块**:考勤签到(支持刷脸/数字码/二维码 3 种方式,**共用 `_create_record` 公共核**)、实验室准入(**7 种判定分支** + 安全等级匹配 + 培训分数阈值)、数据报表(matplotlib 4 类图)。

**架构上分 4 层**:ui → service → dao → model,严格自顶向下,**业务可独立 mock 测试**。

**安全方面**:bcrypt 12 rounds 慢哈希、login_attempt 表防爆破(5 次失败锁定)、SQLAlchemy ORM 全程防 SQL 注入、二维码 token 用 `secrets.token_urlsafe(16)` 128 bit 密码学安全随机 + 60 秒 TTL 覆盖式失效。

**工程化**:**219 个单元测试 + 10 个 smoke 端到端全部通过**,PyInstaller 打包 380 MB 一键 exe。

**已完成 14 个迭代阶段 (W2-W15+)** V1.0 → V5.0,完整闭环。"

---

## 配套文档

- 完整版 20 道 + 25 道次频速记 + 答辩 tips:`docs/答辩Q&A.md`
- 答辩 PPT 大纲(5 分钟 9 页):`智能考勤与实验室准入系统-5分钟答辩.pptx` + `docs/W14-defense-outline.md`
- 项目交接总入口:`docs/HANDOFF.md`
- 数据库设计文档:`docs/DATABASE.md`
- 架构文档:看 `src/` 4 层代码 + `CLAUDE.md`（W15+ cleanup 已删 ARCHITECTURE.md，4 层依赖在 CLAUDE.md 决策表里有详细描述）
