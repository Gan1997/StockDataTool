# -*- coding: utf-8 -*-
"""
绘图模块 - 使用Plotly生成专业分析图表
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import PLOT_CONFIG, STOCK_CONFIG
from src.logger import get_logger
from src.strategy_backtest import StrategyBacktest

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
            # title=f'{stock_code} K线图',
            width=self.config['width'],
            height=self.config['height'] if show_volume else self.config['height'] * 0.7,
            template=self.config['template'],
            xaxis_rangeslider_visible=False,
            xaxis=dict(
                tickformat='%Y-%m',
                tickangle=-45,
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                tickfont=dict(size=6)
            ),
            xaxis2=dict(
                tickformat='%Y-%m',
                tickangle=-45,
                tickfont=dict(size=6)
            ),
            yaxis=dict(
                tickfont=dict(size=6),
                title=dict(font=dict(size=4))
            ),
            yaxis2=dict(
                tickfont=dict(size=6),
                title=dict(font=dict(size=4))
            ),
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

    def _resample_df(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """
        将日线数据重采样为周线或月线

        Args:
            df: 日线数据DataFrame
            period: 'W' 周线, 'M' 月线

        Returns:
            重采样后的DataFrame
        """
        if df.empty:
            return df

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        # 重采样规则
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }

        resampled = df.resample(period).agg(agg_dict).dropna()

        # 重新计算均线
        for col in ['ma5', 'ma10', 'ma20', 'ma30', 'ma60']:
            if col in df.columns:
                resampled[col] = df[col].resample(period).last()

        # 重新计算回撤和波动率
        if 'drawdown_pct' in df.columns:
            resampled['drawdown_pct'] = df['drawdown_pct'].resample(period).max()
        if 'volatility_20d' in df.columns:
            resampled['volatility_20d'] = df['volatility_20d'].resample(period).last()
        if 'volatility_60d' in df.columns:
            resampled['volatility_60d'] = df['volatility_60d'].resample(period).last()

        # 重新计算累计收益率
        if 'cumulative_return' in df.columns:
            resampled['cumulative_return'] = df['cumulative_return'].resample(period).last()

        resampled = resampled.reset_index()
        resampled['date'] = resampled['date'].astype(str)

        return resampled

    def plot_ma(
        self,
        df: pd.DataFrame,
        stock_code: str = "unknown",
        save_path: Path = None
    ) -> go.Figure:
        """
        绘制均线+K线+成交量图（专业金融风格）

        Args:
            df: DataFrame，需包含 date, open, high, low, close, volume, ma5, ma10, ma20, ma30, ma60
            stock_code: 股票代码
            save_path: 保存路径

        Returns:
            Plotly Figure对象
        """
        if df.empty:
            logger.warning("数据为空，跳过绘图")
            return None

        # 计算RSI和MACD指标
        df = df.copy()
        if 'close' in df.columns:
            # 计算RSI (14日)
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = (-delta).where(delta < 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # 计算MACD (12, 26, 9)
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = ema12 - ema26
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']

        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.40, 0.15, 0.20, 0.25],
            specs=[[{'secondary_y': False}], [{'secondary_y': False}], [{'secondary_y': False}], [{'secondary_y': False}]]
        )

        up_color = '#c62828'
        down_color = '#2e7d32'

        fig.add_trace(
            go.Candlestick(
                x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='K线',
                increasing=dict(
                    line=dict(color=up_color, width=1),
                    fillcolor=up_color
                ),
                decreasing=dict(
                    line=dict(color=down_color, width=1),
                    fillcolor=down_color
                ),
                showlegend=False
            ),
            row=1, col=1
        )

        ma_periods = [20, 60]
        ma_colors = ['#1565c0', '#6a1b9a']
        ma_widths = [1.5, 2.0]

        for i, period in enumerate(ma_periods):
            col = f'ma{period}'
            if col in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['date'],
                        y=df[col],
                        mode='lines',
                        name=f'MA{period}',
                        line=dict(color=ma_colors[i], width=ma_widths[i]),
                        showlegend=True
                    ),
                    row=1, col=1
                )

        if 'volume' in df.columns:
            colors_vol = [
                up_color if df['close'].iloc[i] >= df['open'].iloc[i]
                else down_color
                for i in range(len(df))
            ]

            fig.add_trace(
                go.Bar(
                    x=df['date'],
                    y=df['volume'],
                    name='成交量',
                    marker_color=colors_vol,
                    opacity=1.0,
                    showlegend=False
                ),
                row=2, col=1
            )

        # 添加RSI指标 (row 3)
        if 'rsi' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['rsi'],
                    mode='lines',
                    name='RSI(14)',
                    line=dict(color='#7b1fa2', width=1.5),
                    showlegend=True
                ),
                row=3, col=1
            )

        # 添加MACD指标 (row 4)
        if 'macd' in df.columns and 'macd_signal' in df.columns and 'macd_hist' in df.columns:
            # MACD线
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['macd'],
                    mode='lines',
                    name='MACD',
                    line=dict(color='#1976d2', width=1.5),
                    showlegend=True
                ),
                row=4, col=1
            )
            # Signal线
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['macd_signal'],
                    mode='lines',
                    name='Signal',
                    line=dict(color='#ff5722', width=1.5),
                    showlegend=True
                ),
                row=4, col=1
            )
            # MACD柱状图
            colors_hist = [
                '#c62828' if df['macd_hist'].iloc[i] >= 0 else '#2e7d32'
                for i in range(len(df))
            ]
            fig.add_trace(
                go.Bar(
                    x=df['date'],
                    y=df['macd_hist'],
                    name='Histogram',
                    marker_color=colors_hist,
                    opacity=0.7,
                    showlegend=False
                ),
                row=4, col=1
            )

        fig.update_layout(
            template='plotly_white',
            xaxis_rangeslider_visible=False,
            margin=dict(l=60, r=20, t=30, b=40),
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.05,
                xanchor='center',
                x=0.5,
                font=dict(size=10)
            ),
            dragmode='pan',
            hovermode='x unified'
        )

        fig.update_xaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            row=1, col=1
        )

        fig.update_xaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            row=2, col=1
        )

        fig.update_yaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            title_text='价格(元)',
            title_font=dict(size=10),
            row=1, col=1
        )

        fig.update_yaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            title_text='成交量',
            title_font=dict(size=10),
            row=2, col=1
        )

        # RSI的xaxis和yaxis (row 3)
        fig.update_xaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            row=3, col=1
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            title_text='RSI',
            title_font=dict(size=10),
            range=[0, 100],
            row=3, col=1
        )

        # MACD的xaxis和yaxis (row 4)
        fig.update_xaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            row=4, col=1
        )
        fig.update_yaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            title_text='MACD',
            title_font=dict(size=10),
            row=4, col=1
        )

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
                fillcolor='rgba(183, 28, 28, 0.2)',
                line=dict(color='#b71c1c', width=1.5)
            )
        )

        fig.update_layout(
            template='plotly_white',
            margin=dict(l=60, r=20, t=30, b=40),
            showlegend=False,
            dragmode='pan',
            hovermode='x unified'
        )

        fig.update_xaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True
        )

        fig.update_yaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            title_text='回撤 (%)',
            title_font=dict(size=10)
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

        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['cumulative_return'],
                mode='lines',
                name='净值曲线',
                line=dict(color='#1565c0', width=1.5)
            )
        )

        if benchmark_df is not None and 'cumulative_return' in benchmark_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=benchmark_df['date'],
                    y=benchmark_df['cumulative_return'],
                    mode='lines',
                    name='基准',
                    line=dict(color='#757575', width=1.5, dash='dash')
                )
            )

        fig.update_layout(
            template='plotly_white',
            margin=dict(l=60, r=20, t=30, b=40),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            dragmode='pan',
            hovermode='x unified'
        )

        fig.update_xaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True
        )

        fig.update_yaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            title_text='净值',
            title_font=dict(size=10)
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
                    line=dict(color='#d32f2f', width=1.5)
                )
            )

        if 'volatility_60d' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['date'],
                    y=df['volatility_60d'] * 100,
                    mode='lines',
                    name='60日波动率',
                    line=dict(color='#1565c0', width=1.5)
                )
            )

        fig.update_layout(
            template='plotly_white',
            margin=dict(l=60, r=20, t=30, b=40),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            dragmode='pan',
            hovermode='x unified'
        )

        fig.update_xaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True
        )

        fig.update_yaxes(
            showgrid=True,
            gridcolor='#eeeeee',
            gridwidth=0.5,
            ticks='outside',
            tickfont=dict(size=9),
            showline=True,
            linecolor='#bdbdbd',
            mirror=True,
            title_text='波动率 (%)',
            title_font=dict(size=10)
        )

        if save_path:
            fig.write_html(save_path)
            logger.info(f"波动率图已保存: {save_path}")

        return fig

    def save_integrated_html(
        self,
        df: pd.DataFrame,
        stock_code: str,
        output_dir: Path = None,
        include_benchmark: bool = False,
        benchmark_df: pd.DataFrame = None
    ) -> str:
        """
        将所有图表集成到一张HTML页面

        Args:
            df: DataFrame
            stock_code: 股票代码
            output_dir: 输出目录
            include_benchmark: 是否包含基准对比
            benchmark_df: 基准数据

        Returns:
            str - HTML文件路径
        """
        if output_dir is None:
            output_dir = Path(self.config['output_dir'])

        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成各个图表
        charts = {}

        # K线图
        fig_kline = self.plot_candlestick(df, stock_code)
        if fig_kline:
            charts['K线图'] = fig_kline

        # 回撤图
        fig_dd = self.plot_drawdown(df, stock_code)
        if fig_dd:
            charts['回撤图'] = fig_dd

        # 收益率图
        fig_ret = self.plot_returns(df, stock_code, benchmark_df if include_benchmark else None)
        if fig_ret:
            charts['收益率'] = fig_ret

        # 波动率图
        if 'volatility_20d' in df.columns or 'volatility_60d' in df.columns:
            fig_vol = self.plot_volatility(df, stock_code)
            if fig_vol:
                charts['波动率'] = fig_vol

        # 生成集成HTML
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            f'<title>{stock_code} 分析报告</title>',
            '<meta charset="utf-8">',
            '<style>',
            'body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }',
            '.chart-container { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
            'h1 { color: #333; text-align: center; }',
            'h2 { color: #666; border-bottom: 2px solid #1f77b4; padding-bottom: 10px; }',
            '.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }',
            '.stat-box { background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
            '.stat-label { color: #666; font-size: 14px; }',
            '.stat-value { color: #333; font-size: 20px; font-weight: bold; }',
            '</style>',
            '</head>',
            '<body>',
            f'<h1>{stock_code} 技术分析报告</h1>',
        ]

        # 添加统计信息
        html_parts.append('<div class="stats">')
        if 'close' in df.columns and len(df) > 0:
            start_price = df['close'].iloc[0]
            end_price = df['close'].iloc[-1]
            total_return = (end_price / start_price - 1) * 100
            html_parts.append(f'<div class="stat-box"><div class="stat-label">区间涨跌幅</div><div class="stat-value">{total_return:.2f}%</div></div>')

        if 'drawdown_pct' in df.columns:
            max_dd = df['drawdown_pct'].min()
            html_parts.append(f'<div class="stat-box"><div class="stat-label">最大回撤</div><div class="stat-value">{max_dd:.2f}%</div></div>')

        if 'volatility_20d' in df.columns:
            vol = df['volatility_20d'].iloc[-1] * 100
            html_parts.append(f'<div class="stat-box"><div class="stat-label">20日波动率</div><div class="stat-value">{vol:.2f}%</div></div>')

        html_parts.append('</div>')

        # 添加各个图表
        for title, fig in charts.items():
            html_parts.append(f'<div class="chart-container">')
            html_parts.append(f'<h2>{title}</h2>')
            html_parts.append(fig.to_html(full_html=False, include_plotlyjs='cdn'))
            html_parts.append('</div>')

        html_parts.extend([
            '</body>',
            '</html>'
        ])

        # 保存文件
        output_path = output_dir / f"{stock_code}_report.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        logger.info(f"集成报告已保存: {output_path}")
        return str(output_path)

    def _fig_to_json(self, fig):
        """将 plotly figure 转换为可 JSON 序列化的字典"""
        # 使用 plotly 自带的 to_json()，然后解析为字典
        return json.loads(fig.to_json())

    def save_batch_report(
        self,
        data_dict: Dict[str, pd.DataFrame],
        output_dir: Path = None,
        include_benchmark: bool = False,
        benchmark_dict: Dict[str, pd.DataFrame] = None
    ) -> str:
        """
        生成4宫格分析看板：K线+均线 | 回撤图
        展示筛选后的股票对比分析

        Args:
            data_dict: Dict[stock_code, DataFrame]
            output_dir: 输出目录
            include_benchmark: 是否包含基准对比
            benchmark_dict: 基准数据字典

        Returns:
            str - HTML文件路径
        """
        if output_dir is None:
            output_dir = Path(self.config['output_dir'])

        output_dir.mkdir(parents=True, exist_ok=True)

        if not data_dict:
            logger.warning("没有数据可展示")
            return None

        # 预计算每只股票的统计和图表
        stock_data = {}
        all_codes = list(data_dict.keys())

        for code, df in data_dict.items():
            if df.empty:
                continue

            # 日线数据
            fig_ma_d = self.plot_ma(df, code)
            fig_dd_d = self.plot_drawdown(df, code)
            fig_ret_d = self.plot_returns(df, code, None)
            fig_vol_d = self.plot_volatility(df, code) if 'volatility_20d' in df.columns else None

            # 周线数据
            df_w = self._resample_df(df, 'W')
            fig_ma_w = self.plot_ma(df_w, code) if len(df_w) > 0 else None
            fig_dd_w = self.plot_drawdown(df_w, code) if len(df_w) > 0 else None
            fig_ret_w = self.plot_returns(df_w, code, None) if len(df_w) > 0 else None
            fig_vol_w = self.plot_volatility(df_w, code) if len(df_w) > 0 and 'volatility_20d' in df_w.columns else None

            # 月线数据
            df_m = self._resample_df(df, 'M')
            fig_ma_m = self.plot_ma(df_m, code) if len(df_m) > 0 else None
            fig_dd_m = self.plot_drawdown(df_m, code) if len(df_m) > 0 else None
            fig_ret_m = self.plot_returns(df_m, code, None) if len(df_m) > 0 else None
            fig_vol_m = self.plot_volatility(df_m, code) if len(df_m) > 0 and 'volatility_20d' in df_m.columns else None

            # 提取原始数据用于前端动态计算
            raw_data_d = {
                'dates': df['date'].astype(str).tolist(),
                'close': df['close'].tolist(),
                'volume': df['volume'].tolist(),
                'ma20': df['ma20'].tolist() if 'ma20' in df.columns else [],
                'ma60': df['ma60'].tolist() if 'ma60' in df.columns else [],
                'drawdown_pct': df['drawdown_pct'].tolist() if 'drawdown_pct' in df.columns else [],
                'high': df['high'].tolist() if 'high' in df.columns else [],
            }

            raw_data_w = {
                'dates': df_w['date'].astype(str).tolist() if len(df_w) > 0 else [],
                'close': df_w['close'].tolist() if len(df_w) > 0 else [],
                'volume': df_w['volume'].tolist() if len(df_w) > 0 else [],
                'ma20': df_w['ma20'].tolist() if len(df_w) > 0 and 'ma20' in df_w.columns else [],
                'ma60': df_w['ma60'].tolist() if len(df_w) > 0 and 'ma60' in df_w.columns else [],
                'drawdown_pct': df_w['drawdown_pct'].tolist() if len(df_w) > 0 and 'drawdown_pct' in df_w.columns else [],
                'high': df_w['high'].tolist() if len(df_w) > 0 and 'high' in df_w.columns else [],
            }

            raw_data_m = {
                'dates': df_m['date'].astype(str).tolist() if len(df_m) > 0 else [],
                'close': df_m['close'].tolist() if len(df_m) > 0 else [],
                'volume': df_m['volume'].tolist() if len(df_m) > 0 else [],
                'ma20': df_m['ma20'].tolist() if len(df_m) > 0 and 'ma20' in df_m.columns else [],
                'ma60': df_m['ma60'].tolist() if len(df_m) > 0 and 'ma60' in df_m.columns else [],
                'drawdown_pct': df_m['drawdown_pct'].tolist() if len(df_m) > 0 and 'drawdown_pct' in df_m.columns else [],
                'high': df_m['high'].tolist() if len(df_m) > 0 and 'high' in df_m.columns else [],
            }

            # 策略回测评估
            sb = StrategyBacktest()
            strategy_eval = sb.evaluate_strategies(df)
            strategy_chart = None
            if strategy_eval:
                # 计算买入持有基准净值
                if 'close' in df.columns and len(df) > 0:
                    benchmark = (df['close'] / df['close'].iloc[0]).tolist()
                else:
                    benchmark = None
                strategy_chart = sb.plot_strategy_equity(strategy_eval, code, benchmark)

                # 计算每个策略的换手率 = 买入次数 / 交易日数 * 100%
                trading_days = len(df) if len(df) > 0 else 1
                for strategy_list in ['momentum', 'reversal', 'turtle']:
                    if strategy_list in strategy_eval:
                        for item in strategy_eval[strategy_list]:
                            stats = item['data']['stats']
                            buy_count = stats.get('buy_count', stats.get('trades', 0))
                            stats['turnover_rate'] = round(buy_count / trading_days * 100, 2)

            stock_data[code] = {
                'ma_d': self._fig_to_json(fig_ma_d) if fig_ma_d else None,
                'ma_w': self._fig_to_json(fig_ma_w) if fig_ma_w else None,
                'ma_m': self._fig_to_json(fig_ma_m) if fig_ma_m else None,
                'drawdown_d': self._fig_to_json(fig_dd_d) if fig_dd_d else None,
                'drawdown_w': self._fig_to_json(fig_dd_w) if fig_dd_w else None,
                'drawdown_m': self._fig_to_json(fig_dd_m) if fig_dd_m else None,
                'returns_d': self._fig_to_json(fig_ret_d) if fig_ret_d else None,
                'returns_w': self._fig_to_json(fig_ret_w) if fig_ret_w else None,
                'returns_m': self._fig_to_json(fig_ret_m) if fig_ret_m else None,
                'volatility_d': self._fig_to_json(fig_vol_d) if fig_vol_d else None,
                'volatility_w': self._fig_to_json(fig_vol_w) if fig_vol_w else None,
                'volatility_m': self._fig_to_json(fig_vol_m) if fig_vol_m else None,
                'raw_d': raw_data_d,
                'raw_w': raw_data_w,
                'raw_m': raw_data_m,
                'days': len(df),
                'name': STOCK_CONFIG['stock_list'].get(code, code),
                'strategy': strategy_eval,
                'strategy_chart': self._fig_to_json(strategy_chart) if strategy_chart else None,
            }

        # 生成HTML - 预先渲染所有图表，通过CSS控制显示/隐藏
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<title>股票分析看板</title>',
            '<meta charset="utf-8">',
            '<style>',
            '* { margin: 0; padding: 0; box-sizing: border-box; }',
            'body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; background: #f5f7fa; min-height: 100vh; color: #333; }',
            '.header { background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%); padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; gap: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }',
            '.header h1 { font-size: 1rem; color: white; font-weight: 600; }',
            '.header-controls { display: flex; gap: 8px; align-items: center; }',
            '.date-input { padding: 5px 8px; border: 1px solid #ddd; border-radius: 4px; background: white; font-size: 12px; color: #333; }',
            '.btn { padding: 5px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 500; }',
            '.btn-primary { background: #2c5282; color: white; }',
            '.btn-primary:hover { background: #1e3a5f; }',
            '.btn-secondary { background: #e2e8f0; color: #4a5568; }',
            '.btn-secondary:hover { background: #cbd5e0; }',
            '.view-toggle { display: flex; background: #e2e8f0; border-radius: 6px; padding: 2px; }',
            '.view-btn { border: none; background: transparent; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 12px; color: #64748b; font-weight: 500; transition: all 0.2s; }',
            '.view-btn:hover { background: rgba(255,255,255,0.5); color: #2c5282; }',
            '.view-btn.active { background: white; color: #2c5282; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }',
            '.toolbar { display: flex; justify-content: space-between; align-items: center; padding: 8px 20px; background: white; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; gap: 10px; }',
            '.toolbar-left { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }',
            '.toolbar-right { display: flex; gap: 10px; align-items: center; }',
            '.filter-group { display: flex; gap: 5px; align-items: center; }',
            '.filter-label { font-size: 11px; color: #64748b; font-weight: 500; }',
            '.filter-input { padding: 4px 8px; border: 1px solid #cbd5e0; border-radius: 4px; background: white; color: #333; font-size: 12px; width: 55px; }',
            '.stat-card { background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); padding: 6px 12px; border-radius: 6px; display: flex; flex-direction: column; align-items: center; border: 1px solid #e2e8f0; }',
            '.stat-card .label { font-size: 10px; color: #64748b; font-weight: 500; }',
            '.stat-card .value { font-size: 0.95rem; font-weight: 700; color: #1e3a5f; }',
            '.stat-card .value.positive { color: #c53030; }',
            '.stat-card .value.negative { color: #276749; }',
            '.quick-selector { display: flex; gap: 5px; padding: 6px 20px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; align-items: center; }',
            '.quick-btn { background: #e2e8f0; color: #4a5568; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; border: 1px solid #cbd5e0; font-weight: 500; }',
            '.quick-btn:hover, .quick-btn.active { background: #2c5282; color: white; border-color: #2c5282; }',
            '.period-selector { display: flex; gap: 2px; }',
            '.period-btn { padding: 5px 10px; border: 1px solid #e2e8f0; border-radius: 4px; cursor: pointer; font-size: 12px; background: white; color: #64748b; }',
            '.period-btn:hover { background: #f1f5f9; }',
            '.period-btn.active { background: #2c5282; color: white; border-color: #2c5282; }',
            '.charts-container { display: flex; gap: 16px; padding: 16px 24px; height: calc(100vh - 130px); min-height: 700px; align-items: stretch; }',
            '.left-panel { flex: 0 0 65%; display: flex; flex-direction: column; }',
            '.left-panel .grid-cell { flex: 1; min-height: 0; }',
            '.right-panel { flex: 1; display: flex; flex-direction: column; gap: 12px; }',
            '.right-panel .grid-cell { flex: 1; min-height: 0; }',
            '.grid-cell { background: white; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; min-height: 180px; min-width: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; cursor: pointer; transition: box-shadow 0.2s; }',
            '.grid-cell:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.15); }',
            '.expand-hint { font-size: 10px; color: #94a3b8; opacity: 0; transition: opacity 0.2s; }',
            '.grid-cell:hover .expand-hint { opacity: 1; }',
            '.cell-header { padding: 8px 14px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; flex-shrink: 0; background: #f8fafc; height: 40px; }',
            '.cell-title { font-weight: 600; font-size: 12px; color: #1e3a5f; }',
            '.cell-subtitle { font-size: 10px; color: #64748b; }',
            '.cell-body { flex: 1; min-height: 0; min-width: 0; position: relative; }',
            '.cell-body > div { width: 100% !important; height: 100% !important; }',
            '.quick-btn { background: rgba(102, 126, 234, 0.2); color: #667eea; padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; border: none; }',
            '.quick-btn:hover { background: #667eea; color: white; }',
            '.rank-table { width: 100%; border-collapse: collapse; }',
            '.rank-table th, .rank-table td { padding: 10px 15px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }',
            '.rank-table th { background: rgba(255,255,255,0.05); color: #888; font-weight: 500; font-size: 13px; }',
            '.rank-table tr:hover { background: rgba(255,255,255,0.03); }',
            '.rank-table .rank { width: 40px; text-align: center; }',
            '.rank-table .code { font-weight: 600; color: #667eea; }',
            '.rank-table .positive { color: #EF5350; }',
            '.rank-table .negative { color: #26A69A; }',
            '.all-charts { display: none; }',
            '.chart-modal { display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: #ffffff; z-index: 10000; }',
            '.chart-modal.active { display: flex; flex-direction: column; }',
            '.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 24px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }',
            '.modal-title { color: #1e3a5f; font-size: 16px; font-weight: 600; }',
            '.modal-close { background: rgba(239, 68, 68, 0.1); border: none; color: #ef4444; width: 36px; height: 36px; border-radius: 50%; font-size: 20px; cursor: pointer; }',
            '.modal-close:hover { background: rgba(239, 68, 68, 0.2); }',
            '.modal-body { flex: 1; padding: 0; overflow: hidden; }',
            '.modal-chart { width: 100%; height: 100%; }',
            '.modal-chart .js-plotly-plot, .modal-chart > div { width: 100% !important; height: 100% !important; }',
            '.strategy-badge { display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }',
            '.strategy-badge.momentum { background: #e3f2fd; color: #1565c0; }',
            '.strategy-badge.reversal { background: #ffebee; color: #c62828; }',
            '.strategy-badge.turtle { background: #e8f5e9; color: #2e7d32; }',
            '.strategy-badge.neutral { background: #f5f5f5; color: #757575; }',
            '.strategy-section { display: none; padding: 16px 24px; background: #f5f7fa; }',
            '.strategy-section.active { display: block; }',
            '.strategy-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }',
            '.strategy-card { background: white; border-radius: 8px; padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }',
            '.strategy-card h4 { font-size: 12px; color: #1e3a5f; margin-bottom: 8px; font-weight: 600; }',
            '.strategy-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }',
            '.strategy-stat { display: flex; justify-content: space-between; font-size: 11px; padding: 3px 0; border-bottom: 1px dotted #e2e8f0; }',
            '.strategy-stat .label { color: #64748b; }',
            '.strategy-stat .value { font-weight: 600; color: #1e3a5f; }',
            '.strategy-stat .value.positive { color: #c62828; }',
            '.strategy-stat .value.negative { color: #2e7d32; }',
            '.strategy-chart-container { height: 320px; margin-top: 12px; background: white; border-radius: 8px; border: 1px solid #e2e8f0; }',
            '.strategy-selector { display: flex; gap: 16px; padding: 10px 12px; background: white; border-radius: 6px; border: 1px solid #e2e8f0; margin-bottom: 8px; flex-wrap: wrap; }',
            '.selector-group { display: flex; align-items: center; gap: 8px; }',
            '.selector-label { font-size: 11px; color: #1e3a5f; font-weight: 600; }',
            '.strategy-checkbox { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #64748b; cursor: pointer; }',
            '.strategy-checkbox input[type="checkbox"] { width: 14px; height: 14px; cursor: pointer; accent-color: #2c5282; }',
            '.strategy-checkbox:hover { color: #2c5282; }',
            '.tab-bar { display: flex; gap: 2px; padding: 0 24px; background: white; border-bottom: 1px solid #e2e8f0; }',
            '.tab-btn { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 12px; color: #64748b; font-weight: 500; border-bottom: 2px solid transparent; }',
            '.tab-btn:hover { color: #2c5282; }',
            '.tab-btn.active { color: #2c5282; border-bottom-color: #2c5282; }',
            '.view-container { position: relative; }',
            '.ranking-section { display: none; padding: 15px 25px; }',
            '.ranking-section.active { display: block; }',
            '</style>',
            '</head>',
            '<body>',
        ]

        # 生成HTML内容
        stock_json = json.dumps(stock_data, ensure_ascii=False)

        # 构建选项HTML
        options_html = ''.join(f'<option value="{c}">{stock_data[c]["name"]} ({c})</option>' for c in all_codes)
        # 构建快速切换按钮HTML（显示股票名称）
        buttons_html = ''.join(f'<span class="quick-btn active" data-code="{c}" onclick="quickSwitch(\'{c}\')">{stock_data[c]["name"]}</span>' for c in all_codes[:8])

        # 获取时间范围（默认最近6个月）
        first_df = data_dict.get(all_codes[0])
        if first_df is not None and len(first_df) > 0:
            max_idx = first_df.index.max()
            if hasattr(max_idx, 'strftime'):
                end_date = max_idx.strftime('%Y-%m-%d')
                start_date = (max_idx - pd.DateOffset(months=6)).strftime('%Y-%m-%d')
            else:
                end_date = pd.Timestamp(max_idx).strftime('%Y-%m-%d')
                start_date = (pd.Timestamp(max_idx) - pd.DateOffset(months=6)).strftime('%Y-%m-%d')
        else:
            end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
            start_date = (pd.Timestamp.now() - pd.DateOffset(months=6)).strftime('%Y-%m-%d')

        html_parts.append(f'''
        <div class="header">
            <h1>📈 股票分析看板</h1>
            <div class="header-controls">
                <input type="date" class="date-input" id="startDate" value="{start_date}" onchange="filterByDate()">
                <input type="date" class="date-input" id="endDate" value="{end_date}" onchange="filterByDate()">
                <div class="view-toggle">
                    <button class="view-btn active" id="btnCharts" onclick="showCharts()">📊图表</button>
                    <button class="view-btn" id="btnRanking" onclick="showRanking()">📋榜单</button>
                </div>
                <div class="period-selector">
                    <button class="period-btn active" onclick="switchPeriod('d')">日线</button>
                    <button class="period-btn" onclick="switchPeriod('w')">周线</button>
                    <button class="period-btn" onclick="switchPeriod('m')">月线</button>
                </div>
            </div>
        </div>

        <div class="toolbar">
            <div class="toolbar-left">
                <div class="stat-card">
                    <div class="label">股票</div>
                    <div class="value" id="statCode">{all_codes[0] if all_codes else '-'}</div>
                </div>
                <div class="stat-card">
                    <div class="label">涨跌</div>
                    <div class="value positive" id="statReturn">-</div>
                </div>
                <div class="stat-card">
                    <div class="label">回撤</div>
                    <div class="value negative" id="statDrawdown">-</div>
                </div>
                <div class="stat-card">
                    <div class="label">量比</div>
                    <div class="value" id="statVolume">-</div>
                </div>
                <div class="stat-card">
                    <div class="label">策略适配</div>
                    <div class="value" id="statStrategy">-</div>
                </div>
            </div>
            <div class="toolbar-right">
                <div class="filter-group">
                    <span class="filter-label">收益></span>
                    <input type="number" class="filter-input" id="filterReturn" value="0" step="1">
                    <span class="filter-label">%</span>
                </div>
                <div class="filter-group">
                    <span class="filter-label">回撤<</span>
                    <input type="number" class="filter-input" id="filterDrawdown" value="20" step="1">
                    <span class="filter-label">%</span>
                </div>
                <div class="filter-group">
                    <input type="checkbox" id="filterMA">
                    <span class="filter-label">均线多头</span>
                </div>
                <div class="filter-group">
                    <input type="checkbox" id="filterVolume">
                    <span class="filter-label">放量突破</span>
                </div>
                <button class="btn btn-primary" onclick="applyFilter()">筛选</button>
                <button class="btn btn-secondary" onclick="resetFilter()">重置</button>
                <span id="filterCount" style="color:#888;font-size:10px;"></span>
            </div>
        </div>

        <div class="quick-selector" id="quickSelector">
            {buttons_html}
        </div>

        <!-- Tab切换栏 -->
        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab('technical')">技术分析</button>
            <button class="tab-btn" onclick="switchTab('strategy')">策略回测</button>
        </div>

        <!-- 视图容器：技术分析、策略回测、榜单共享同一空间 -->
        <div class="view-container">
            <!-- 左一右三图表视图 -->
            <div class="charts-container" id="chartsView">
                <!-- 左侧大图：均线 -->
                <div class="left-panel">
                    <div class="grid-cell" onclick="expandChart('chart1')">
                        <div class="cell-header">
                            <span class="cell-title">K线+均线+成交量</span>
                            <span class="expand-hint">↗ 点击展开</span>
                        </div>
                        <div class="cell-body" id="chart1"></div>
                    </div>
                </div>
                <!-- 右侧三个小图 -->
                <div class="right-panel">
                    <div class="grid-cell" onclick="expandChart('chart2')">
                        <div class="cell-header">
                            <span class="cell-title">净值</span>
                            <span class="expand-hint">↗ 点击展开</span>
                        </div>
                        <div class="cell-body" id="chart2"></div>
                    </div>
                    <div class="grid-cell" onclick="expandChart('chart3')">
                        <div class="cell-header">
                            <span class="cell-title">回撤分析</span>
                            <span class="expand-hint">↗ 点击展开</span>
                        </div>
                        <div class="cell-body" id="chart3"></div>
                    </div>
                    <div class="grid-cell" onclick="expandChart('chart4')">
                        <div class="cell-header">
                            <span class="cell-title">波动率</span>
                            <span class="expand-hint">↗ 点击展开</span>
                        </div>
                        <div class="cell-body" id="chart4"></div>
                    </div>
                </div>
            </div>

            <!-- 策略回测视图 -->
            <div id="strategyView" class="strategy-section">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div>
                    <span class="strategy-badge" id="strategyBadge">-</span>
                    <span style="font-size: 12px; color: #64748b; margin-left: 8px;">最佳策略: <b id="bestStrategy">-</b></span>
                </div>
            </div>
            <!-- 策略选择器 -->
            <div class="strategy-selector" id="strategySelector">
                <div class="selector-group">
                    <span class="selector-label">动量:</span>
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_momentum_1" checked onchange="updateStrategyChart()">231-21</label>
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_momentum_2" onchange="updateStrategyChart()">189-63</label>
                </div>
                <div class="selector-group">
                    <span class="selector-label">反转:</span>
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_reversal_1" checked onchange="updateStrategyChart()">3日</label>
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_reversal_2" onchange="updateStrategyChart()">5日</label>
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_reversal_3" onchange="updateStrategyChart()">10日</label>
                </div>
                <div class="selector-group">
                    <span class="selector-label">海龟:</span>
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_turtle_1" checked onchange="updateStrategyChart()">20-10</label>
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_turtle_2" onchange="updateStrategyChart()">55-20</label>
                </div>
                <div class="selector-group">
                    <label class="strategy-checkbox"><input type="checkbox" id="chk_benchmark" checked onchange="updateStrategyChart()">买入持有</label>
                </div>
            </div>
            <div class="strategy-chart-container" id="strategyChart"></div>
            <div class="strategy-grid" id="strategyGrid" style="margin-top: 12px;"></div>
            </div>

            <!-- 榜单视图 -->
            <div id="rankingView" class="ranking-section">
                <table class="rank-table">
                <thead>
                    <tr>
                        <th class="rank">#</th>
                        <th>股票代码</th>
                        <th>股票名称</th>
                        <th>区间收益</th>
                        <th>年化收益</th>
                        <th>最大回撤</th>
                        <th>量比</th>
                        <th>策略适配</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="rankBody">
                </tbody>
            </table>
            </div>
        </div>

        <!-- 图表全屏模态框 -->
        <div class="chart-modal" id="chartModal">
            <div class="modal-header">
                <span class="modal-title" id="modalTitle">图表详情</span>
                <button class="modal-close" onclick="closeModal()">×</button>
            </div>
            <div class="modal-body">
                <div class="modal-chart" id="modalChart"></div>
            </div>
        </div>

        <!-- 隐藏的图表容器 -->
        <div class="all-charts" id="allChartsContainer">
''')

        # 预先渲染所有图表
        for code in all_codes:
            data = stock_data.get(code, {})
            ma_json = json.dumps(data.get("ma")) if data.get("ma") else ""
            drawdown_json = json.dumps(data.get("drawdown")) if data.get("drawdown") else ""
            returns_json = json.dumps(data.get("returns")) if data.get("returns") else ""
            volatility_json = json.dumps(data.get("volatility")) if data.get("volatility") else ""
            # 转义 </script> 防止HTML解析器提前结束脚本
            ma_json = ma_json.replace('</script', '<\\/script')
            drawdown_json = drawdown_json.replace('</script', '<\\/script')
            returns_json = returns_json.replace('</script', '<\\/script')
            volatility_json = volatility_json.replace('</script', '<\\/script')
            html_parts.append(f'<div class="chart-wrapper hidden" data-stock="{code}" data-type="ma">{ma_json}</div>')
            html_parts.append(f'<div class="chart-wrapper hidden" data-stock="{code}" data-type="drawdown">{drawdown_json}</div>')
            html_parts.append(f'<div class="chart-wrapper hidden" data-stock="{code}" data-type="returns">{returns_json}</div>')
            html_parts.append(f'<div class="chart-wrapper hidden" data-stock="{code}" data-type="volatility">{volatility_json}</div>')

        html_parts.append('</div>')

        # JavaScript
        first_code = all_codes[0] if all_codes else ""
        js_template = '''
        <script src="https://cdn.plot.ly/plotly-2.29.1.min.js"></script>
        <script>
        let stockData = {};
        let allCodes = [];
        let currentStock = null;
        let currentView = 'charts';
        let filteredCodes = [];
        let dataLoaded = false;
        let currentPeriod = 'd';

        function switchPeriod(period) {
            currentPeriod = period;
            document.querySelectorAll('.period-btn').forEach(btn => {
                btn.classList.toggle('active', btn.textContent === (period === 'd' ? '日线' : period === 'w' ? '周线' : '月线'));
            });
            updateDisplay();
        }

        function showLoading(msg) {
            let loadingDiv = document.getElementById('loading-indicator');
            if (!loadingDiv) {
                loadingDiv = document.createElement('div');
                loadingDiv.id = 'loading-indicator';
                loadingDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);padding:30px 50px;background:rgba(0,0,0,0.8);color:white;border-radius:8px;font-size:16px;z-index:9999;';
                document.body.appendChild(loadingDiv);
            }
            loadingDiv.textContent = msg;
        }
        function hideLoading() {
            const loadingDiv = document.getElementById('loading-indicator');
            if (loadingDiv) loadingDiv.remove();
        }

        function loadStockData() {
            showLoading('正在加载数据...');
            console.log('Starting to load stock_data.json...');

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000);

            return fetch('stock_data.json', { cache: 'no-cache', signal: controller.signal })
                .then(response => {
                    clearTimeout(timeoutId);
                    console.log('Response status:', response.status, response.statusText);
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('JSON parsed successfully, keys:', Object.keys(data));
                    stockData = data;
                    allCodes = Object.keys(stockData);
                    filteredCodes = allCodes;
                    if (allCodes.length > 0) {
                        currentStock = allCodes[0];
                    }
                    dataLoaded = true;
                    console.log('Data loaded, currentStock:', currentStock);
                    hideLoading();
                    initDisplay();
                })
                .catch(error => {
                    clearTimeout(timeoutId);
                    console.error('Error loading stock data:', error);
                    hideLoading();
                    const errorDiv = document.createElement('div');
                    errorDiv.style.cssText = 'padding:50px;text-align:center;font-size:20px;color:red;';
                    errorDiv.innerHTML = '数据加载失败: ' + error.message + '<br>请刷新页面重试<br><small>如果问题持续，请检查网络连接</small>';
                    document.body.appendChild(errorDiv);
                });
        }

        function initDisplay() {
            updateDisplay();
            setupDateInputs();
        }

        function subtractMonths(dateStr, months) {
            const date = new Date(dateStr);
            const year = date.getFullYear();
            const month = date.getMonth();
            const day = date.getDate();
            let newYear = year;
            let newMonth = month - months;
            while (newMonth < 0) {
                newYear -= 1;
                newMonth += 12;
            }
            const lastDayOfNewMonth = new Date(newYear, newMonth + 1, 0).getDate();
            const newDay = Math.min(day, lastDayOfNewMonth);
            return new Date(newYear, newMonth, newDay).toISOString().split('T')[0];
        }

        function setupDateInputs() {
            const data = stockData[currentStock];
            const periodKey = currentPeriod === 'd' ? '_d' : currentPeriod === 'w' ? '_w' : '_m';
            const rawData = data['raw' + periodKey];
            if (!rawData || !rawData.dates || rawData.dates.length === 0) return;

            const dates = rawData.dates;
            const startDateInput = document.getElementById('startDate');
            const endDateInput = document.getElementById('endDate');

            if (dates.length > 0) {
                const latestDate = dates[dates.length - 1];
                const sixMonthsAgoStr = subtractMonths(latestDate, 6);

                startDateInput.value = sixMonthsAgoStr;
                endDateInput.value = latestDate;
                startDateInput.max = latestDate;
                endDateInput.min = dates[0];
                endDateInput.max = latestDate;
            }
        }

        function getFilteredIndices(code) {
            const data = stockData[code];
            const periodKey = currentPeriod === 'd' ? '_d' : currentPeriod === 'w' ? '_w' : '_m';
            const rawData = data['raw' + periodKey];
            if (!rawData) return {indices: [], startIdx: 0, endIdx: 0};

            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const dates = rawData.dates;
            
            let startIdx = 0;
            let endIdx = dates.length - 1;
            
            for (let i = 0; i < dates.length; i++) {
                if (dates[i] >= startDate) {
                    startIdx = i;
                    break;
                }
            }
            for (let i = dates.length - 1; i >= 0; i--) {
                if (dates[i] <= endDate) {
                    endIdx = i;
                    break;
                }
            }
            
            return {startIdx, endIdx, indices: Array.from({length: endIdx - startIdx + 1}, (_, i) => startIdx + i)};
        }

        function calculateStats(code) {
            const data = stockData[code];
            const periodKey = currentPeriod === 'd' ? '_d' : currentPeriod === 'w' ? '_w' : '_m';
            const rawData = data['raw' + periodKey];
            if (!rawData) return {return: 0, max_drawdown: 0, volume_ratio: 0, ma_golden_cross: false, volume_breakout: false};

            const {startIdx, endIdx} = getFilteredIndices(code);
            const close = rawData.close;
            const volume = rawData.volume;
            const ma20 = rawData.ma20;
            const ma60 = rawData.ma60;
            const drawdown_pct = rawData.drawdown_pct;
            const high = rawData.high;

            if (endIdx < startIdx || startIdx >= close.length || endIdx >= close.length) {
                return {return: 0, max_drawdown: 0, volume_ratio: 0, ma_golden_cross: false, volume_breakout: false};
            }

            const startPrice = close[startIdx];
            const endPrice = close[endIdx];
            const total_return = startPrice > 0 ? ((endPrice / startPrice - 1) * 100) : 0;

            let max_dd = 0;
            for (let i = startIdx; i <= endIdx; i++) {
                if (drawdown_pct[i] !== undefined && drawdown_pct[i] < max_dd) {
                    max_dd = drawdown_pct[i];
                }
            }

            let volume_ratio = 0;
            const volEndIdx = Math.max(startIdx, endIdx - 20);
            if (volEndIdx <= endIdx) {
                let sumVol = 0;
                let count = 0;
                for (let i = volEndIdx; i < endIdx; i++) {
                    if (volume[i] !== undefined) {
                        sumVol += volume[i];
                        count++;
                    }
                }
                const avgVol = count > 0 ? sumVol / count : 0;
                if (avgVol > 0 && volume[endIdx] !== undefined) {
                    volume_ratio = volume[endIdx] / avgVol;
                }
            }

            const ma_golden_cross = ma20 && ma60 && ma20[endIdx] !== undefined && ma60[endIdx] !== undefined &&
                                    ma20[endIdx] > ma60[endIdx];
            
            let volume_breakout = false;
            if (volEndIdx <= endIdx && high.length > endIdx && volume[endIdx] !== undefined && close[endIdx] !== undefined) {
                let maxHigh = -Infinity;
                for (let i = volEndIdx; i < endIdx; i++) {
                    if (high[i] !== undefined && high[i] > maxHigh) {
                        maxHigh = high[i];
                    }
                }
                let sumVol20 = 0;
                let count20 = 0;
                for (let i = volEndIdx; i < endIdx; i++) {
                    if (volume[i] !== undefined) {
                        sumVol20 += volume[i];
                        count20++;
                    }
                }
                const avgVol20 = count20 > 0 ? sumVol20 / count20 : 0;
                const volRatio20 = avgVol20 > 0 ? volume[endIdx] / avgVol20 : 0;
                volume_breakout = volRatio20 > 1.5 && close[endIdx] > maxHigh;
            }
            
            return {return: total_return, max_drawdown: max_dd, volume_ratio: volume_ratio, ma_golden_cross, volume_breakout};
        }

        function quickSwitch(code) {
            currentStock = code;
            // 通过data-code属性匹配，而不是文本内容
            document.querySelectorAll('.quick-btn[data-code]').forEach(btn => {
                btn.classList.toggle('active', btn.getAttribute('data-code') === code);
            });
            updateDisplay();
        }

        function filterByDate() {
            updateDisplay();
        }

        function applyFilter() {
            filteredCodes = allCodes;
            
            const minReturn = parseFloat(document.getElementById('filterReturn').value) || 0;
            const maxDrawdown = parseFloat(document.getElementById('filterDrawdown').value) || 100;
            const checkMA = document.getElementById('filterMA').checked;
            const checkVolume = document.getElementById('filterVolume').checked;

            filteredCodes = filteredCodes.filter(code => {
                const stats = calculateStats(code);
                if (stats.return < minReturn) return false;
                if (stats.max_drawdown > maxDrawdown) return false;
                if (checkMA && !stats.ma_golden_cross) return false;
                if (checkVolume && !stats.volume_breakout) return false;
                return true;
            });

            document.getElementById('filterCount').textContent = '筛选: ' + filteredCodes.length + '/' + allCodes.length;

            const selector = document.getElementById('quickSelector');
            if (filteredCodes.length === 0) {
                selector.innerHTML = '<span style="color:#888;font-size:10px;">无符合条件</span>';
            } else {
                selector.innerHTML = filteredCodes.slice(0, 8).map(c =>
                    '<span class="quick-btn' + (c === currentStock ? ' active' : '') + '" data-code="' + c + '" onclick="quickSwitch(\\'' + c + '\\')">' + (stockData[c] && stockData[c].name ? stockData[c].name : c) + '</span>'
                ).join('');
            }

            if (filteredCodes.length > 0 && !filteredCodes.includes(currentStock)) {
                quickSwitch(filteredCodes[0]);
            } else if (filteredCodes.length === 0) {
                updateDisplay();
            }
            renderRanking();
        }

        function resetFilter() {
            document.getElementById('filterReturn').value = '0';
            document.getElementById('filterDrawdown').value = '20';
            document.getElementById('filterMA').checked = false;
            document.getElementById('filterVolume').checked = false;
            filteredCodes = allCodes;
            document.getElementById('filterCount').textContent = '';

            const selector = document.getElementById('quickSelector');
            selector.innerHTML = filteredCodes.map(c => 
                '<span class="quick-btn' + (c === currentStock ? ' active' : '') + '" data-code="' + c + '" onclick="quickSwitch(\\'' + c + '\\')">' + (stockData[c] && stockData[c].name ? stockData[c].name : c) + '</span>'
            ).join('');

            if (!allCodes.includes(currentStock)) {
                quickSwitch(allCodes[0]);
            } else {
                updateDisplay();
            }
            renderRanking();
        }

        function updateDisplay() {
            const data = stockData[currentStock];
            console.log('updateDisplay called, currentStock:', currentStock, 'data:', data);
            if (!data) {
                console.log('No data for currentStock');
                return;
            }

            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const stats = calculateStats(currentStock);

            document.getElementById('statCode').textContent = currentStock;
            const returnSign = stats.return >= 0 ? '+' : '';
            const returnEl = document.getElementById('statReturn');
            returnEl.textContent = returnSign + stats.return.toFixed(2) + '%';
            returnEl.className = 'value ' + (stats.return >= 0 ? 'positive' : 'negative');
            document.getElementById('statDrawdown').textContent = stats.max_drawdown.toFixed(2) + '%';
            document.getElementById('statVolume').textContent = stats.volume_ratio.toFixed(2);

            // 更新策略适配度
            if (data.strategy) {
                const adaptType = data.strategy.adapt_type;
                const badge = document.getElementById('strategyBadge');
                badge.textContent = adaptType;
                const badgeClass = adaptType === '动量策略' ? 'momentum' : 
                                   adaptType === '反转策略' ? 'reversal' : 
                                   adaptType === '海龟策略' ? 'turtle' : 'neutral';
                badge.className = 'strategy-badge ' + badgeClass;
                document.getElementById('bestStrategy').textContent = data.strategy.best_strategy;
                document.getElementById('statStrategy').textContent = adaptType.replace('策略', '');
            }

            // 使用 requestAnimationFrame 确保容器尺寸正确
            requestAnimationFrame(() => {
                renderCharts(data, startDate, endDate);
                renderStrategyData(data);
            });
        }

        function renderCharts(data, startDate, endDate) {
            try {
                const periodKey = currentPeriod === 'd' ? '_d' : currentPeriod === 'w' ? '_w' : '_m';
                const chartIds = ['chart1', 'chart2', 'chart3', 'chart4'];
                
                chartIds.forEach(id => {
                    const keyMap = {'chart1': 'ma', 'chart2': 'returns', 'chart3': 'drawdown', 'chart4': 'volatility'};
                    const key = keyMap[id] + periodKey;
                    const container = document.getElementById(id);
                    if (data[key]) {
                        const fig = data[key];

                        const containerRect = container.getBoundingClientRect();
                        let containerWidth = containerRect.width;
                        let containerHeight = containerRect.height;

                        if (containerWidth === 0) containerWidth = id === 'chart1' ? 700 : 400;
                        if (containerHeight === 0) containerHeight = id === 'chart1' ? 500 : 200;

                        const layout = {
                            ...fig.layout,
                            autosize: false,
                            width: containerWidth,
                            height: containerHeight,
                            margin: {l: 50, r: 20, t: 20, b: 40}
                        };
                        if (layout.xaxis) {
                            layout.xaxis.range = [startDate, endDate];
                        }
                        container.innerHTML = '<div id="' + id + '-plot"></div>';
                        Plotly.newPlot(id + '-plot', fig.data, layout, {responsive: false, displayModeBar: false});
                    } else {
                        container.innerHTML = '<div style="padding:20px;color:#888;text-align:center;">暂无数据</div>';
                    }
                });

                setTimeout(() => {
                    chartIds.forEach(sourceId => {
                        const sourcePlot = document.getElementById(sourceId + '-plot');
                        if (!sourcePlot || !sourcePlot.data) return;

                        sourcePlot.on('hover', function(data) {
                            const pointIndex = data.points && data.points.length > 0 ? data.points[0].pointIndex : null;
                            if (pointIndex === null) {
                                chartIds.forEach(targetId => {
                                    const targetPlot = document.getElementById(targetId + '-plot');
                                    if (targetPlot && targetPlot !== sourcePlot) {
                                        Plotly.hover(targetPlot, {points: []});
                                    }
                                });
                                return;
                            }

                            chartIds.forEach(targetId => {
                                const targetPlot = document.getElementById(targetId + '-plot');
                                if (targetPlot && targetPlot !== sourcePlot) {
                                    Plotly.hover(targetPlot, {points: [[0, pointIndex]]});
                                }
                            });
                        });

                        sourcePlot.on('relayout', function(eventData) {
                            if (eventData['xaxis.range[0]'] !== undefined && eventData['xaxis.range[1]'] !== undefined) {
                                const newRange = [eventData['xaxis.range[0]'], eventData['xaxis.range[1]']];
                                chartIds.forEach(targetId => {
                                    const targetPlot = document.getElementById(targetId + '-plot');
                                    if (targetPlot && targetPlot !== sourcePlot) {
                                        Plotly.relayout(targetPlot, {
                                            'xaxis.range[0]': newRange[0],
                                            'xaxis.range[1]': newRange[1]
                                        });
                                    }
                                });
                            }
                        });
                    });
                }, 500);
            } catch (e) {
                console.error('Error rendering charts:', e);
            }
        }

        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.toggle('active', btn.textContent === (tab === 'technical' ? '技术分析' : '策略回测'));
            });
            document.getElementById('chartsView').style.display = tab === 'technical' ? 'flex' : 'none';
            document.getElementById('strategyView').classList.toggle('active', tab === 'strategy');
            if (tab === 'strategy') {
                const data = stockData[currentStock];
                if (data) renderStrategyData(data);
            }
        }

        function getSelectedStrategies() {
            return {
                momentum: [
                    document.getElementById('chk_momentum_1').checked,
                    document.getElementById('chk_momentum_2').checked
                ],
                reversal: [
                    document.getElementById('chk_reversal_1').checked,
                    document.getElementById('chk_reversal_2').checked,
                    document.getElementById('chk_reversal_3').checked
                ],
                turtle: [
                    document.getElementById('chk_turtle_1').checked,
                    document.getElementById('chk_turtle_2').checked
                ],
                benchmark: document.getElementById('chk_benchmark').checked
            };
        }

        function updateStrategyChart() {
            const data = stockData[currentStock];
            if (!data || !data.strategy) return;
            renderStrategyChart(data);
        }

        function renderStrategyData(data) {
            if (!data.strategy) return;
            renderStrategyChart(data);

            // 渲染策略统计卡片
            const grid = document.getElementById('strategyGrid');
            let html = '';
            const allStrategies = [...(data.strategy.momentum || []), ...(data.strategy.reversal || []), ...(data.strategy.turtle || [])];
            allStrategies.forEach(s => {
                const st = s.data.stats;
                const buyCount = st.buy_count || 0;
                const sellCount = st.sell_count || 0;
                const tradeCount = st.trade_count || (buyCount + sellCount);
                const turnoverRate = st.turnover_rate || 0;
                html += '<div class="strategy-card">';
                html += '<h4>' + s.name + '</h4>';
                html += '<div class="strategy-stats">';
                html += '<div class="strategy-stat"><span class="label">年化收益</span><span class="value ' + (st.annual_return >= 0 ? 'positive' : 'negative') + '">' + (st.annual_return >= 0 ? '+' : '') + st.annual_return + '%</span></div>';
                html += '<div class="strategy-stat"><span class="label">夏普比率</span><span class="value">' + st.sharpe_ratio + '</span></div>';
                html += '<div class="strategy-stat"><span class="label">最大回撤</span><span class="value negative">' + st.max_drawdown + '%</span></div>';
                html += '<div class="strategy-stat"><span class="label">日胜率</span><span class="value">' + st.win_rate + '%</span></div>';
                html += '<div class="strategy-stat"><span class="label">总收益</span><span class="value ' + (st.total_return >= 0 ? 'positive' : 'negative') + '">' + (st.total_return >= 0 ? '+' : '') + st.total_return + '%</span></div>';
                html += '<div class="strategy-stat"><span class="label">卡尔玛</span><span class="value">' + st.calmar_ratio + '</span></div>';
                html += '<div class="strategy-stat"><span class="label">买入/卖出</span><span class="value">' + buyCount + ' / ' + sellCount + '</span></div>';
                html += '<div class="strategy-stat"><span class="label">交易笔数</span><span class="value">' + tradeCount + '</span></div>';
                html += '<div class="strategy-stat"><span class="label">换手率</span><span class="value">' + turnoverRate + '%</span></div>';
                html += '</div></div>';
            });
            grid.innerHTML = html;
        }

        function renderStrategyChart(data) {
            const container = document.getElementById('strategyChart');
            if (!data.strategy_chart) {
                container.innerHTML = '<div style="padding:20px;color:#888;text-align:center;">暂无策略数据</div>';
                return;
            }

            const selected = getSelectedStrategies();
            const originalData = data.strategy_chart.data;
            const filteredTraces = [];

            // 策略名称映射
            const momentumNames = ['动量 231-21', '动量 189-63'];
            const reversalNames = ['反转 3日', '反转 5日', '反转 10日'];
            const turtleNames = ['海龟 20-10', '海龟 55-20'];

            // 过滤动量策略
            (data.strategy.momentum || []).forEach((item, i) => {
                if (selected.momentum[i]) {
                    const trace = originalData.find(t => t.name === item.name);
                    if (trace) filteredTraces.push(trace);
                }
            });

            // 过滤反转策略
            (data.strategy.reversal || []).forEach((item, i) => {
                if (selected.reversal[i]) {
                    const trace = originalData.find(t => t.name === item.name);
                    if (trace) filteredTraces.push(trace);
                }
            });

            // 过滤海龟策略
            (data.strategy.turtle || []).forEach((item, i) => {
                if (selected.turtle[i]) {
                    const trace = originalData.find(t => t.name === item.name);
                    if (trace) filteredTraces.push(trace);
                }
            });

            // 过滤基准
            if (selected.benchmark) {
                const trace = originalData.find(t => t.name === '买入持有');
                if (trace) filteredTraces.push(trace);
            }

            if (filteredTraces.length === 0) {
                container.innerHTML = '<div style="padding:20px;color:#888;text-align:center;">请选择要显示的策略</div>';
                return;
            }

            const rect = container.getBoundingClientRect();
            const layout = {
                ...data.strategy_chart.layout,
                autosize: false,
                width: rect.width || container.offsetWidth || 800,
                height: rect.height || container.offsetHeight || 320,
                margin: {l: 50, r: 20, t: 30, b: 40},
                showlegend: true,
                legend: {orientation: 'h', y: 1.05, x: 0.5, xanchor: 'center', font: {size: 10}}
            };

            container.innerHTML = '<div id="strategy-plot"></div>';
            Plotly.newPlot('strategy-plot', filteredTraces, layout, {responsive: false, displayModeBar: false});
        }

        function showCharts() {
            currentView = 'charts';
            const isStrategy = document.querySelector('.tab-btn.active') && document.querySelector('.tab-btn.active').textContent === '策略回测';
            document.getElementById('chartsView').style.display = isStrategy ? 'none' : 'flex';
            document.getElementById('strategyView').classList.toggle('active', isStrategy);
            document.getElementById('rankingView').classList.remove('active');
            document.getElementById('btnCharts').classList.add('active');
            document.getElementById('btnRanking').classList.remove('active');
        }

        function showRanking() {
            currentView = 'ranking';
            document.getElementById('chartsView').style.display = 'none';
            document.getElementById('strategyView').classList.remove('active');
            document.getElementById('rankingView').classList.add('active');
            document.getElementById('btnCharts').classList.remove('active');
            document.getElementById('btnRanking').classList.add('active');
            renderRanking();
        }

        function expandChart(chartId) {
            const chartTypeMap = {
                'chart1': 'ma',
                'chart2': 'returns',
                'chart3': 'drawdown',
                'chart4': 'volatility'
            };
            const periodKey = currentPeriod === 'd' ? '_d' : currentPeriod === 'w' ? '_w' : '_m';
            const type = chartTypeMap[chartId] + periodKey;
            const titleMap = {
                'chart1': 'K线+均线+成交量',
                'chart2': '净值',
                'chart3': '回撤分析',
                'chart4': '波动率'
            };
            const periodLabel = currentPeriod === 'd' ? '日线' : currentPeriod === 'w' ? '周线' : '月线';
            const data = stockData[currentStock];
            if (data && data[type]) {
                document.getElementById('modalTitle').textContent = `${currentStock} - ${titleMap[chartId]} (${periodLabel})`;
                const modalChart = document.getElementById('modalChart');
                modalChart.innerHTML = '<div id="modal-plot"></div>';
                
                document.getElementById('chartModal').classList.add('active');
                
                requestAnimationFrame(() => {
                    const rect = modalChart.getBoundingClientRect();
                    const layout = {
                        ...data[type].layout,
                        autosize: false,
                        width: rect.width,
                        height: rect.height,
                        margin: {l: 60, r: 20, t: 30, b: 40}
                    };
                    Plotly.newPlot('modal-plot', data[type].data, layout, {responsive: false});
                });
            }
        }

        function closeModal() {
            document.getElementById('chartModal').classList.remove('active');
            document.getElementById('modalChart').innerHTML = '';
        }

        function renderRanking() {
            const tbody = document.getElementById('rankBody');
            const sorted = filteredCodes.map(code => [code, calculateStats(code)]).sort((a, b) => b[1].return - a[1].return);
            tbody.innerHTML = sorted.map(([code, stats], i) => {
                const rank = i + 1;
                const returnClass = stats.return >= 0 ? 'positive' : 'negative';
                const returnSign = stats.return >= 0 ? '+' : '';
                const annualized = (stats.return * 252 / stockData[code].days).toFixed(2);
                const stockName = stockData[code] && stockData[code].name ? stockData[code].name : code;
                const strategyInfo = stockData[code] && stockData[code].strategy ? stockData[code].strategy : {};
                const adaptType = strategyInfo.adapt_type || '-';
                const adaptBadge = adaptType === '动量策略' ? '<span class="strategy-badge momentum">动量</span>' :
                                   adaptType === '反转策略' ? '<span class="strategy-badge reversal">反转</span>' :
                                   adaptType === '海龟策略' ? '<span class="strategy-badge turtle">海龟</span>' :
                                   '<span class="strategy-badge neutral">-</span>';
                return '<tr>' +
                    '<td>' + rank + '</td>' +
                    '<td class="code">' + code + '</td>' +
                    '<td>' + stockName + '</td>' +
                    '<td class="' + returnClass + '">' + returnSign + stats.return.toFixed(2) + '%</td>' +
                    '<td>' + annualized + '%</td>' +
                    '<td>' + stats.max_drawdown.toFixed(2) + '%</td>' +
                    '<td>' + stats.volume_ratio.toFixed(2) + '</td>' +
                    '<td>' + adaptBadge + '</td>' +
                    '<td><button class="quick-btn" onclick="quickSwitch(\\'' + code + '\\'); showCharts();">查看</button></td>' +
                '</tr>';
            }).join('');
        }

        renderRanking();

        document.addEventListener('DOMContentLoaded', function() {
            loadStockData();
        });
        </script>
        '''
        js_code = js_template
        html_parts.append(js_code)

        html_parts.extend(['</body>', '</html>'])

        # 清理NaN值为null以便JSON序列化
        import math
        def clean_nan(obj):
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(item) for item in obj]
            elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj

        # 保存文件
        output_path = output_dir / "batch_report.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        # 保存股票数据到外部JSON文件
        data_json_path = output_dir / "stock_data.json"
        cleaned_data = clean_nan(stock_data)
        with open(data_json_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

        logger.info(f"看板报告已保存: {output_path}")
        logger.info(f"股票数据已保存: {data_json_path}")
        return str(output_path)

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

        # 生成集成HTML报告
        integrated_path = self.save_integrated_html(df, stock_code, output_dir, include_benchmark, benchmark_df)
        paths['integrated'] = integrated_path

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
