# -*- coding: utf-8 -*-
"""
数据获取模块 - 从Baostock获取股票数据
"""

import baostock as bs
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import time

from config import BAOSTOCK_CONFIG, STOCK_CONFIG
from src.logger import get_logger

logger = get_logger("Fetcher")


class StockFetcher:
    """股票数据获取器"""

    def __init__(self, use_cache: bool = True, cache_dir: Path = None):
        """
        初始化获取器

        Args:
            use_cache: 是否使用本地缓存
            cache_dir: 缓存目录
        """
        self.use_cache = use_cache if use_cache is not None else BAOSTOCK_CONFIG["use_cache"]
        self.cache_dir = cache_dir if cache_dir else BAOSTOCK_CONFIG["cache_dir"]
        self._logged_in = False

    def _ensure_login(self):
        """确保已登录Baostock"""
        if not self._logged_in:
            logger.info("登录Baostock...")
            lg = bs.login()
            if lg.error_code != '0':
                raise ConnectionError(f"Baostock登录失败: {lg.error_msg}")
            self._logged_in = True
            logger.info("Baostock登录成功")

    def _logout(self):
        """登出Baostock"""
        if self._logged_in:
            bs.logout()
            self._logged_in = False

    def _get_cache_path(self, stock_code: str, start_date: str, end_date: str) -> Path:
        """获取缓存文件路径"""
        filename = f"{stock_code}_{start_date}_{end_date}.csv"
        return self.cache_dir / filename

    def _normalize_stock_code(self, stock_code: str) -> str:
        """
        标准化股票代码

        Args:
            stock_code: 原始股票代码，如 600519 或 sh.600519

        Returns:
            Baostock格式的股票代码，如 sh.600519
        """
        stock_code = stock_code.strip()

        # 判断交易所前缀
        if stock_code.startswith("6"):
            # 上证
            prefix = "sh"
        elif stock_code.startswith(("0", "3")):
            # 深证
            prefix = "sz"
        else:
            prefix = "sh"  # 默认上证

        # 去掉已有前缀
        if "." in stock_code:
            return stock_code.lower()

        return f"{prefix}.{stock_code}"

    def fetch_daily(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        adjust: str = "3"
    ) -> pd.DataFrame:
        """
        获取日K线数据

        Args:
            stock_code: 股票代码，如 600519
            start_date: 开始日期，格式 YYYY-MM-DD
            end_date: 结束日期，格式 YYYY-MM-DD
            adjust: 复权类型，3=后复权(默认)，2=前复权，0=不复权

        Returns:
            DataFrame，包含 date, code, open, high, low, close, volume
        """
        # 使用配置默认值
        if start_date is None:
            start_date = STOCK_CONFIG["start_date"]
        if end_date is None:
            end_date = STOCK_CONFIG["end_date"]

        stock_code = self._normalize_stock_code(stock_code)
        cache_path = self._get_cache_path(stock_code, start_date, end_date)

        # 检查缓存
        if self.use_cache and cache_path.exists():
            logger.info(f"从缓存加载: {stock_code} ({start_date} ~ {end_date})")
            df = pd.read_csv(cache_path)
            df['date'] = pd.to_datetime(df['date'])
            return df

        # 获取数据
        logger.info(f"从Baostock获取数据: {stock_code} ({start_date} ~ {end_date})")
        self._ensure_login()

        rs = bs.query_history_k_data_plus(
            stock_code,
            "date,code,open,high,low,close,volume",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjust
        )

        if rs.error_code != '0':
            raise ValueError(f"获取数据失败: {rs.error_msg}")

        # 转换为DataFrame
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())

        df = pd.DataFrame(data_list, columns=rs.fields)

        # 类型转换
        numeric_fields = ['open', 'high', 'low', 'close', 'volume']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = pd.to_numeric(df[field], errors='coerce')

        df['date'] = pd.to_datetime(df['date'])

        # 保存缓存
        if self.use_cache:
            df.to_csv(cache_path, index=False, encoding='utf-8')
            logger.info(f"数据已缓存: {cache_path}")

        logger.info(f"成功获取 {len(df)} 条数据")
        time.sleep(1)  # 避免请求过快
        return df

    def fetch_batch(
        self,
        stock_codes: List[str] = None,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票数据

        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict[stock_code, DataFrame]
        """
        if stock_codes is None:
            stock_codes = STOCK_CONFIG["stock_list"]

        if start_date is None:
            start_date = STOCK_CONFIG["start_date"]
        if end_date is None:
            end_date = STOCK_CONFIG["end_date"]

        logger.info(f"批量获取 {len(stock_codes)} 只股票数据...")
        results = {}

        for i, code in enumerate(stock_codes, 1):
            try:
                logger.info(f"[{i}/{len(stock_codes)}] 正在获取: {code}")
                df = self.fetch_daily(code, start_date, end_date)
                results[code] = df
            except Exception as e:
                logger.error(f"获取 {code} 失败: {e}")
                results[code] = pd.DataFrame()

        success_count = sum(1 for df in results.values() if not df.empty)
        logger.info(f"批量获取完成: {success_count}/{len(stock_codes)} 成功")

        return results

    def fetch_with_retry(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        max_retries: int = 3
    ) -> pd.DataFrame:
        """
        带重试的数据获取

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            max_retries: 最大重试次数

        Returns:
            DataFrame
        """
        for attempt in range(1, max_retries + 1):
            try:
                return self.fetch_daily(stock_code, start_date, end_date)
            except Exception as e:
                logger.warning(f"获取失败 (尝试 {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    raise
                self._logged_in = False  # 重置登录状态

        return pd.DataFrame()

    def __enter__(self):
        """上下文管理器入口"""
        self._ensure_login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self._logout()
        return False


if __name__ == "__main__":
    # 测试代码
    with StockFetcher() as fetcher:
        df = fetcher.fetch_daily("600519", "2024-01-01", "2024-06-30")
        print(df.head())
