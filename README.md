# StockDataTool

📈 股票数据处理与分析工具 - 一站式完成数据获取、清洗、分析、存储和可视化

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-green.svg)](https://github.com/yourusername/StockDataTool)

## 功能特性

- **数据获取**：从 Baostock 获取股票日线/周线/月线数据，支持本地缓存
- **数据检查**：自动检测缺失值、重复数据、停牌断点和异常价格
- **数据清洗**：智能清洗和预处理，确保数据质量
- **数据分析**：计算均线、回撤、收益率、波动率等指标
- **数据存储**：支持 MongoDB 持久化存储
- **可视化**：生成专业的 K 线图、回撤图、收益率图、波动率图
- **选股功能**：基于多因子策略筛选优质股票
- **策略回测**：支持动量、反转、海龟等经典策略回测

## 技术栈

- **Python 3.8+** - 核心编程语言
- **Baostock** - 免费股票数据接口
- **Pandas / NumPy** - 数据处理与分析
- **Plotly** - 交互式图表可视化
- **MongoDB** - 数据持久化存储（可选）
- **Loguru** - 日志管理

## 快速开始

### 环境要求

- Python 3.8+
- MongoDB（可选，用于数据存储）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

修改 [config.py](config.py) 配置股票列表和时间区间：

```python
STOCK_CONFIG = {
    "stock_list": {
        "600519": "贵州茅台",
        "000858": "五粮液",
        "000333": "美的集团",
        # 添加更多股票...
    },
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
}
```

### 运行

```bash
# 默认运行（处理 stock_list 中的第一只股票）
python main.py

# 指定单只股票
python main.py --stock 600519

# 批量处理所有股票
python main.py --mode batch

# 选股模式
python main.py --screen

# 指定时间区间
python main.py --stock 600519 --start 2024-01-01 --end 2024-12-31

# 指定周期（d=日线, w=周线, m=月线）
python main.py --period w

# 不保存到数据库
python main.py --no-db

# 不生成图表
python main.py --no-plot
```

## 项目结构

```
StockDataTool/
├── config.py                    # 配置文件（集中管理所有参数）
├── main.py                      # 主入口（命令行接口）
├── requirements.txt             # Python 依赖列表
├── README.md                    # 项目说明文档
├── src/                         # 核心模块
│   ├── __init__.py
│   ├── fetcher.py               # 数据获取模块（Baostock）
│   ├── checker.py               # 数据检查模块（质量校验）
│   ├── cleaner.py               # 数据清洗模块（预处理）
│   ├── analyzer.py              # 数据分析模块（指标计算）
│   ├── storage.py               # 数据存储模块（MongoDB）
│   ├── plotter.py               # 图表绘制模块（Plotly）
│   ├── logger.py                # 日志配置（Loguru）
│   └── strategy_backtest.py     # 策略回测模块
├── data/                        # 数据缓存目录
├── output/                      # 输出目录（图表、报告）
├── logs/                        # 日志目录
└── strategy/                    # 策略实验（Jupyter Notebook）
    ├── 动量因子/
    └── 反转因子/
```

## 核心模块说明

### Fetcher（数据获取）

- 从 Baostock 获取免费股票数据
- 支持日线、周线、月线
- 自动本地缓存，避免重复请求
- 支持 MongoDB 校验

### Checker（数据检查）

- 检查缺失值和重复行
- 检测停牌断点
- 识别异常价格波动

### Cleaner（数据清洗）

- 按日期排序
- 删除重复数据
- 类型转换
- 缺失值处理

### Analyzer（数据分析）

- 计算均线（MA5/MA10/MA20/MA30/MA60）
- 计算回撤和收益率
- 计算波动率
- 选股筛选

### Plotter（图表绘制）

- K 线图（含成交量）
- 均线 + RSI + MACD 综合图
- 回撤图
- 收益率对比图
- 波动率图
- 批量分析报告（4宫格看板）

### Storage（数据存储）

- MongoDB 存储
- 支持增量更新
- 支持批量存储

### StrategyBacktest（策略回测）

- 动量策略回测
- 反转策略回测
- 海龟策略回测
- 策略绩效评估

## 输出文件

运行后在 `output/` 目录生成：

| 文件 | 说明 |
|------|------|
| `{stock_code}_report.html` | 单只股票分析报告 |
| `batch_report.html` | 批量分析看板（4宫格） |
| `screening_result.html` | 选股结果表格 |

## 配置说明

### 运行模式

在 [config.py](config.py) 中控制流水线各阶段是否执行：

```python
RUN_MODE = {
    "fetch": True,    # 获取数据
    "check": True,    # 检查数据
    "clean": True,    # 清洗数据
    "analyze": True,  # 分析数据
    "store": True,    # 存储数据库
    "plot": True,     # 绘图
}
```

### 分析指标

```python
ANALYSIS_CONFIG = {
    "ma_periods": [5, 10, 20, 30, 60],    # 均线周期
    "calculate_drawdown": True,            # 计算回撤
    "calculate_returns": True,             # 计算收益率
    "calculate_volatility": True,          # 计算波动率
    "benchmark": "000300",                 # 基准（沪深300）
}
```

### 绘图配置

```python
PLOT_CONFIG = {
    "width": 1200,
    "height": 600,
    "template": "plotly_white",
    "theme": {
        "up_color": "#c53030",    # 上涨颜色
        "down_color": "#276749",  # 下跌颜色
    },
}
```

## 选股筛选条件

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `annualized_return_min` | 年化收益最小值 | 10% |
| `max_drawdown_max` | 最大回撤最大值 | -20% |
| `ma_golden_cross` | 均线多头排列 | False |
| `volume_breakout` | 放量突破 | False |

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--stock` | 指定股票代码 | 配置文件中第一只 |
| `--mode` | 运行模式（single/batch） | batch |
| `--screen` | 启用选股模式 | False |
| `--start` | 开始日期 | 配置文件中 start_date |
| `--end` | 结束日期 | 配置文件中 end_date |
| `--period` | 数据周期（d/w/m） | d |
| `--no-db` | 不保存到数据库 | False |
| `--no-plot` | 不生成图表 | False |

## 使用示例

### 示例 1：分析单只股票

```bash
python main.py --stock 600519 --start 2024-01-01 --end 2024-12-31
```

### 示例 2：批量分析所有股票

```bash
python main.py --mode batch --period w
```

### 示例 3：选股筛选

```bash
python main.py --screen --start 2024-01-01 --end 2024-12-31
```

## License

MIT License

## Contributing

欢迎提交 Issue 和 Pull Request！

## 致谢

- [Baostock](http://www.baostock.com/) - 免费股票数据接口
- [Plotly](https://plotly.com/) - 交互式图表库
- [Pandas](https://pandas.pydata.org/) - 数据分析库