# -*- coding: utf-8 -*-
"""
数据检查模块 - 检测缺失值、重复行、停牌断点、异常价格
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, field

from config import CHECK_CONFIG
from src.logger import get_logger

logger = get_logger("Checker")


@dataclass
class CheckReport:
    """数据检查报告"""
    stock_code: str
    total_rows: int
    missing_report: Dict[str, int] = field(default_factory=dict)
    duplicate_count: int = 0
    suspended_points: List[str] = field(default_factory=list)
    anomaly_report: Dict[str, List[Any]] = field(default_factory=list)
    is_clean: bool = True
    messages: List[str] = field(default_factory=list)

    def add_message(self, msg: str):
        self.messages.append(msg)

    def summary(self) -> str:
        """生成检查报告摘要"""
        lines = [
            f"=== 数据检查报告: {self.stock_code} ===",
            f"总行数: {self.total_rows}",
            f"缺失值: {sum(self.missing_report.values()) if self.missing_report else 0}",
            f"重复行: {self.duplicate_count}",
            f"停牌断点: {len(self.suspended_points)}",
            f"异常记录: {len(self.anomaly_report)}",
            f"数据状态: {'✓ 正常' if self.is_clean else '✗ 需清洗'}",
        ]
        if self.messages:
            lines.append("--- 详情 ---")
            lines.extend(self.messages)
        return "\n".join(lines)


class DataChecker:
    """数据检查器"""

    def __init__(self, config: Dict = None):
        """
        初始化检查器

        Args:
            config: 检查配置
        """
        self.config = config if config else CHECK_CONFIG

    def check(self, df: pd.DataFrame, stock_code: str = "unknown") -> CheckReport:
        """
        执行完整的数据检查

        Args:
            df: 待检查的DataFrame
            stock_code: 股票代码

        Returns:
            CheckReport: 检查报告
        """
        report = CheckReport(stock_code=stock_code, total_rows=len(df))

        logger.info(f"开始检查数据: {stock_code}")

        if df.empty:
            report.is_clean = False
            report.add_message("数据为空")
            return report

        # 执行各项检查
        if self.config.get("check_missing", True):
            self._check_missing(df, report)

        if self.config.get("check_duplicate", True):
            self._check_duplicate(df, report)

        if self.config.get("check_suspended", True):
            self._check_suspended(df, report)

        if self.config.get("check_anomaly", True):
            self._check_anomaly(df, report)

        # 判断整体状态
        report.is_clean = (
            report.duplicate_count == 0
            and len(report.suspended_points) == 0
            and len(report.anomaly_report) == 0
            and all(v == 0 for v in report.missing_report.values())
        )

        logger.info(f"检查完成: {'数据正常' if report.is_clean else '发现问题'}")
        return report

    def _check_missing(self, df: pd.DataFrame, report: CheckReport):
        """检查缺失值"""
        missing = df.isnull().sum()
        missing = missing[missing > 0]

        if not missing.empty:
            report.missing_report = missing.to_dict()
            for col, count in missing.items():
                report.add_message(f"缺失值 - {col}: {count}")

    def _check_duplicate(self, df: pd.DataFrame, report: CheckReport):
        """检查重复行"""
        if 'date' not in df.columns:
            return

        dup_count = df.duplicated(subset=['date']).sum()
        report.duplicate_count = dup_count

        if dup_count > 0:
            report.add_message(f"发现 {dup_count} 条重复日期记录")

    def _check_suspended(self, df: pd.DataFrame, report: CheckReport):
        """检查停牌断点 - 通过检测成交量为0且价格不变的连续日期"""
        if 'volume' not in df.columns or 'close' not in df.columns:
            return

        df_sorted = df.sort_values('date').reset_index(drop=True)

        # 找出成交量为0的日期
        zero_volume = df_sorted[df_sorted['volume'] == 0]['date'].tolist()

        if zero_volume:
            report.suspended_points = [str(d) for d in zero_volume[:10]]  # 只记录前10个
            if len(zero_volume) > 10:
                report.suspended_points.append(f"...共{len(zero_volume)}个")
            report.add_message(f"发现 {len(zero_volume)} 个停牌日")

    def _check_anomaly(self, df: pd.DataFrame, report: CheckReport):
        """检查异常价格"""
        price_min = self.config.get("price_min", 0.01)
        price_max = self.config.get("price_max", 10000)
        pct_change_max = self.config.get("pct_change_max", 20)

        anomalies = []

        # 检查价格范围
        for col in ['open', 'high', 'low', 'close']:
            if col not in df.columns:
                continue

            # 负价格
            neg_mask = df[col] < 0
            if neg_mask.any():
                neg_count = neg_mask.sum()
                anomalies.append(f"{col}负价格: {neg_count}条")

            # 极端价格
            extreme_mask = (df[col] < price_min) | (df[col] > price_max)
            if extreme_mask.any():
                extreme_count = extreme_mask.sum()
                anomalies.append(f"{col}极端价格: {extreme_count}条")

        # 检查涨跌幅
        if 'pct_chg' in df.columns:
            pct_anomaly = (df['pct_chg'].abs() > pct_change_max)
            if pct_anomaly.any():
                pct_count = pct_anomaly.sum()
                anomalies.append(f"涨跌幅异常: {pct_count}条")

        if anomalies:
            report.anomaly_report = anomalies
            for a in anomalies:
                report.add_message(f"异常 - {a}")

    def check_batch(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, CheckReport]:
        """
        批量检查多只股票数据

        Args:
            data_dict: Dict[stock_code, DataFrame]

        Returns:
            Dict[stock_code, CheckReport]
        """
        logger.info(f"批量检查 {len(data_dict)} 只股票...")
        reports = {}

        for code, df in data_dict.items():
            reports[code] = self.check(df, code)

        # 汇总
        clean_count = sum(1 for r in reports.values() if r.is_clean)
        logger.info(f"批量检查完成: {clean_count}/{len(data_dict)} 数据正常")

        return reports


if __name__ == "__main__":
    # 测试代码
    import pandas as pd
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10),
        'code': ['600519'] * 10,
        'open': [100, 101, 102, 0, 104, 105, 106, 107, 108, 109],
        'high': [105, 106, 107, 0, 109, 110, 111, 112, 113, 114],
        'low': [99, 100, 101, 0, 103, 104, 105, 106, 107, 108],
        'close': [103, 104, 105, 0, 107, 108, 109, 110, 111, 112],
        'volume': [1000, 2000, 3000, 0, 5000, 6000, 7000, 8000, 9000, 10000],
        'pct_chg': [1.0, 1.0, 1.0, -100, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    })

    checker = DataChecker()
    report = checker.check(df, "600519")
    print(report.summary())
