"""端点错误处理工具 — 统一 try/except/rollback 样板代码。

使用方式:
    @handle_service_errors({
        SpecificError: ("ERROR_CODE", 404),
    })
    async def my_endpoint(..., db: Session = Depends(get_db)):
        ...
"""

from __future__ import annotations

from functools import wraps

from .response import _error


def handle_service_errors(error_map: dict[type, tuple[str, int]]):
    """装饰器：统一处理 Service 层异常，自动 commit/rollback。

    装饰后的端点函数只需写正常逻辑，异常和事务由装饰器处理。
    端点函数必须有一个名为 `db` 的 keyword 参数（通过 FastAPI Depends 注入）。

    Args:
        error_map: {异常类型: (错误码, HTTP状态码)} 映射。
                   未匹配的异常统一返回 INTERNAL_SERVER_ERROR (500)。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get("db")
            try:
                result = await func(*args, **kwargs)
                if db is not None:
                    db.commit()
                return result
            except tuple(error_map.keys()) as e:
                if db is not None:
                    db.rollback()
                for exc_type, (code, status) in error_map.items():
                    if isinstance(e, exc_type):
                        raise _error(code, str(e), status)
                raise  # 不应到达此处
            except Exception:
                if db is not None:
                    db.rollback()
                raise _error("INTERNAL_SERVER_ERROR", "意外错误", 500)
        return wrapper
    return decorator
