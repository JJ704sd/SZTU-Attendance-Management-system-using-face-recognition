-- =====================================================
-- 智能考勤与实验室准入系统 — W13+ 数据库迁移
-- 适用 MySQL 8.0+
--
-- 用途：已部署的库升级用，不动 schema.sql（schema.sql 走 DROP+CREATE 整体重建）。
-- 执行：mysql -u root -p attendance_lab < migration_w13.sql
-- =====================================================

USE attendance_lab;

-- -----------------------------------------------------
-- W13 新增：attendance_record.signin_method
--   区分刷脸 / 数字码 / 二维码签到，便于审计与统计。
-- -----------------------------------------------------
-- MySQL 8.0.29+ 支持 IF NOT EXISTS；旧版本请手动删 ALTER。
ALTER TABLE attendance_record
    ADD COLUMN IF NOT EXISTS signin_method ENUM('face','digit','qr') DEFAULT 'face'
        COMMENT '签到方式：刷脸/数字码/二维码' AFTER face_image,
    ADD INDEX IF NOT EXISTS idx_method (task_id, signin_method)
        COMMENT '按签到方式统计';

-- -----------------------------------------------------
-- W13 新增表：task_signin_code
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS task_signin_code (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    task_id     INT NOT NULL,
    code_type   ENUM('digit','qr') NOT NULL COMMENT '签到码类型：数字 / 二维码',
    code_value  VARCHAR(64) NOT NULL COMMENT 'digit: 4位数字 (0000-9999); qr: 22位 token',
    expires_at  DATETIME NOT NULL,
    is_active   TINYINT(1) DEFAULT 1 COMMENT '1=有效，0=被新码覆盖或手动失效',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES attendance_task(id) ON DELETE CASCADE,
    INDEX idx_task_type_active (task_id, code_type, is_active),
    INDEX idx_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='签到码表（数字/二维码）';

-- =====================================================
-- 验证（执行完后能看到下列两行）：
--   DESCRIBE attendance_record;  -- 含 signin_method 列
--   DESCRIBE task_signin_code;   -- 新表
-- =====================================================
