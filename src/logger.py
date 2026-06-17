# -*- coding: utf-8 -*-
"""
日志模块 - 统一日志管理
"""

import sys
from loguru import logger
from config import LOG_CONFIG


def setup_logger():
    """配置日志"""
    # 移除默认handler
    logger.remove()

    # 添加控制台输出
    if LOG_CONFIG["console"]:
        logger.add(
            sys.stdout,
            level=LOG_CONFIG["level"],
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        )

    # 添加文件输出
    logger.add(
        LOG_CONFIG["file"],
        level=LOG_CONFIG["level"],
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        rotation=LOG_CONFIG["rotation"],
        retention=LOG_CONFIG["retention"],
        encoding="utf-8",
    )

    return logger


def get_logger(name: str = None):
    """获取日志器"""
    if name:
        return logger.bind(name=name)
    return logger


# 初始化日志
setup_logger()
