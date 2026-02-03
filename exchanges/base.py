"""
交易所抽象基类
定义所有交易所必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime

class ExchangeBase(ABC):
    """交易所基类"""
    
    def __init__(self, config: dict):
        self.config = config
        self.name = config.get('name', 'unknown')
    
    @abstractmethod
    def get_spot_price(self, symbol: str) -> Optional[float]:
        """
        获取现货价格
        :param symbol: 币种符号（如 'BTC'）
        :return: 价格（USDT计价）
        """
        pass
    
    @abstractmethod
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        获取资金费率
        :param symbol: 币种符号
        :return: 资金费率（百分比）
        """
        pass
    
    @abstractmethod
    def get_longshort_ratio(self, symbol: str) -> Optional[Dict]:
        """
        获取多空比
        :param symbol: 币种符号
        :return: {'long': 多头%, 'short': 空头%, 'ratio': 多空比}
        """
        pass
    
    @abstractmethod
    def get_historical_klines(
        self, 
        symbol: str, 
        interval: str, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Dict]:
        """
        获取历史K线数据
        :param symbol: 币种符号
        :param interval: K线周期（'1d', '1h'等）
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return: K线数据列表
        """
        pass