"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_project_root = Path(__file__).resolve().parent.parent.parent
_dotenv_path = _project_root / ".env"
load_dotenv(_dotenv_path)

# --- Language Model ---

LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# --- Image Model (Epic-3+) ---

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "doubao-seedream-4.5")
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "")


def is_llm_configured() -> bool:
    """Return True if LLM credentials are provided (not empty and not placeholder)."""
    return bool(LLM_API_KEY) and LLM_API_KEY != "your_api_key_here"
