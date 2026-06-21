# -*- coding: utf-8 -*-
"""
数据清洗模块 - 类型转换、日期排序、去缺失、去重
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from config import CLEAN_CONFIG
from src.logger import get_logger
from src.checker import CheckReport, DataChecker

logger = get_logger("Cleaner")


class DataCleaner:
    """数据清洗器"""

    def __init__(self, config: Dict = None):
        """
        初始化清洗器

        Args:
            config: 清洗配置
        """
        self.config = config if config else CLEAN_CONFIG

    def clean(
        self,
        df: pd.DataFrame,
        stock_code: str = "unknown",
        report: CheckReport = None
    ) -> pd.DataFrame:
        """
        执行完整的数据清洗

        Args:
            df: 待清洗的DataFrame
            stock_code: 股票代码
            report: 可选的检查报告，用于针对性清洗

        Returns:
            清洗后的DataFrame
        """
        logger.info(f"开始清洗数据: {stock_code}")
        original_len = len(df)

        # 创建副本避免修改原始数据
        df_clean = df.copy()

        # 按配置执行清洗步骤
        if self.config.get("sort_by_date", True):
            df_clean = self._sort_by_date(df_clean)

        if self.config.get("drop_duplicates", True):
            df_clean = self._remove_duplicates(df_clean)

        if self.config.get("fill_missing", False):
            df_clean = self._fill_missing(df_clean)
        else:
            df_clean = self._drop_missing(df_clean)

        if self.config.get("convert_types", True):
            df_clean = self._convert_types(df_clean)

        # 自定义清洗规则
        df_clean = self._clean_price_anomalies(df_clean)

        removed = original_len - len(df_clean)
        logger.info(f"清洗完成: 移除 {removed} 条数据，剩余 {len(df_clean)} 条")

        return df_clean

    def _sort_by_date(self, df: pd.DataFrame) -> pd.DataFrame:
        """按日期排序"""
        if 'date' not in df.columns:
            return df

        df = df.sort_values('date').reset_index(drop=True)
        logger.debug("已完成日期排序")
        return df

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """删除重复行"""
        if 'date' not in df.columns:
            return df

        before = len(df)
        df = df.drop_duplicates(subset=['date'], keep='last')
        removed = before - len(df)

        if removed > 0:
            logger.info(f"删除了 {removed} 条重复数据")

        return df

    def _drop_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """删除缺失值"""
        before = len(df)
        df = df.dropna()
        removed = before - len(df)

        if removed > 0:
            logger.info(f"删除了 {removed} 条含缺失值的数据")

        return df

    def _fill_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """填充缺失值（前向填充）"""
        # 按日期排序后前向填充
        if 'date' in df.columns:
            df = df.sort_values('date')

        # 数值列前向填充
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = df[numeric_cols].fillna(method='ffill')

        # 剩余缺失值后向填充
        df[numeric_cols] = df[numeric_cols].fillna(method='bfill')

        logger.debug("已完成缺失值填充")
        return df

    def _convert_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """类型转换"""
        # 确保日期列是datetime类型
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')

        # 数值列转换
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.debug("类型转换完成")
        return df

    def _clean_price_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗价格异常"""
        # 删除价格为0或负数的行
        if 'close' in df.columns:
            before = len(df)
            df = df[df['close'] > 0]
            removed = before - len(df)
            if removed > 0:
                logger.info(f"删除了 {removed} 条价格为0/负的数据")

        return df

    def clean_with_report(
        self,
        df: pd.DataFrame,
        stock_code: str = "unknown",
        report: CheckReport = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        清洗数据并返回详细报告

        Args:
            df: 待清洗的DataFrame
            stock_code: 股票代码
            report: 可选的检查报告

        Returns:
            (清洗后的DataFrame, 清洗报告)
        """
        original_len = len(df)
        clean_report = {
            "original_rows": original_len,
            "steps": [],
        }

        # 执行清洗
        df_clean = self.clean(df, stock_code)

        clean_report["final_rows"] = len(df_clean)
        clean_report["removed_rows"] = original_len - len(df_clean)
        clean_report["removed_pct"] = (
            f"{clean_report['removed_rows'] / original_len * 100:.2f}%"
            if original_len > 0 else "0%"
        )

        return df_clean, clean_report

    def clean_batch(
        self,
        data_dict: Dict[str, pd.DataFrame],
        reports: Dict[str, CheckReport] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        批量清洗多只股票数据

        Args:
            data_dict: Dict[stock_code, DataFrame]
            reports: 可选的检查报告字典

        Returns:
            Dict[stock_code, DataFrame]
        """
        logger.info(f"批量清洗 {len(data_dict)} 只股票...")
        cleaned = {}

        for code, df in data_dict.items():
            report = reports.get(code) if reports else None
            cleaned[code] = self.clean(df, code, report)

        success_count = sum(1 for df in cleaned.values() if not df.empty)
        logger.info(f"批量清洗完成: {success_count}/{len(data_dict)} 成功")

        return cleaned


if __name__ == "__main__":
    # 测试代码
    import pandas as pd

    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10),
        'code': ['600519'] * 10,
        'open': [100, 101, 102, None, 104, 105, 106, 107, 108, 109],
        'high': [105, 106, 107, 0, 109, 110, 111, 112, 113, 114],
        'low': [99, 100, 101, 0, 103, 104, 105, 106, 107, 108],
        'close': [103, 104, 105, 0, 107, 108, 109, 110, 111, 112],
        'volume': [1000, 2000, 3000, 0, 5000, 6000, 7000, 8000, 9000, 10000],
    })

    cleaner = DataCleaner()
    df_clean, report = cleaner.clean_with_report(df, "600519")
    print(f"清洗报告: {report}")
    print(df_clean.head())
