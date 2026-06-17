"""
scripts/init_db.py — 初始化数据库

执行 db/schema.sql + db/migration_w13.sql + db/migration_w14.sql,
并打印初始化结果。
用法：
    python scripts/init_db.py

W14+ 修复: schema.sql 单独跑会漏掉 2 张表 →
  - migration_w13.sql: task_signin_code (W13+ 数字码/二维码签到)
  - migration_w14.sql: course_teacher (W14+ 多老师对多课程)
现在顺序跑 3 个 SQL, 一把梭到位, 建 14 张表。

已部署库 (schema.sql 跑过) 再跑本脚本也安全: 全部
CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS, 幂等。
"""
import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"
MIGRATION_W13_PATH = PROJECT_ROOT / "db" / "migration_w13.sql"
MIGRATION_W14_PATH = PROJECT_ROOT / "db" / "migration_w14.sql"


def main():
    if not SCHEMA_PATH.exists():
        print(f"[ERR] 找不到 {SCHEMA_PATH}")
        sys.exit(1)

    # 读取 .env 拿到 MySQL 凭据
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    dbname = os.getenv("DB_NAME", "attendance_lab")

    if not password:
        print("[ERR] .env 中没有 DB_PASSWORD，请先配置 (参考 .env.template)")
        sys.exit(1)

    print(f"[INFO] 准备初始化 {dbname} @ {host}:{port} ...")
    cmd = [
        "mysql",
        f"-h{host}",
        f"-P{port}",
        f"-u{user}",
        f"-p{password}",
        "--default-character-set=utf8mb4",
    ]
    # 顺序跑 3 个 SQL:
    #   schema.sql         (13 张表, W12 及之前)
    #   migration_w13.sql  (task_signin_code + signin_method 字段)
    #   migration_w14.sql  (course_teacher 多对多表)
    sql_files = [SCHEMA_PATH]
    if MIGRATION_W13_PATH.exists():
        sql_files.append(MIGRATION_W13_PATH)
        print(f"[INFO] 将同时跑 {MIGRATION_W13_PATH.name} (W13+ task_signin_code)")
    if MIGRATION_W14_PATH.exists():
        sql_files.append(MIGRATION_W14_PATH)
        print(f"[INFO] 将同时跑 {MIGRATION_W14_PATH.name} (W14+ course_teacher)")

    try:
        for sql_path in sql_files:
            with open(sql_path, "r", encoding="utf-8") as f:
                subprocess.run(cmd, stdin=f, check=True)
            print(f"[OK] {sql_path.name} 执行完成")
        print(f"[OK] 数据库 {dbname} 初始化完成 (共 {len(sql_files)} 个 SQL 脚本, 14 张表)")
    except FileNotFoundError:
        print("[ERR] 未找到 mysql 命令，请确认 MySQL Client 已加入 PATH")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] MySQL 执行失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
