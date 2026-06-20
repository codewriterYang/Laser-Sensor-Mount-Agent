"""标准 API 响应辅助函数。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(data: dict) -> dict:
    return {"success": True, "data": data, "timestamp": _now()}


def _error(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"success": False, "error": {"code": code, "message": message}, "timestamp": _now()},
    )
