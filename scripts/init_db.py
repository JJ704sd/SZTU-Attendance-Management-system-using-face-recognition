"""
scripts/init_db.py — 初始化数据库

执行 db/schema.sql + db/migration_w13.sql，并打印初始化结果。
用法：
    python scripts/init_db.py

W14 修复: W13+ 加的 task_signin_code 表在 migration_w13.sql 里,
          schema.sql 单独跑会漏建 → 数字码/二维码签到会报"Table doesn't exist"。
          现在顺序跑 2 个 SQL, 一把梭到位。

          已部署库 (schema.sql 跑过) 再跑本脚本也安全: 两条都是
          CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS, 幂等。
"""
import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"
MIGRATION_W13_PATH = PROJECT_ROOT / "db" / "migration_w13.sql"


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
        print("[ERR] .env 中没有 DB_PASSWORD，请先配置")
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
    # 顺序跑 schema.sql + migration_w13.sql
    # (W14 修复: schema.sql 不含 task_signin_code 表, 漏跑 migration 会让
    #  数字码/二维码签到首次操作就崩)
    sql_files = [SCHEMA_PATH]
    if MIGRATION_W13_PATH.exists():
        sql_files.append(MIGRATION_W13_PATH)
        print(f"[INFO] 将同时跑 {MIGRATION_W13_PATH.name} (W13+ 增量迁移)")

    try:
        for sql_path in sql_files:
            with open(sql_path, "r", encoding="utf-8") as f:
                subprocess.run(cmd, stdin=f, check=True)
            print(f"[OK] {sql_path.name} 执行完成")
        print(f"[OK] 数据库 {dbname} 初始化完成 (共 {len(sql_files)} 个 SQL 脚本)")
    except FileNotFoundError:
        print("[ERR] 未找到 mysql 命令，请确认 MySQL Client 已加入 PATH")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] MySQL 执行失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
