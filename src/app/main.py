"""FastAPI 应用程序 — 激光传感器支架装配 Agent。

所有路由遵循 05_CONTRACT.md 规范。
三阶段审核：产品结构审核 → 装配流程审核 → 指导书审核。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import create_tables
from .routers import step, process, instruction, bom


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时创建数据库表。"""
    create_tables()
    yield


app = FastAPI(title="激光传感器支架装配 Agent", version="0.1.0", lifespan=lifespan)

# 注册业务路由
app.include_router(step.router)
app.include_router(process.router)
app.include_router(instruction.router)
app.include_router(bom.router)

# 过滤 uvicorn access log 中的噪音（favicon.ico、chrome devtools 等）
class _NoiseFilter(logging.Filter):
    _IGNORE = ("/favicon.ico", "/.well-known/", "/robots.txt")
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(n in msg for n in self._IGNORE)

for h in logging.getLogger("uvicorn.access").handlers:
    h.addFilter(_NoiseFilter())

# 前端静态文件
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# 导出文件（PDF 和图片）
_exports_dir = Path("exports")
_exports_dir.mkdir(exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(_exports_dir)), name="exports")


@app.get("/")
async def root():
    """提供前端 SPA 页面。"""
    return FileResponse(str(_static_dir / "index.html"))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """将 HTTPException.detail 解包为直接 JSON 响应体。"""
    return JSONResponse(status_code=exc.status_code, content=exc.detail)
