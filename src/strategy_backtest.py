# -*- coding: utf-8 -*-
"""
策略回测模块 - 动量因子 & 反转因子
用于评估单只股票的策略适配度
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.logger import get_logger

logger = get_logger("StrategyBacktest")


class StrategyBacktest:
    """策略回测器 - 针对单只股票评估动量/反转策略适配度"""

    def __init__(self):
        pass

    @staticmethod
    def momentum_factor(prices: pd.Series, lookback: int = 63, lag: int = 21) -> pd.Series:
        """
        动量因子: 过去 (lookback+lag) 到 lag 天的累计收益
        经典版: lookback=231, lag=21 (12-1)
        改良版: lookback=189, lag=63 (25-5, 平滑噪音)
        """
        return prices.shift(lag).pct_change(lookback)

    @staticmethod
    def reversal_factor(returns: pd.Series, n_days: int = 5) -> pd.Series:
        """
        反转因子: -(过去N天累计收益)
        负号让「跌得多」分数最高
        """
        return -returns.rolling(n_days).sum()

    @staticmethod
    def compute_ic(factor: pd.Series, future_returns: pd.Series, freq: str = 'ME') -> pd.Series:
        """
        计算 RankIC 时间序列
        对于单只股票，按月度计算因子值与未来收益的秩相关系数
        """
        # 将日频数据重采样为月频
        monthly_factor = factor.resample(freq).last().dropna()
        monthly_ret = future_returns.resample(freq).last().shift(-1).dropna()

        common = monthly_factor.index.intersection(monthly_ret.index)
        ics = []
        for d in common:
            f_val = monthly_factor.loc[d]
            r_val = monthly_ret.loc[d]
            if pd.notna(f_val) and pd.notna(r_val):
                # 单只股票无法计算秩相关系数，改用 Pearson 相关系数
                ics.append(np.sign(f_val * r_val))
        return pd.Series(ics, index=common)

    def backtest_momentum(self, df: pd.DataFrame, lookback: int = 63, lag: int = 21,
                          hold_days: int = 21, threshold: float = 0.0) -> Dict[str, Any]:
        """
        动量策略回测
        当动量因子 > threshold 时做多，持有 hold_days

        Returns:
            Dict 包含: dates, equity, returns, stats
        """
        if df.empty or 'close' not in df.columns:
            return None

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        prices = df['close']
        daily_ret = prices.pct_change().fillna(0)

        # 计算动量因子
        factor = self.momentum_factor(prices, lookback, lag)

        # 生成交易信号: 因子 > threshold 时做多
        signal = (factor > threshold).astype(int)

        # 计算策略收益（信号延迟1天执行）
        strategy_ret = signal.shift(1).fillna(0) * daily_ret

        # 计算累计净值
        equity = (1 + strategy_ret).cumprod()

        # 计算统计指标
        stats = self._calc_stats(strategy_ret, equity)

        # 统计买卖交易笔数
        signal_shifted = signal.shift(1).fillna(0)
        buy_count = int((signal_shifted.diff().fillna(0) == 1).sum())
        sell_count = int((signal_shifted.diff().fillna(0) == -1).sum())
        stats['buy_count'] = buy_count
        stats['sell_count'] = sell_count
        stats['trade_count'] = buy_count + sell_count

        return {
            'dates': equity.index.strftime('%Y-%m-%d').tolist(),
            'equity': equity.values.tolist(),
            'returns': strategy_ret.values.tolist(),
            'factor': factor.fillna(0).values.tolist(),
            'signal': signal.fillna(0).values.tolist(),
            'stats': stats,
            'params': {'lookback': lookback, 'lag': lag, 'hold_days': hold_days, 'threshold': threshold}
        }

    def backtest_reversal(self, df: pd.DataFrame, n_days: int = 5,
                          hold_days: int = 7, threshold: float = 0.0) -> Dict[str, Any]:
        """
        反转策略回测
        当反转因子 > threshold 时做多（即过去N天跌得多），持有 hold_days

        Returns:
            Dict 包含: dates, equity, returns, stats
        """
        if df.empty or 'close' not in df.columns:
            return None

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        prices = df['close']
        daily_ret = prices.pct_change().fillna(0)

        # 计算反转因子
        factor = self.reversal_factor(daily_ret, n_days)

        # 生成交易信号: 因子 > threshold 时做多（跌得多 -> 买入）
        signal = (factor > threshold).astype(int)

        # 计算策略收益（信号延迟1天执行）
        strategy_ret = signal.shift(1).fillna(0) * daily_ret

        # 计算累计净值
        equity = (1 + strategy_ret).cumprod()

        # 计算统计指标
        stats = self._calc_stats(strategy_ret, equity)

        # 统计买卖交易笔数
        signal_shifted = signal.shift(1).fillna(0)
        buy_count = int((signal_shifted.diff().fillna(0) == 1).sum())
        sell_count = int((signal_shifted.diff().fillna(0) == -1).sum())
        stats['buy_count'] = buy_count
        stats['sell_count'] = sell_count
        stats['trade_count'] = buy_count + sell_count

        return {
            'dates': equity.index.strftime('%Y-%m-%d').tolist(),
            'equity': equity.values.tolist(),
            'returns': strategy_ret.values.tolist(),
            'factor': factor.fillna(0).values.tolist(),
            'signal': signal.fillna(0).values.tolist(),
            'stats': stats,
            'params': {'n_days': n_days, 'hold_days': hold_days, 'threshold': threshold}
        }

    def backtest_turtle(self, df: pd.DataFrame, entry_window: int = 20,
                        exit_window: int = 10) -> Dict[str, Any]:
        """
        海龟策略回测（突破系统）
        
        入场信号：价格突破 entry_window 日最高价时买入
        出场信号：价格跌破 exit_window 日最低价时卖出
        
        Args:
            df: DataFrame，需包含 date, close, high, low
            entry_window: 入场突破窗口（默认20日）
            exit_window: 出场突破窗口（默认10日）
            
        Returns:
            Dict 包含: dates, equity, returns, stats
        """
        if df.empty or 'close' not in df.columns or 'high' not in df.columns or 'low' not in df.columns:
            return None

        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        prices = df['close']
        highs = df['high']
        lows = df['low']
        daily_ret = prices.pct_change().fillna(0)

        # 计算突破通道
        entry_high = highs.rolling(entry_window).max()  # 入场：突破N日最高
        exit_low = lows.rolling(exit_window).min()      # 出场：跌破M日最低

        # 生成交易信号
        signal = pd.Series(0, index=prices.index)
        position = 0  # 当前持仓状态

        for i in range(entry_window, len(prices)):
            if position == 0:  # 无持仓
                # 入场条件：收盘价突破 entry_window 最高价
                if prices.iloc[i] >= entry_high.iloc[i - 1]:
                    position = 1
                    signal.iloc[i] = 1
            else:  # 有持仓
                # 出场条件：收盘价跌破 exit_window 最低价
                if prices.iloc[i] <= exit_low.iloc[i - 1]:
                    position = 0
                    signal.iloc[i] = 0
                else:
                    signal.iloc[i] = 1  # 继续持有

        # 计算策略收益（信号延迟1天执行）
        strategy_ret = signal.shift(1).fillna(0) * daily_ret

        # 计算累计净值
        equity = (1 + strategy_ret).cumprod()

        # 计算统计指标
        stats = self._calc_stats(strategy_ret, equity)

        # 统计买卖交易笔数
        signal_shifted = signal.shift(1).fillna(0)
        buy_count = int((signal_shifted.diff().fillna(0) == 1).sum())
        sell_count = int((signal_shifted.diff().fillna(0) == -1).sum())
        stats['buy_count'] = buy_count
        stats['sell_count'] = sell_count
        stats['trade_count'] = buy_count + sell_count
        stats['trades'] = buy_count  # 兼容旧字段

        return {
            'dates': equity.index.strftime('%Y-%m-%d').tolist(),
            'equity': equity.values.tolist(),
            'returns': strategy_ret.values.tolist(),
            'signal': signal.values.tolist(),
            'stats': stats,
            'params': {'entry_window': entry_window, 'exit_window': exit_window}
        }

    def _calc_stats(self, returns: pd.Series, equity: pd.Series) -> Dict[str, float]:
        """计算策略统计指标"""
        if len(returns) == 0:
            return {}

        ann_ret = returns.mean() * 252
        ann_vol = returns.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        max_dd = (equity / equity.cummax() - 1).min()
        win_rate = (returns > 0).mean()
        calmar = ann_ret / abs(max_dd) if max_dd != 0 else 0

        return {
            'annual_return': round(ann_ret * 100, 2),
            'annual_volatility': round(ann_vol * 100, 2),
            'sharpe_ratio': round(sharpe, 2),
            'max_drawdown': round(max_dd * 100, 2),
            'win_rate': round(win_rate * 100, 2),
            'calmar_ratio': round(calmar, 2),
            'total_return': round((equity.iloc[-1] - 1) * 100, 2) if len(equity) > 0 else 0,
            'trading_days': len(returns),
        }

    def evaluate_strategies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        综合评估动量、反转和海龟策略对单只股票的适配度

        Returns:
            Dict 包含三种策略的回测结果和适配度评分
        """
        if df.empty or 'close' not in df.columns:
            return None

        # 动量策略回测 (多种参数)
        momentum_results = []
        for lookback, lag in [(231, 21), (189, 63)]:
            result = self.backtest_momentum(df, lookback=lookback, lag=lag)
            if result:
                momentum_results.append({
                    'name': f'动量 {lookback}-{lag}',
                    'data': result
                })

        # 反转策略回测 (多种参数)
        reversal_results = []
        for n in [3, 5, 10]:
            result = self.backtest_reversal(df, n_days=n)
            if result:
                reversal_results.append({
                    'name': f'反转 {n}日',
                    'data': result
                })

        # 海龟策略回测 (突破系统)
        turtle_results = []
        for entry, exit in [(20, 10), (55, 20)]:
            result = self.backtest_turtle(df, entry_window=entry, exit_window=exit)
            if result:
                turtle_results.append({
                    'name': f'海龟 {entry}-{exit}',
                    'data': result
                })

        # 计算适配度评分 (基于夏普比率和最大回撤)
        def score_strategy(stats):
            if not stats:
                return 0
            sharpe = stats.get('sharpe_ratio', 0)
            max_dd = abs(stats.get('max_drawdown', 0))
            # 夏普 > 0.5 且 回撤 < 20% 为适配
            if sharpe > 0.5 and max_dd < 20:
                return sharpe * (1 - max_dd / 100) * 100
            return 0

        # 找出最佳策略
        all_results = momentum_results + reversal_results + turtle_results
        best = None
        best_score = -999
        for r in all_results:
            score = score_strategy(r['data']['stats'])
            if score > best_score:
                best_score = score
                best = r

        # 判断股票更适合哪种策略类型
        mom_best_score = max([score_strategy(r['data']['stats']) for r in momentum_results], default=0)
        rev_best_score = max([score_strategy(r['data']['stats']) for r in reversal_results], default=0)
        turtle_best_score = max([score_strategy(r['data']['stats']) for r in turtle_results], default=0)

        scores = {
            '动量策略': mom_best_score,
            '反转策略': rev_best_score,
            '海龟策略': turtle_best_score,
        }
        adapt_type = max(scores, key=scores.get)
        adapt_score = scores[adapt_type]
        if adapt_score == 0:
            adapt_type = '无明显优势'

        return {
            'momentum': momentum_results,
            'reversal': reversal_results,
            'turtle': turtle_results,
            'best_strategy': best['name'] if best else '无',
            'best_score': round(best_score, 2),
            'adapt_type': adapt_type,
            'adapt_score': round(adapt_score, 2),
        }

    def plot_strategy_equity(self, strategy_data: Dict[str, Any], stock_code: str = "",
                             benchmark_equity: List[float] = None) -> go.Figure:
        """
        绘制策略净值曲线对比图

        Args:
            strategy_data: evaluate_strategies 返回的结果
            stock_code: 股票代码
            benchmark_equity: 基准净值曲线

        Returns:
            Plotly Figure
        """
        if not strategy_data:
            return None

        fig = go.Figure()

        # 清晰的颜色区分 + 线宽区分，全部使用实线
        colors = {
            '动量 231-21': '#1565c0',  # 深蓝
            '动量 189-63': '#42a5f5',  # 亮蓝
            '反转 3日': '#c62828',     # 深红
            '反转 5日': '#ef5350',     # 亮红
            '反转 10日': '#ff7043',    # 橙红
            '海龟 20-10': '#2e7d32',   # 深绿
            '海龟 55-20': '#66bb6a',  # 亮绿
        }

        # 通过线宽区分主次策略，全部实线
        line_styles = {
            '动量 231-21': {'width': 3.0, 'dash': 'solid'},  # 粗实线
            '动量 189-63': {'width': 1.8, 'dash': 'solid'},
            '反转 3日': {'width': 3.0, 'dash': 'solid'},    # 粗实线
            '反转 5日': {'width': 1.8, 'dash': 'solid'},
            '反转 10日': {'width': 1.2, 'dash': 'solid'},
            '海龟 20-10': {'width': 3.0, 'dash': 'solid'},  # 粗实线
            '海龟 55-20': {'width': 1.8, 'dash': 'solid'},
        }

        # 绘制动量策略
        for item in strategy_data.get('momentum', []):
            data = item['data']
            name = item['name']
            style = line_styles.get(name, {'width': 1.5, 'dash': 'solid'})
            fig.add_trace(go.Scatter(
                x=data['dates'],
                y=data['equity'],
                mode='lines',
                name=name,
                line=dict(color=colors.get(name, '#1565c0'), width=style['width'], dash=style['dash']),
            ))

        # 绘制反转策略
        for item in strategy_data.get('reversal', []):
            data = item['data']
            name = item['name']
            style = line_styles.get(name, {'width': 1.5, 'dash': 'dash'})
            fig.add_trace(go.Scatter(
                x=data['dates'],
                y=data['equity'],
                mode='lines',
                name=name,
                line=dict(color=colors.get(name, '#c62828'), width=style['width'], dash=style['dash']),
            ))

        # 绘制海龟策略
        for item in strategy_data.get('turtle', []):
            data = item['data']
            name = item['name']
            style = line_styles.get(name, {'width': 2.5, 'dash': 'dot'})
            fig.add_trace(go.Scatter(
                x=data['dates'],
                y=data['equity'],
                mode='lines',
                name=name,
                line=dict(color=colors.get(name, '#43a047'), width=style['width'], dash=style['dash']),
            ))

        # 添加基准线 (买入持有)
        if benchmark_equity:
            dates = None
            if strategy_data.get('momentum'):
                dates = strategy_data['momentum'][0]['data']['dates']
            elif strategy_data.get('turtle'):
                dates = strategy_data['turtle'][0]['data']['dates']
            if dates:
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=benchmark_equity,
                    mode='lines',
                    name='买入持有',
                    line=dict(color='#9e9e9e', width=2.0, dash='longdashdot'),
                ))

        fig.update_layout(
            template='plotly_white',
            margin=dict(l=60, r=20, t=30, b=40),
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.05,
                xanchor='center',
                x=0.5,
                font=dict(size=10)
            ),
            dragmode='pan',
            hovermode='x unified',
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
            title_font=dict(size=10),
        )

        return fig
