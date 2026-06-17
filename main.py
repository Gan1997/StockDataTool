# -*- coding: utf-8 -*-
"""
股票数据流水线 - 主入口

一键运行: fetch → check → clean → analyze → store → plot

用法:
    python main.py                    # 运行完整流水线
    python main.py --stock 600519     # 指定单只股票
    python main.py --mode batch       # 批量处理
    python main.py --screen           # 选股模式
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

import config
from src.logger import get_logger
from src.fetcher import StockFetcher
from src.checker import DataChecker
from src.cleaner import DataCleaner
from src.analyzer import DataAnalyzer
from src.storage import MongoStorage
from src.plotter import StockPlotter

logger = get_logger("Main")


class StockPipeline:
    """股票数据流水线"""

    def __init__(self):
        self.fetcher = StockFetcher()
        self.checker = DataChecker()
        self.cleaner = DataCleaner()
        self.analyzer = DataAnalyzer()
        self.storage = MongoStorage()
        self.plotter = StockPlotter()

    def run_single(
        self,
        stock_code: str = None,
        start_date: str = None,
        end_date: str = None,
        save_to_db: bool = True,
        generate_plots: bool = True
    ) -> Dict:
        """
        运行单只股票的完整流水线

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            save_to_db: 是否保存到数据库
            generate_plots: 是否生成图表

        Returns:
            运行结果字典
        """
        stock_code = stock_code or config.STOCK_CONFIG["stock_code"]
        start_date = start_date or config.STOCK_CONFIG["start_date"]
        end_date = end_date or config.STOCK_CONFIG["end_date"]

        logger.info(f"=" * 50)
        logger.info(f"开始流水线: {stock_code} ({start_date} ~ {end_date})")
        logger.info(f"=" * 50)

        result = {
            "stock_code": stock_code,
            "status": "success",
            "stages": {}
        }

        # Stage 1: 获取数据
        if config.RUN_MODE["fetch"]:
            try:
                logger.info("[1/6] 获取数据...")
                df = self.fetcher.fetch_daily(stock_code, start_date, end_date)
                result["stages"]["fetch"] = {"status": "success", "rows": len(df)}
                logger.info(f"获取完成: {len(df)} 条数据")
            except Exception as e:
                logger.error(f"获取数据失败: {e}")
                result["status"] = "failed"
                result["stages"]["fetch"] = {"status": "failed", "error": str(e)}
                return result

        # Stage 2: 检查数据
        if config.RUN_MODE["check"]:
            try:
                logger.info("[2/6] 检查数据...")
                check_report = self.checker.check(df, stock_code)
                result["stages"]["check"] = {
                    "status": "success",
                    "is_clean": check_report.is_clean,
                    "issues": check_report.messages
                }
                logger.info(f"检查完成: {'正常' if check_report.is_clean else '需清洗'}")
            except Exception as e:
                logger.error(f"检查数据失败: {e}")
                result["stages"]["check"] = {"status": "failed", "error": str(e)}

        # Stage 3: 清洗数据
        if config.RUN_MODE["clean"]:
            try:
                logger.info("[3/6] 清洗数据...")
                df_clean, clean_report = self.cleaner.clean_with_report(df, stock_code)
                result["stages"]["clean"] = {
                    "status": "success",
                    "original_rows": clean_report["original_rows"],
                    "final_rows": clean_report["final_rows"]
                }
                logger.info(f"清洗完成: {clean_report['final_rows']} 条数据")
            except Exception as e:
                logger.error(f"清洗数据失败: {e}")
                result["stages"]["clean"] = {"status": "failed", "error": str(e)}
                return result

        # Stage 4: 分析数据
        if config.RUN_MODE["analyze"]:
            try:
                logger.info("[4/6] 分析数据...")
                df_analyzed = self.analyzer.analyze(df_clean, stock_code)
                stats = self.analyzer.get_summary_stats(df_analyzed, stock_code)
                result["stages"]["analyze"] = {
                    "status": "success",
                    "stats": stats
                }
                logger.info(f"分析完成")
            except Exception as e:
                logger.error(f"分析数据失败: {e}")
                result["stages"]["analyze"] = {"status": "failed", "error": str(e)}

        # Stage 5: 存储数据库
        if config.RUN_MODE["store"] and save_to_db:
            try:
                logger.info("[5/6] 存储数据库...")
                with self.storage:
                    inserted = self.storage.store(df_clean, stock_code)
                result["stages"]["store"] = {
                    "status": "success",
                    "inserted": inserted
                }
                logger.info(f"存储完成: {inserted} 条记录")
            except Exception as e:
                logger.error(f"存储数据库失败: {e}")
                result["stages"]["store"] = {"status": "failed", "error": str(e)}

        # Stage 6: 生成图表
        if config.RUN_MODE["plot"] and generate_plots:
            try:
                logger.info("[6/6] 生成图表...")
                output_dir = Path(config.PLOT_CONFIG["output_dir"])
                paths = self.plotter.save_all(df_analyzed, stock_code, output_dir)
                result["stages"]["plot"] = {
                    "status": "success",
                    "paths": paths
                }
                logger.info(f"图表生成完成")
            except Exception as e:
                logger.error(f"生成图表失败: {e}")
                result["stages"]["plot"] = {"status": "failed", "error": str(e)}

        logger.info(f"=" * 50)
        logger.info(f"流水线完成: {stock_code}")
        logger.info(f"=" * 50)

        return result

    def run_batch(
        self,
        stock_codes: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        save_to_db: bool = True,
        generate_plots: bool = True
    ) -> Dict[str, Dict]:
        """
        批量处理多只股票

        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            save_to_db: 是否保存到数据库
            generate_plots: 是否生成图表

        Returns:
            Dict[stock_code, result]
        """
        if stock_codes is None:
            stock_codes = config.STOCK_CONFIG["stock_list"]

        logger.info(f"=" * 50)
        logger.info(f"批量处理: {len(stock_codes)} 只股票")
        logger.info(f"=" * 50)

        results = {}

        for i, code in enumerate(stock_codes, 1):
            logger.info(f"\n[{i}/{len(stock_codes)}] 处理 {code}...")
            try:
                results[code] = self.run_single(
                    code, start_date, end_date,
                    save_to_db=save_to_db,
                    generate_plots=generate_plots
                )
            except Exception as e:
                logger.error(f"处理 {code} 失败: {e}")
                results[code] = {"status": "failed", "error": str(e)}

        # 汇总结果
        success_count = sum(1 for r in results.values() if r.get("status") == "success")
        logger.info(f"\n批量处理完成: {success_count}/{len(stock_codes)} 成功")

        return results

    def run_screen(
        self,
        stock_codes: List[str] = None,
        criteria: Dict = None,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        选股筛选

        Args:
            stock_codes: 股票池
            criteria: 筛选条件
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            符合条件的股票列表
        """
        if stock_codes is None:
            stock_codes = config.STOCK_CONFIG["stock_list"]

        if criteria is None:
            criteria = {
                "annualized_return_min": 0.1,  # 年化收益 > 10%
                "max_drawdown_max": -0.2,       # 最大回撤 < -20%
            }

        logger.info(f"=" * 50)
        logger.info(f"选股筛选: {len(stock_codes)} 只股票")
        logger.info(f"条件: {criteria}")
        logger.info(f"=" * 50)

        # 批量获取
        logger.info("获取数据...")
        data_dict = self.fetcher.fetch_batch(stock_codes, start_date, end_date)

        # 批量清洗
        logger.info("清洗数据...")
        cleaned_dict = self.cleaner.clean_batch(data_dict)

        # 批量分析
        logger.info("分析数据...")
        analyzed_dict = self.analyzer.analyze_batch(cleaned_dict)

        # 筛选
        logger.info("筛选...")
        results = self.analyzer.screen_stocks(analyzed_dict, criteria)

        # 输出结果
        logger.info(f"\n筛选完成: {len(results)} 只股票符合条件")
        for r in results:
            logger.info(f"  {r['stock_code']}: "
                       f"年化收益={r.get('annualized_return', 'N/A')}, "
                       f"最大回撤={r.get('max_drawdown', 'N/A')}")

        return results


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="股票数据流水线工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                                    # 运行完整流水线
  python main.py --stock 600519                     # 处理单只股票
  python main.py --mode batch                        # 批量处理
  python main.py --screen                           # 选股模式
  python main.py --no-db                            # 不存数据库
  python main.py --no-plot                          # 不生成图表
        """
    )

    parser.add_argument(
        "--stock", "-s",
        type=str,
        help="股票代码，如 600519"
    )

    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["single", "batch"],
        default="single",
        help="运行模式: single(默认) 或 batch"
    )

    parser.add_argument(
        "--screen",
        action="store_true",
        help="选股模式"
    )

    parser.add_argument(
        "--no-db",
        action="store_true",
        help="跳过数据库存储"
    )

    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="跳过图表生成"
    )

    parser.add_argument(
        "--start",
        type=str,
        help="开始日期，如 2024-01-01"
    )

    parser.add_argument(
        "--end",
        type=str,
        help="结束日期，如 2024-12-31"
    )

    return parser.parse_args()


def main():
    """主入口"""
    args = parse_args()

    pipeline = StockPipeline()

    if args.screen:
        # 选股模式
        results = pipeline.run_screen(
            stock_codes=[args.stock] if args.stock else None,
            start_date=args.start,
            end_date=args.end
        )
        # 绘制选股结果
        if results:
            plotter = StockPlotter()
            output_dir = Path(config.PLOT_CONFIG["output_dir"])
            plotter.plot_screening_result(results, output_dir / "screening_result.html")

    elif args.mode == "batch" or args.stock is None:
        # 批量模式
        pipeline.run_batch(
            save_to_db=not args.no_db,
            generate_plots=not args.no_plot,
            start_date=args.start,
            end_date=args.end
        )

    else:
        # 单股模式
        pipeline.run_single(
            stock_code=args.stock,
            save_to_db=not args.no_db,
            generate_plots=not args.no_plot,
            start_date=args.start,
            end_date=args.end
        )


if __name__ == "__main__":
    main()
