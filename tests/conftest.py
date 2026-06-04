"""
tests/conftest.py — pytest 公共 fixture
- 自动把项目根目录加进 sys.path
- 加载 .env
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env（在测试自己的临时 MySQL 之前生效）
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
