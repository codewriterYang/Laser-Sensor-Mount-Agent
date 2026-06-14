"""项目日志配置 — 统一格式，同时输出到控制台和文件。"""

import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 北京时间 (UTC+8)
_BEIJING_TZ = timezone(timedelta(hours=8))


class _BeijingFormatter(logging.Formatter):
    """使用北京时间的日志格式化器。"""

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=_BEIJING_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

LOGS_DIR = Path("logs")
LOG_FILE = LOGS_DIR / "app.log"


def setup_logging(level: str = "INFO") -> logging.Logger:
    """初始化项目日志系统。

    输出到：
    - 控制台（标准输出）
    - 文件 logs/app.log（自动轮转）
    """
    LOGS_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger("laser_sensor_mount")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 统一日志格式（北京时间）
    fmt = _BeijingFormatter(
        fmt="%(asctime)s | %(levelname)-7s | %(module)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # 文件输出
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


# 全局 logger 实例
logger = setup_logging()
