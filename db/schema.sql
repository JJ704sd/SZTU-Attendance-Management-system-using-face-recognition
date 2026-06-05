-- =====================================================
-- 智能考勤与实验室准入系统 数据库 Schema
-- 适用 MySQL 8.0+  字符集 utf8mb4
-- 建库：CREATE DATABASE attendance_lab DEFAULT CHARSET utf8mb4;
-- 执行：mysql -u root -p < schema.sql
-- =====================================================

DROP DATABASE IF EXISTS attendance_lab;
CREATE DATABASE attendance_lab DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE attendance_lab;

-- -----------------------------------------------------
-- 1. 用户表（三类角色统一）
-- -----------------------------------------------------
CREATE TABLE user (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(50) NOT NULL UNIQUE COMMENT '登录用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT 'bcrypt 哈希',
    real_name     VARCHAR(50) NOT NULL COMMENT '真实姓名',
    role          ENUM('student','teacher','lab_admin') NOT NULL COMMENT '角色',
    student_id    VARCHAR(20) UNIQUE COMMENT '学号（学生专用）',
    direction     VARCHAR(50) COMMENT '专业方向：纳米医学技术/生物医学仪器/生物医学检测/智能医疗仪器/智能医疗信息/智能医学工程',
    email         VARCHAR(100),
    phone         VARCHAR(20),
    avatar_path   VARCHAR(255) COMMENT '头像路径',
    is_active     TINYINT(1) DEFAULT 1 COMMENT '账号是否启用',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_role (role),
    INDEX idx_student_id (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- -----------------------------------------------------
-- 2. 人脸编码（每采集一张存一条，便于重训）
-- -----------------------------------------------------
CREATE TABLE face_encoding (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    user_id     INT NOT NULL,
    encoding    BLOB NOT NULL COMMENT '128维float32向量，序列化为bytes',
    image_path  VARCHAR(255) NOT NULL COMMENT '原始图像路径',
    is_primary  TINYINT(1) DEFAULT 0 COMMENT '是否主图（识别优先用）',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_primary (user_id, is_primary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='人脸编码表';

-- -----------------------------------------------------
-- 3. 课程表
-- -----------------------------------------------------
CREATE TABLE course (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    course_code VARCHAR(20) NOT NULL UNIQUE COMMENT '课程编号',
    course_name VARCHAR(100) NOT NULL,
    course_type ENUM('theory','experiment') NOT NULL DEFAULT 'theory' COMMENT '理论/实验',
    teacher_id  INT NOT NULL,
    credit      FLOAT DEFAULT 2.0,
    semester    VARCHAR(20) COMMENT '如 2025-2026-2',
    FOREIGN KEY (teacher_id) REFERENCES user(id),
    INDEX idx_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程表';

-- -----------------------------------------------------
-- 4. 教室表
-- -----------------------------------------------------
CREATE TABLE classroom (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    name       VARCHAR(50) NOT NULL,
    location   VARCHAR(100) COMMENT '教学楼+房间号',
    capacity   INT DEFAULT 60,
    has_camera TINYINT(1) DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='教室表';

-- -----------------------------------------------------
-- 5. 实验室表（含安全等级）
-- -----------------------------------------------------
CREATE TABLE laboratory (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(50) NOT NULL,
    location      VARCHAR(100),
    safety_level  TINYINT NOT NULL COMMENT '1-5，5最高',
    required_training VARCHAR(50) COMMENT '要求的培训类型',
    manager_id    INT COMMENT '实验室管理员',
    FOREIGN KEY (manager_id) REFERENCES user(id),
    INDEX idx_safety (safety_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实验室表';

-- -----------------------------------------------------
-- 6. 考勤任务（教师发起）
-- -----------------------------------------------------
CREATE TABLE attendance_task (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    course_id    INT NOT NULL,
    teacher_id   INT NOT NULL,
    classroom_id INT NOT NULL,
    start_time   DATETIME NOT NULL,
    end_time     DATETIME NOT NULL,
    status       ENUM('open','closed') DEFAULT 'open',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES course(id),
    FOREIGN KEY (teacher_id) REFERENCES user(id),
    FOREIGN KEY (classroom_id) REFERENCES classroom(id),
    INDEX idx_course_time (course_id, start_time),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考勤任务表';

-- -----------------------------------------------------
-- 7. 考勤记录
-- -----------------------------------------------------
CREATE TABLE attendance_record (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    task_id       INT NOT NULL,
    student_id    INT NOT NULL,
    sign_in_time  DATETIME,
    status        ENUM('present','late','absent','leave') DEFAULT 'absent',
    match_score   FLOAT COMMENT '人脸匹配欧氏距离，越小越像',
    face_image    VARCHAR(255) COMMENT '签到时抓拍的照片路径',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES attendance_task(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES user(id),
    UNIQUE KEY uk_task_student (task_id, student_id) COMMENT '同一任务同一学生只记一次',
    INDEX idx_student_time (student_id, sign_in_time),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='考勤记录表';

-- -----------------------------------------------------
-- 8. 请假申请
-- -----------------------------------------------------
CREATE TABLE leave_request (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    student_id  INT NOT NULL,
    task_id     INT NOT NULL,
    reason      TEXT NOT NULL,
    status      ENUM('pending','approved','rejected') DEFAULT 'pending',
    approver_id INT COMMENT '审批人（教师/管理员）',
    approve_time DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES user(id),
    FOREIGN KEY (task_id) REFERENCES attendance_task(id) ON DELETE CASCADE,
    FOREIGN KEY (approver_id) REFERENCES user(id),
    INDEX idx_student (student_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='请假申请表';

-- -----------------------------------------------------
-- 9. 安全培训记录
-- -----------------------------------------------------
CREATE TABLE lab_training (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    student_id      INT NOT NULL,
    lab_id          INT NOT NULL,
    training_type   ENUM('生物','化学','辐射','设备') NOT NULL,
    completion_date DATE NOT NULL,
    expiry_date     DATE NOT NULL,
    score           FLOAT NOT NULL,
    instructor_id   INT COMMENT '培训教师',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES user(id),
    FOREIGN KEY (lab_id) REFERENCES laboratory(id),
    FOREIGN KEY (instructor_id) REFERENCES user(id),
    INDEX idx_student_lab (student_id, lab_id),
    INDEX idx_expiry (expiry_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='安全培训记录表';

-- -----------------------------------------------------
-- 10. 实验室准入日志（审计）
-- -----------------------------------------------------
CREATE TABLE lab_access_log (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    student_id  INT,
    lab_id      INT NOT NULL,
    access_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    granted     TINYINT(1) NOT NULL COMMENT '1放行/0拒绝',
    reason      VARCHAR(255) COMMENT '拒绝原因或放行备注',
    face_image  VARCHAR(255) COMMENT '抓拍图像',
    FOREIGN KEY (student_id) REFERENCES user(id),
    FOREIGN KEY (lab_id) REFERENCES laboratory(id),
    INDEX idx_time (access_time DESC),
    INDEX idx_lab_time (lab_id, access_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='实验室准入日志';

-- =====================================================
-- 测试数据（可选，用于演示）
-- =====================================================
INSERT INTO user (username, password_hash, real_name, role, student_id, direction) VALUES
('20230101', '$2b$12$placeholder', '张三', 'student', '20230101', '生物医学仪器'),
('20230102', '$2b$12$placeholder', '李四', 'student', '20230102', '智能医疗信息'),
('teacher01', '$2b$12$placeholder', '王老师', 'teacher', NULL, NULL),
('labadmin01', '$2b$12$placeholder', '赵管理员', 'lab_admin', NULL, NULL);

INSERT INTO laboratory (name, location, safety_level, required_training, manager_id) VALUES
('BME-1 嵌入式实验室', 'C栋301', 2, '设备', 4),
('BME-2 生物医学检测实验室', 'C栋402', 3, '生物', 4),
('BME-3 化学实验室', 'D栋105', 4, '化学', 4);

INSERT INTO classroom (name, location, capacity) VALUES
('A101', 'A栋1楼', 80),
('A202', 'A栋2楼', 60);
