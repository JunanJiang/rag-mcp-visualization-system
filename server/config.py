"""统一配置管理。

所有配置项集中在此文件，优先从环境变量读取，回落到适合本地开发的默认值。
其他模块通过 ``from config import cfg`` 使用配置。
"""

import os
from pathlib import Path


# 路径
_SERVER_DIR = Path(__file__).parent
_PROJECT_ROOT = _SERVER_DIR.parent

UPLOAD_FOLDER = Path(os.environ.get("SIMUREPORT_UPLOAD_FOLDER", str(_SERVER_DIR / "uploads")))
OUTPUT_FOLDER = Path(os.environ.get("SIMUREPORT_OUTPUT_FOLDER", str(_SERVER_DIR / "outputs")))
KB_FOLDER = Path(os.environ.get("SIMUREPORT_KB_FOLDER", str(_PROJECT_ROOT / "知识库")))
KB_UPLOAD_FOLDER = Path(os.environ.get("SIMUREPORT_KB_UPLOAD_FOLDER", str(_SERVER_DIR / "kb_uploads")))
CHROMA_PERSIST_DIR = os.environ.get("SIMUREPORT_CHROMA_DIR", str(_SERVER_DIR / "chroma_db"))
DB_PATH = Path(os.environ.get("SIMUREPORT_DB_PATH", str(_SERVER_DIR / "simureport.db")))

# Flask
MAX_CONTENT_LENGTH = int(os.environ.get("SIMUREPORT_MAX_UPLOAD_MB", "500")) * 1024 * 1024

# JWT
JWT_SECRET = os.environ.get("JWT_SECRET", "simureport-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))

# LLM 与联网检索凭据只从环境变量读取
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

# 数据包规范版本
DATAPACKAGE_SPEC_VERSION = "1.0"


# 确保关键目录存在
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
KB_UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
