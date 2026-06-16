-- =====================================================
-- 智能考勤与实验室准入系统 — W14+ 数据库迁移
-- 适用 MySQL 8.0+
--
-- 用途: W14+ 演示模式配套, 让一门课可以挂多个老师
--       (xls 课表里 3 门课有多老师: 信号与系统 / 数据库原理 / 医用电子技术)
--
-- 策略: 保留 course.teacher_id 作为 "主讲教师" (兼容现有 attendance_task.teacher_id 业务)
--       本表存所有任课教师 (包括主讲 + 助教 / 同课程不同节次不同老师)
--
-- 执行: mysql -u root -p attendance_lab < migration_w14.sql
-- =====================================================

USE attendance_lab;

-- -----------------------------------------------------
-- W14+ 新增表: course_teacher (课程-教师 多对多关联)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS course_teacher (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    course_id   INT NOT NULL,
    teacher_id  INT NOT NULL,
    role        ENUM('main','assistant') NOT NULL DEFAULT 'main'
        COMMENT '主讲 (main) / 助教 (assistant)',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES course(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES user(id) ON DELETE CASCADE,
    UNIQUE KEY uk_course_teacher (course_id, teacher_id),
    INDEX idx_course (course_id),
    INDEX idx_teacher (teacher_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程-教师 多对多关联表 (W14+)';

-- =====================================================
-- 验证 (执行完后能看到):
--   DESCRIBE course_teacher;
-- =====================================================
