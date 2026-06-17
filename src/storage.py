# -*- coding: utf-8 -*-
"""
MongoDB存储模块 - 数据持久化
"""

import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError

from config import MONGODB_CONFIG
from src.logger import get_logger

logger = get_logger("Storage")


class MongoStorage:
    """MongoDB存储器"""

    def __init__(self, config: Dict = None):
        """
        初始化MongoDB连接

        Args:
            config: MongoDB配置
        """
        self.config = config if config else MONGODB_CONFIG
        self._client: Optional[MongoClient] = None
        self._db = None
        self._collection = None

    def connect(self) -> bool:
        """
        建立MongoDB连接

        Returns:
            连接是否成功
        """
        try:
            # 构建连接字符串
            if self.config.get("username") and self.config.get("password"):
                uri = f"mongodb://{self.config['username']}:{self.config['password']}@{self.config['host']}:{self.config['port']}"
            else:
                uri = f"mongodb://{self.config['host']}:{self.config['port']}"

            self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command('ping')  # 测试连接

            self._db = self._client[self.config["database"]]
            self._collection = self._db[self.config["collection"]]

            logger.info(f"MongoDB连接成功: {self.config['host']}:{self.config['port']}")
            return True

        except ConnectionFailure as e:
            logger.error(f"MongoDB连接失败: {e}")
            return False

    def disconnect(self):
        """断开MongoDB连接"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._collection = None
            logger.info("MongoDB连接已断开")

    def _ensure_index(self):
        """确保索引存在"""
        if self._collection is None:
            return

        try:
            # 创建复合索引：股票代码 + 日期
            self._collection.create_index(
                [("code", ASCENDING), ("date", DESCENDING)],
                unique=True,
                name="code_date_idx"
            )
            logger.debug("索引检查完成")
        except Exception as e:
            logger.warning(f"索引创建失败: {e}")

    def store(
        self,
        df: pd.DataFrame,
        stock_code: str = None,
        if_exists: str = "append"
    ) -> int:
        """
        存储DataFrame到MongoDB

        Args:
            df: 待存储的DataFrame
            stock_code: 股票代码
            if_exists: 如果存在怎么办 'append'/'replace'/'skip'

        Returns:
            插入的记录数
        """
        if self._collection is None:
            if not self.connect():
                return 0

        self._ensure_index()

        if df.empty:
            logger.warning("DataFrame为空，跳过存储")
            return 0

        # 添加股票代码列
        if stock_code and 'code' not in df.columns:
            df = df.copy()
            df['code'] = stock_code

        # 添加时间戳
        df = df.copy()
        df['updated_at'] = datetime.now()

        # 转换日期为字符串（MongoDB兼容）
        if 'date' in df.columns:
            df['date'] = df['date'].astype(str)

        records = df.to_dict('records')

        inserted_count = 0
        if if_exists == "skip":
            # 只插入不存在的
            for record in records:
                try:
                    self._collection.insert_one(record)
                    inserted_count += 1
                except DuplicateKeyError:
                    pass
        else:
            # 批量插入
            try:
                result = self._collection.insert_many(records, ordered=False)
                inserted_count = len(result.inserted_ids)
            except Exception as e:
                # 部分插入失败
                inserted_count = 0
                logger.error(f"批量插入失败: {e}")

        logger.info(f"存储完成: {inserted_count} 条记录")
        return inserted_count

    def load(
        self,
        stock_code: str = None,
        start_date: str = None,
        end_date: str = None,
        fields: List[str] = None,
        limit: int = None
    ) -> pd.DataFrame:
        """
        从MongoDB加载数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            fields: 要加载的字段
            limit: 最大记录数

        Returns:
            DataFrame
        """
        if self._collection is None:
            if not self.connect():
                return pd.DataFrame()

        # 构建查询条件
        query = {}

        if stock_code:
            query['code'] = stock_code

        if start_date or end_date:
            query['date'] = {}
            if start_date:
                query['date']['$gte'] = start_date
            if end_date:
                query['date']['$lte'] = end_date

        # 执行查询
        cursor = self._collection.find(query)

        if limit:
            cursor = cursor.limit(limit)

        # 转换为DataFrame
        data = list(cursor)

        if not data:
            return pd.DataFrame()

        # 移除MongoDB的_id字段
        for item in data:
            item.pop('_id', None)

        df = pd.DataFrame(data)

        # 转换日期列
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        logger.info(f"加载完成: {len(df)} 条记录")
        return df

    def exists(self, stock_code: str, start_date: str = None, end_date: str = None) -> bool:
        """
        检查数据是否已存在

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            是否存在
        """
        if self._collection is None:
            if not self.connect():
                return False

        query = {'code': stock_code}

        if start_date and end_date:
            query['date'] = {'$gte': start_date, '$lte': end_date}
        elif start_date:
            query['date'] = {'$gte': start_date}
        elif end_date:
            query['date'] = {'$lte': end_date}

        count = self._collection.count_documents(query)
        return count > 0

    def delete(self, stock_code: str = None, start_date: str = None, end_date: str = None) -> int:
        """
        删除数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            删除的记录数
        """
        if self._collection is None:
            if not self.connect():
                return 0

        query = {}

        if stock_code:
            query['code'] = stock_code

        if start_date or end_date:
            query['date'] = {}
            if start_date:
                query['date']['$gte'] = start_date
            if end_date:
                query['date']['$lte'] = end_date

        result = self._collection.delete_many(query)
        deleted = result.deleted_count

        logger.info(f"删除完成: {deleted} 条记录")
        return deleted

    def get_stock_list(self) -> List[str]:
        """
        获取数据库中已有的股票列表

        Returns:
            股票代码列表
        """
        if self._collection is None:
            if not self.connect():
                return []

        stocks = self._collection.distinct('code')
        return stocks

    def store_batch(
        self,
        data_dict: Dict[str, pd.DataFrame],
        if_exists: str = "append"
    ) -> Dict[str, int]:
        """
        批量存储多只股票数据

        Args:
            data_dict: Dict[stock_code, DataFrame]
            if_exists: 如果存在怎么办

        Returns:
            Dict[stock_code, 插入记录数]
        """
        logger.info(f"批量存储 {len(data_dict)} 只股票...")
        results = {}

        for code, df in data_dict.items():
            count = self.store(df, code, if_exists)
            results[code] = count

        success_count = sum(1 for c in results.values() if c > 0)
        logger.info(f"批量存储完成: {success_count}/{len(data_dict)} 成功")

        return results

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        return False


if __name__ == "__main__":
    # 测试代码
    import pandas as pd

    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10),
        'open': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        'high': [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
        'low': [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
        'close': [103, 104, 105, 106, 107, 108, 109, 110, 111, 112],
        'volume': [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000],
    })

    # 注意：需要MongoDB运行中才能测试
    # with MongoStorage() as storage:
    #     storage.store(df, "600519")
    #     df_loaded = storage.load("600519")
    #     print(df_loaded.head())
