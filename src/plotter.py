# -*- coding: utf-8 -*-
"""
绘图模块 - 使用Plotly生成专业分析图表
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import PLOT_CONFIG
from src.logger import get_logger

logger = get_logger("Plotter")


class StockPlotter:
    """股票绘图器"""

    def __init__(self, config: Dict = None):
        """
        初始化绘图器

        Args:
            config: 绘图配置
        """
        self.config = config if config else PLOT_CONFIG

    def plot_candlestick(
        self,
        df: pd.DataFrame,
        stock_code: str = "unknown",
        show_ma: bool = True,
        show_volume: bool = True,
        save_path: Path = None
    ) -> go.Figure:
        """
        绘制K线图

        Args:
            df: DataFrame，需包含 date, open, high, low, close, volume
            stock_code: 股票代码
            show_ma: 是否显示均线
            show_volume: 是否显示成交量
            save_path: 保存路径

        Returns:
            Plotly Figure对象
        """
        if df.empty:
            logger.warning("数据为空，跳过绘图")
            return None

        # 创建子图
        if show_volume:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.7, 0.3],
                subplot_titles=('K线图', '成交量')
            )
        else:
            fig = make_subplots(rows=1, cols=1)

        # K线
        fig.add_trace(
            go.Candlestick(
                x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K线',
                increasing_line_color=self.config['theme']['up_color'],
                decreasing_line_color=self.config['theme']['down_color'],
            ),
            row=1 if show_volume else 1, col=1
        )

        # 添加均线
        if show_ma:
            ma_periods = [5, 10, 20, 30, 60]
            colors = self.config['theme']['ma_colors']

            for i, period in enumerate(ma_periods):
                col = f'ma{period}'
                if col in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df['date'],
                            y=df[col],
                            mode='lines',
                            name=f'MA{period}',
                            line=dict(color=colors[i % len(colors)], width=1.5)
                        ),
                        row=1 if show_volume else 1, col=1
                    )

        # 添加成交量
        if show_volume and 'volume' in df.columns:
            colors = [
                self.config['theme']['up_color'] if df['close'].iloc[i] >= df['open'].iloc[i]
                else self.config['theme']['down_color']
                for i in range(len(df))
            ]

            fig.add_trace(
                go.Bar(
                    x=df['date'],
                    y=df['volume'],
                    name='成交量',
                    marker_color=colors,
                    opacity=0.7
                ),
                row=2, col=1
            )

        # 更新布局
        fig.update_layout(
            title=f'{stock_code} K线图',
            width=self.config['width'],
            height=self.config['height'] if show_volume else self.config['height'] * 0.7,
            template=self.config['template'],
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # 更新Y轴标签
        fig.update_yaxes(title_text="价格", row=1, col=1)
        if show_volume:
            fig.update_yaxes(title_text="成交量", row=2, col=1)

        # 保存
        if save_path:
            fig.write_html(save_path)
            logger.info(f"图表已保存: {save_path}")

        return fig

    def plot_drawdown(
        self,
        df: pd.DataFrame,
        stock_code: str = "unknown",
        save_path: Path = None
    ) -> go.Figure:
        """
        绘制回撤图

        Args:
            df: DataFrame，需包含 date, drawdown_pct
            stock_code: 股票代码
            save_path: 保存路径

        Returns:
            Plotly Figure对象
        """
        if df.empty or 'drawdown_pct' not in df.columns:
            logger.warning("缺少回撤数据，跳过绘图")
            return None

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['drawdown_pct'],
                mode='lines',
                name='回撤',
                fill='tozeroy',
                fillcolor='rgba(239, 83, 80, 0.3)',
                line=dict(color=self.config['theme']['down_color'], width=1.5)
            )
        )

        fig.update_layout(
            title=f'{stock_code} 回撤图',
            width=self.config['width'],
            height=self.config['height'] * 0.6,
            template=self.config['template'],
            yaxis_title='回撤 (%)',
            showlegend=False
        )

        if save_path:
            fig.write_html(save_path)
            logger.info(f"回撤图已保存: {save_path}")

        return fig

    def plot_returns(
        self,
        df: pd.DataFrame,
        stock_code: str = "unknown",
        benchmark_df: pd.DataFrame = None,
        save_path: Path = None
    ) -> go.Figure:
        """
        绘制收益率对比图

        Args:
            df: DataFrame，需包含 date, cumulative_return
            stock_code: 股票代码
            benchmark_df: 基准数据DataFrame
            save_path: 保存路径

        Returns:
            Plotly Figure对象
        """
        if df.empty or 'cumulative_return' not in df.columns:
            logger.warning("缺少收益率数据，跳过绘图")
            return None

        fig = go.Figure()

        # 股票收益率
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['cumulative_return'],
                mode='lines',
                name=stock_code,
                line=dict(width=2)
            )
        )

        # 基准收益率
        if benchmark_df is not None and 'cumulative_return' in benchmark_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=benchmark_df['date'],
                    y=benchmark_df['cumulative_return'],
                    mode='lines',
                    name='基准',
                    line=dict(width=1.5, dash='dash')
                )
            )

        # 添加参考线
        fig.add_hline(y=1.0, line_dash="dot", line_color="gray", opacity=0.5)

        fig.update_layout(
            title=f'{stock_code} 累计收益率',
            width=self.config['width'],
            height=self.config['height'] * 0.6,
            template=self.config['template'],
            yaxis_title='净值',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        if save_path:
            fig.write_html(save_path)
            logger.info(f"收益率图已保存: {save_path}")

        return fig

    def plot_comparison(
        self,
        data_dict: Dict[str, pd.DataFrame],
        metric: str = "cumulative_return",
        title: str = "股票对比",
        save_path: Path = None
    ) -> go.Figure:
        """
        绘制多股票对比图

        Args:
            data_dict: Dict[stock_code, DataFrame]
            metric: 对比指标，如 'cumulative_return', 'close'
            title: 图表标题
            save_path: 保存路径

        Returns:
            Plotly Figure对象
        """
        fig = go.Figure()

        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']

        for i, (code, df) in enumerate(data_dict.items()):
            if df.empty or metric not in df.columns:
                continue

            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df[metric],
                    mode='lines',
                    name=code,
                    line=dict(color=colors[i % len(colors)], width=1.5)
                )
            )

        fig.update_layout(
            title=title,
            width=self.config['width'],
            height=self.config['height'] * 0.7,
            template=self.config['template'],
            yaxis_title=metric,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        if save_path:
            fig.write_html(save_path)
            logger.info(f"对比图已保存: {save_path}")

        return fig

    def plot_screening_result(
        self,
        results: List[Dict[str, Any]],
        save_path: Path = None
    ) -> go.Figure:
        """
        绘制选股结果表格

        Args:
            results: 选股结果列表
            save_path: 保存路径

        Returns:
            Plotly Figure对象
        """
        if not results:
            logger.warning("选股结果为空，跳过绘图")
            return None

        df = pd.DataFrame(results)

        # 表格数据
        fig = go.Figure(data=[
            go.Table(
                header=dict(
                    values=list(df.columns),
                    fill_color='#1f77b4',
                    align='center',
                    font=dict(color='white', size=12),
                    height=30
                ),
                cells=dict(
                    values=[df[col] for col in df.columns],
                    fill_color='#f8f9fa',
                    align='center',
                    font=dict(size=11),
                    height=25
                )
            )
        ])

        fig.update_layout(
            title='选股结果',
            width=min(1200, len(df.columns) * 150),
            height=max(300, len(df) * 35 + 80),
        )

        if save_path:
            fig.write_html(save_path)
            logger.info(f"选股结果表已保存: {save_path}")

        return fig

    def plot_volatility(
        self,
        df: pd.DataFrame,
        stock_code: str = "unknown",
        save_path: Path = None
    ) -> go.Figure:
        """
        绘制波动率图

        Args:
            df: DataFrame，需包含 date, volatility_20d, volatility_60d
            stock_code: 股票代码
            save_path: 保存路径

        Returns:
            Plotly Figure对象
        """
        if df.empty:
            logger.warning("数据为空，跳过绘图")
            return None

        fig = go.Figure()

        if 'volatility_20d' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['volatility_20d'] * 100,
                    mode='lines',
                    name='20日波动率',
                    line=dict(color='#FF6B6B', width=1.5)
                )
            )

        if 'volatility_60d' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['volatility_60d'] * 100,
                    mode='lines',
                    name='60日波动率',
                    line=dict(color='#4ECDC4', width=1.5)
                )
            )

        fig.update_layout(
            title=f'{stock_code} 历史波动率',
            width=self.config['width'],
            height=self.config['height'] * 0.6,
            template=self.config['template'],
            yaxis_title='波动率 (%)',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        if save_path:
            fig.write_html(save_path)
            logger.info(f"波动率图已保存: {save_path}")

        return fig

    def save_all(
        self,
        df: pd.DataFrame,
        stock_code: str,
        output_dir: Path = None,
        include_benchmark: bool = False,
        benchmark_df: pd.DataFrame = None
    ) -> Dict[str, str]:
        """
        保存所有图表

        Args:
            df: DataFrame
            stock_code: 股票代码
            output_dir: 输出目录
            include_benchmark: 是否包含基准对比
            benchmark_df: 基准数据

        Returns:
            Dict[str, str] - 各图表路径
        """
        if output_dir is None:
            output_dir = Path(self.config['output_dir'])

        output_dir.mkdir(parents=True, exist_ok=True)

        paths = {}
        prefix = f"{stock_code}_"

        # K线图
        fig = self.plot_candlestick(df, stock_code)
        if fig:
            path = output_dir / f"{prefix}candlestick.html"
            fig.write_html(path)
            paths['candlestick'] = str(path)

        # 回撤图
        fig = self.plot_drawdown(df, stock_code)
        if fig:
            path = output_dir / f"{prefix}drawdown.html"
            fig.write_html(path)
            paths['drawdown'] = str(path)

        # 收益率图
        fig = self.plot_returns(df, stock_code, benchmark_df if include_benchmark else None)
        if fig:
            path = output_dir / f"{prefix}returns.html"
            fig.write_html(path)
            paths['returns'] = str(path)

        # 波动率图
        if 'volatility_20d' in df.columns or 'volatility_60d' in df.columns:
            fig = self.plot_volatility(df, stock_code)
            if fig:
                path = output_dir / f"{prefix}volatility.html"
                fig.write_html(path)
                paths['volatility'] = str(path)

        logger.info(f"所有图表已保存到: {output_dir}")
        return paths


if __name__ == "__main__":
    # 测试代码
    import pandas as pd

    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100),
        'open': [100 + i * 0.1 for i in range(100)],
        'high': [105 + i * 0.1 for i in range(100)],
        'low': [95 + i * 0.1 for i in range(100)],
        'close': [102 + i * 0.1 for i in range(100)],
        'volume': [1000 + i * 10 for i in range(100)],
        'pct_chg': [1.0 for i in range(100)],
        'ma5': [100 + i * 0.1 for i in range(100)],
        'ma20': [100 + i * 0.1 for i in range(100)],
        'cumulative_return': [1 + i * 0.001 for i in range(100)],
        'drawdown_pct': [-i * 0.05 for i in range(100)],
        'volatility_20d': [0.15 + i * 0.001 for i in range(100)],
    })

    plotter = StockPlotter()
    fig = plotter.plot_candlestick(df, "600519")
    print(f"K线图生成完成: {fig is not None}")
