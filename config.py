# -*- coding: utf-8 -*-
"""
配置文件 - 集中管理所有配置参数
换股票、换区间只改这一处
"""

from pathlib import Path

# ========== 项目路径 ==========
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# ========== 数据源配置 (Baostock) ==========
BAOSTOCK_CONFIG = {
    "use_cache": True,           # 是否启用本地缓存
    "cache_dir": DATA_DIR,        # 缓存目录
}

# ========== MongoDB 配置 ==========
MONGODB_CONFIG = {
    "host": "localhost",
    "port": 27017,
    "database": "stock_data",
    "collection": "daily_kline",
    "username": "",
    "password": "",
}

# ========== 股票配置 ==========
STOCK_CONFIG = {
    # 股票列表（字典格式：代码 -> 名称）
    "stock_list": {
        "600519": "贵州茅台",
        "000858": "五粮液",
        "000333": "美的集团",
        "600036": "招商银行",
        "601318": "中国平安",
        "000001": "平安银行",
        "600887": "伊利股份",
        "000568": "泸州老窖",
    },
    # 时间区间
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
}

# ========== 数据检查配置 ==========
CHECK_CONFIG = {
    "check_missing": True,        # 检查缺失值
    "check_duplicate": True,      # 检查重复行
    "check_suspended": True,      # 检查停牌断点
    "check_anomaly": True,        # 检查异常价格
    # 异常价格阈值
    "price_min": 0.01,            # 最低价格
    "price_max": 10000,           # 最高价格
    "pct_change_max": 20,         # 最大涨跌幅 (%)
}

# ========== 清洗配置 ==========
CLEAN_CONFIG = {
    "sort_by_date": True,         # 按日期排序
    "drop_duplicates": True,      # 删除重复行
    "fill_missing": False,        # 填充缺失值 (False=删除, True=前向填充)
    "convert_types": True,        # 类型转换
}

# ========== 分析指标配置 ==========
ANALYSIS_CONFIG = {
    # 均线周期
    "ma_periods": [5, 10, 20, 30, 60],
    # 计算回撤
    "calculate_drawdown": True,
    # 计算收益率
    "calculate_returns": True,
    # 计算波动率
    "calculate_volatility": True,
    # 基准收益率 (用于计算超额收益)
    "benchmark": "000300",  # 沪深300
}

# ========== 绘图配置 ==========
PLOT_CONFIG = {
    "width": 1200,
    "height": 600,
    "template": "plotly_white",
    "theme": {
        "up_color": "#c53030",    # 上涨颜色（深红色 - 金融风格）
        "down_color": "#276749",  # 下跌颜色（深绿色 - 金融风格）
        "ma_colors": ["#c53030", "#2c5282", "#64748b", "#94a3b8", "#cbd5e0"],
    },
    "output_dir": OUTPUT_DIR,
}

# ========== 日志配置 ==========
LOG_CONFIG = {
    "level": "INFO",              # DEBUG/INFO/WARNING/ERROR
    "file": LOG_DIR / "stock_pipeline.log",
    "rotation": "10 MB",          # 日志轮转大小
    "retention": "7 days",        # 日志保留天数
    "console": True,              # 是否输出到控制台
}

# ========== 运行模式 ==========
RUN_MODE = {
    "fetch": True,                # 获取数据
    "check": True,                # 检查数据
    "clean": True,                # 清洗数据
    "analyze": True,              # 分析数据
    "store": True,                # 存储数据库
    "plot": True,                 # 绘图
}
