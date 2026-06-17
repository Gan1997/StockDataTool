# -*- coding: utf-8 -*-
"""
数据分析模块 - 计算净值、均线、回撤、收益率等指标
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from config import ANALYSIS_CONFIG
from src.logger import get_logger

logger = get_logger("Analyzer")


class DataAnalyzer:
    """数据分析器"""

    def __init__(self, config: Dict = None):
        """
        初始化分析器

        Args:
            config: 分析配置
        """
        self.config = config if config else ANALYSIS_CONFIG

    def analyze(self, df: pd.DataFrame, stock_code: str = "unknown") -> pd.DataFrame:
        """
        执行完整的数据分析

        Args:
            df: 待分析的DataFrame（应已是清洗后的数据）
            stock_code: 股票代码

        Returns:
            添加了分析指标的DataFrame
        """
        logger.info(f"开始分析数据: {stock_code}")

        # 确保按日期排序
        if 'date' in df.columns:
            df = df.sort_values('date').reset_index(drop=True)

        # 计算各项指标
        if self.config.get("calculate_returns", True):
            df = self._calculate_returns(df)

        if self.config.get("calculate_drawdown", True):
            df = self._calculate_drawdown(df)

        if self.config.get("calculate_volatility", True):
            df = self._calculate_volatility(df)

        # 计算均线
        ma_periods = self.config.get("ma_periods", [5, 10, 20, 30, 60])
        df = self._calculate_ma(df, ma_periods)

        logger.info(f"分析完成: 新增 {len(df.columns)} 列指标")
        return df

    def _calculate_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算收益率"""
        if 'close' not in df.columns:
            return df

        # 日收益率
        df['daily_return'] = df['close'].pct_change()

        # 累计收益率（净值曲线，假设初始净值为1）
        df['cumulative_return'] = (1 + df['daily_return'].fillna(0)).cumprod()

        # 年化收益率（假设252个交易日）
        trading_days = len(df)
        if trading_days > 0:
            total_return = df['cumulative_return'].iloc[-1]
            years = trading_days / 252
            df['annualized_return'] = (total_return ** (1 / years) - 1) if years > 0 else 0

        logger.debug("收益率计算完成")
        return df

    def _calculate_drawdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算回撤"""
        if 'cumulative_return' not in df.columns:
            df = self._calculate_returns(df)

        # 历史净值高点
        df['peak'] = df['cumulative_return'].cummax()

        # 回撤金额
        df['drawdown'] = df['cumulative_return'] - df['peak']

        # 回撤百分比
        df['drawdown_pct'] = (df['drawdown'] / df['peak']) * 100

        # 最大回撤
        df['max_drawdown'] = df['drawdown_pct'].cummax()

        logger.debug("回撤计算完成")
        return df

    def _calculate_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算波动率"""
        if 'daily_return' not in df.columns:
            df = self._calculate_returns(df)

        # 日波动率（20日滚动）
        df['volatility_20d'] = df['daily_return'].rolling(window=20).std() * np.sqrt(252)

        # 日波动率（60日滚动）
        df['volatility_60d'] = df['daily_return'].rolling(window=60).std() * np.sqrt(252)

        logger.debug("波动率计算完成")
        return df

    def _calculate_ma(self, df: pd.DataFrame, periods: List[int]) -> pd.DataFrame:
        """计算移动平均线"""
        if 'close' not in df.columns:
            return df

        for period in periods:
            col_name = f'ma{period}'
            df[col_name] = df['close'].rolling(window=period).mean()

        logger.debug(f"均线计算完成: {periods}")
        return df

    def get_summary_stats(self, df: pd.DataFrame, stock_code: str = "unknown") -> Dict[str, Any]:
        """
        获取汇总统计数据

        Args:
            df: DataFrame
            stock_code: 股票代码

        Returns:
            统计摘要字典
        """
        if df.empty or 'close' not in df.columns:
            return {}

        stats = {
            "stock_code": stock_code,
            "data_range": f"{df['date'].min()} ~ {df['date'].max()}" if 'date' in df.columns else "N/A",
            "trading_days": len(df),
            "start_price": df['close'].iloc[0],
            "end_price": df['close'].iloc[-1],
            "total_return": f"{((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.2f}%" if len(df) > 1 else "0%",
            "max_price": df['high'].max() if 'high' in df.columns else None,
            "min_price": df['low'].min() if 'low' in df.columns else None,
            "avg_volume": df['volume'].mean() if 'volume' in df.columns else None,
        }

        # 添加收益率相关统计
        if 'daily_return' in df.columns:
            stats["daily_return_mean"] = f"{df['daily_return'].mean() * 100:.4f}%"
            stats["daily_return_std"] = f"{df['daily_return'].std() * 100:.4f}%"
            stats["annualized_volatility"] = f"{df['daily_return'].std() * np.sqrt(252) * 100:.2f}%"

        # 添加回撤统计
        if 'drawdown_pct' in df.columns:
            stats["max_drawdown"] = f"{df['drawdown_pct'].min():.2f}%"

        # 添加均线统计
        ma_periods = self.config.get("ma_periods", [5, 10, 20, 30, 60])
        for period in ma_periods:
            col = f'ma{period}'
            if col in df.columns:
                stats[f'{col}_current'] = f"{df[col].iloc[-1]:.2f}"
                # 均线多头排列判断
                ma_cols = [f'ma{p}' for p in ma_periods if f'ma{p}' in df.columns]
                if len(ma_cols) >= 3:
                    stats[f'{col}_golden_cross'] = (
                        df[col].iloc[-1] > df[f'ma{ma_periods[0]}'].iloc[-1]
                        if f'ma{ma_periods[0]}' in df.columns else None
                    )

        return stats

    def screen_stocks(
        self,
        data_dict: Dict[str, pd.DataFrame],
        criteria: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        选股筛选

        Args:
            data_dict: Dict[stock_code, DataFrame]
            criteria: 筛选条件，如 {'annualized_return_min': 0.1, 'max_drawdown_max': -0.2}

        Returns:
            符合条件的股票列表
        """
        if criteria is None:
            criteria = {}

        logger.info(f"开始选股筛选: {len(data_dict)} 只股票")
        results = []

        for code, df in data_dict.items():
            if df.empty:
                continue

            # 分析数据
            df_analyzed = self.analyze(df.copy(), code)
            stats = self.get_summary_stats(df_analyzed, code)

            # 检查各项条件
            passed = True

            # 年化收益率 > X
            if 'annualized_return_min' in criteria:
                required = criteria['annualized_return_min']
                if 'annualized_return' not in df_analyzed.columns:
                    passed = False
                elif df_analyzed['annualized_return'].iloc[-1] < required:
                    passed = False

            # 最大回撤 < X (回撤是负数)
            if 'max_drawdown_max' in criteria:
                max_dd = criteria['max_drawdown_max']
                if 'drawdown_pct' not in df_analyzed.columns:
                    passed = False
                elif df_analyzed['drawdown_pct'].min() > max_dd:
                    passed = False

            # 均线多头排列
            if 'ma_golden_cross' in criteria and criteria['ma_golden_cross']:
                ma_periods = self.config.get("ma_periods", [5, 10, 20, 30, 60])
                ma_cols = [f'ma{p}' for p in ma_periods if f'ma{p}' in df_analyzed.columns]
                if len(ma_cols) >= 3:
                    # 短期 > 中期 > 长期
                    if not (
                        df_analyzed[ma_cols[0]].iloc[-1] > df_analyzed[ma_cols[1]].iloc[-1] > df_analyzed[ma_cols[2]].iloc[-1]
                    ):
                        passed = False

            if passed:
                results.append(stats)

        logger.info(f"筛选完成: {len(results)}/{len(data_dict)} 只股票符合条件")
        return results

    def analyze_batch(
        self,
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        批量分析多只股票

        Args:
            data_dict: Dict[stock_code, DataFrame]

        Returns:
            Dict[stock_code, DataFrame] - 添加了指标的DataFrame
        """
        logger.info(f"批量分析 {len(data_dict)} 只股票...")
        analyzed = {}

        for code, df in data_dict.items():
            analyzed[code] = self.analyze(df.copy(), code)

        return analyzed


if __name__ == "__main__":
    # 测试代码
    import pandas as pd

    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100),
        'code': ['600519'] * 100,
        'open': np.random.uniform(100, 110, 100),
        'high': np.random.uniform(110, 120, 100),
        'low': np.random.uniform(90, 100, 100),
        'close': np.random.uniform(100, 110, 100),
        'volume': np.random.uniform(1000, 5000, 100),
        'amount': np.random.uniform(100000, 500000, 100),
        'pct_chg': np.random.uniform(-5, 5, 100),
    })

    analyzer = DataAnalyzer()
    df_analyzed = analyzer.analyze(df, "600519")
    stats = analyzer.get_summary_stats(df_analyzed, "600519")

    print("统计摘要:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
