# -*- coding: utf-8 -*-
"""
选股工具Web应用
基于Flask的选股工具，提供API接口和Web界面
"""

import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify

# 尝试导入必要的库
try:
    from src.fetcher import StockFetcher
    from src.checker import DataChecker
    from src.cleaner import DataCleaner
    from src.analyzer import DataAnalyzer
    from src.plotter import StockPlotter
    import config
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖: pip install -r requirements.txt")

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'stock-screening-tool'
app.config['JSON_AS_ASCII'] = False

# 初始化组件
fetcher = StockFetcher(use_cache=True)
checker = DataChecker()
cleaner = DataCleaner()
analyzer = DataAnalyzer()
plotter = StockPlotter()


def get_stock_pool():
    """获取股票池"""
    return config.STOCK_CONFIG.get("stock_list", [])


@app.route('/')
def index():
    """主页"""
    return render_template('stock_screen.html')


@app.route('/api/stock_pool')
def api_stock_pool():
    """获取股票池列表"""
    stock_pool = get_stock_pool()
    return jsonify({
        'code': 0,
        'data': stock_pool
    })


@app.route('/api/screen', methods=['POST'])
def api_screen():
    """
    选股筛选API

    请求参数:
    {
        "annualized_return_min": 0.1,   # 年化收益 > X%
        "max_drawdown_max": -0.2,       # 最大回撤 < Y%
        "ma_golden_cross": true,         # 均线多头排列
        "volume_breakout": true,         # 放量突破
        "start_date": "2024-01-01",
        "end_date": "2025-12-31"
    }
    """
    try:
        params = request.get_json()

        # 提取筛选条件
        criteria = {}

        annualized_return_min = params.get('annualized_return_min')
        if annualized_return_min is not None:
            criteria['annualized_return_min'] = float(annualized_return_min) / 100  # 转为小数

        max_drawdown_max = params.get('max_drawdown_max')
        if max_drawdown_max is not None:
            criteria['max_drawdown_max'] = float(max_drawdown_max) / 100  # 转为负数

        criteria['ma_golden_cross'] = params.get('ma_golden_cross', False)
        criteria['volume_breakout'] = params.get('volume_breakout', False)

        start_date = params.get('start_date', config.STOCK_CONFIG['start_date'])
        end_date = params.get('end_date', config.STOCK_CONFIG['end_date'])

        # 获取股票池
        stock_pool = params.get('stock_pool')
        if not stock_pool:
            stock_pool = get_stock_pool()

        print(f"开始选股筛选: {len(stock_pool)} 只股票")
        print(f"筛选条件: {criteria}")

        # 批量获取数据
        data_dict = fetcher.fetch_batch(stock_pool, start_date, end_date)

        # 批量清洗
        cleaned_dict = cleaner.clean_batch(data_dict)

        # 批量分析
        analyzed_dict = analyzer.analyze_batch(cleaned_dict)

        # 筛选
        results = analyzer.screen_stocks(analyzed_dict, criteria)

        # 添加放量突破判断
        if criteria.get('volume_breakout'):
            results = _filter_volume_breakout(analyzed_dict, results)

        # 格式化结果
        formatted_results = []
        for r in results:
            formatted = {
                'stock_code': r.get('stock_code', ''),
                'total_return': r.get('total_return', 'N/A'),
                'annualized_return': f"{r.get('annualized_return', 0) * 100:.2f}%" if 'annualized_return' in r else 'N/A',
                'max_drawdown': f"{r.get('drawdown_pct', 0):.2f}%" if 'drawdown_pct' in r else 'N/A',
                'ma_golden_cross': r.get('ma_golden_cross', False),
                'volume_breakout': r.get('volume_breakout', False),
                'avg_volume': f"{r.get('avg_volume', 0):.0f}" if 'avg_volume' in r else 'N/A',
            }
            formatted_results.append(formatted)

        return jsonify({
            'code': 0,
            'message': f'筛选完成，共 {len(formatted_results)} 只股票符合条件',
            'data': formatted_results,
            'criteria': {
                'annualized_return_min': annualized_return_min,
                'max_drawdown_max': max_drawdown_max,
                'ma_golden_cross': criteria.get('ma_golden_cross'),
                'volume_breakout': criteria.get('volume_breakout'),
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 1,
            'message': f'筛选失败: {str(e)}',
            'data': []
        }), 500


def _filter_volume_breakout(analyzed_dict, results):
    """
    筛选放量突破的股票

    放量突破条件：
    1. 今日成交量 > 20日均量的1.5倍
    2. 今日收盘价 > 20日最高价
    """
    filtered = []

    for r in results:
        stock_code = r.get('stock_code')
        if stock_code not in analyzed_dict:
            continue

        df = analyzed_dict[stock_code]
        if df.empty or len(df) < 21:
            continue

        # 获取最新数据和20日数据
        latest = df.iloc[-1]
        ma20_volume = df['volume'].iloc[-20:].mean()
        ma20_high = df['high'].iloc[-20:].max()

        # 判断放量突破
        volume_ratio = latest['volume'] / ma20_volume if ma20_volume > 0 else 0
        price_breakout = latest['close'] > ma20_high

        if volume_ratio > 1.5 and price_breakout:
            r['volume_breakout'] = True
            r['volume_ratio'] = f"{volume_ratio:.2f}"
            filtered.append(r)
        else:
            r['volume_breakout'] = False
            r['volume_ratio'] = f"{volume_ratio:.2f}"
            # 如果只是要求放量突破但没有这个条件，仍保留
            if not results[0].get('volume_breakout') if results else True:
                filtered.append(r)

    return filtered


@app.route('/api/stock/<stock_code>')
def api_stock_detail(stock_code):
    """获取单只股票的详细分析"""
    try:
        start_date = request.args.get('start_date', config.STOCK_CONFIG['start_date'])
        end_date = request.args.get('end_date', config.STOCK_CONFIG['end_date'])

        # 获取数据
        df = fetcher.fetch_daily(stock_code, start_date, end_date)

        # 清洗
        df_clean = cleaner.clean(df)

        # 分析
        df_analyzed = analyzer.analyze(df_clean, stock_code)

        # 统计
        stats = analyzer.get_summary_stats(df_analyzed, stock_code)

        return jsonify({
            'code': 0,
            'data': {
                'stock_code': stock_code,
                'stats': stats,
                'data_range': f"{df['date'].min()} ~ {df['date'].max()}" if 'date' in df.columns else 'N/A',
                'row_count': len(df)
            }
        })

    except Exception as e:
        return jsonify({
            'code': 1,
            'message': f'获取失败: {str(e)}'
        }), 500


@app.route('/api/chart/<stock_code>')
def api_chart(stock_code):
    """生成股票图表"""
    try:
        start_date = request.args.get('start_date', config.STOCK_CONFIG['start_date'])
        end_date = request.args.get('end_date', config.STOCK_CONFIG['end_date'])

        # 获取并处理数据
        df = fetcher.fetch_daily(stock_code, start_date, end_date)
        df_clean = cleaner.clean(df)
        df_analyzed = analyzer.analyze(df_clean, stock_code)

        # 保存图表
        output_dir = Path(config.PLOT_CONFIG['output_dir'])
        paths = plotter.save_all(df_analyzed, stock_code, output_dir)

        return jsonify({
            'code': 0,
            'data': paths
        })

    except Exception as e:
        return jsonify({
            'code': 1,
            'message': f'生成图表失败: {str(e)}'
        }), 500


@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok'})


def create_template_dir():
    """创建模板目录"""
    template_dir = Path(__file__).parent / 'templates'
    template_dir.mkdir(exist_ok=True)
    return template_dir


if __name__ == '__main__':
    # 创建模板目录
    create_template_dir()

    print("=" * 50)
    print("选股工具Web应用")
    print("=" * 50)
    print("访问地址: http://127.0.0.1:5000")
    print("=" * 50)

    # 启动应用
    app.run(host='0.0.0.0', port=5000, debug=True)
