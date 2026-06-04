"""
scripts/init_db.py — 初始化数据库

执行 db/schema.sql，并打印初始化结果。
用法：
    python scripts/init_db.py
"""
import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


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
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            subprocess.run(cmd, stdin=f, check=True)
        print(f"[OK] 数据库 {dbname} 初始化完成")
    except FileNotFoundError:
        print("[ERR] 未找到 mysql 命令，请确认 MySQL Client 已加入 PATH")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] MySQL 执行失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
