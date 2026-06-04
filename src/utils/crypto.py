"""
utils/crypto.py — 密码哈希工具
"""
import bcrypt


def hash_password(plain: str) -> str:
    """明文密码 -> bcrypt 哈希（$2b$12$...）"""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文 vs 哈希"""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
