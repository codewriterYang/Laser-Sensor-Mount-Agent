"""应用程序配置，从环境变量加载。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 从项目根目录加载 .env（当前文件向上两级）
_project_root = Path(__file__).resolve().parent.parent.parent
_dotenv_path = _project_root / ".env"
load_dotenv(_dotenv_path)

# --- 语言模型 ---

LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# --- 图像模型 (Epic-3+) ---

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "doubao-seedream-4.5")
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "")


def is_llm_configured() -> bool:
    """如果 LLM 凭据已配置（非空且非占位符），返回 True。"""
    return bool(LLM_API_KEY) and LLM_API_KEY != "your_api_key_here"


def is_image_configured() -> bool:
    """如果图片模型凭据已配置（非空且非占位符），返回 True。"""
    return bool(IMAGE_API_KEY) and IMAGE_API_KEY != "your_api_key_here"
