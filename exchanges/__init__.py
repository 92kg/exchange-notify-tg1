"""
交易所模块
提供统一的交易所接口
"""

from .base import ExchangeBase
from .okx import OKXExchange
from .binance import BinanceExchange

class ExchangeFactory:
    """交易所工厂类"""
    
    _exchanges = {
        'okx': OKXExchange,
        'binance': BinanceExchange,
    }
    
    @classmethod
    def create(cls, config: dict) -> ExchangeBase:
        """
        创建交易所实例
        :param config: 配置字典
        :return: 交易所实例
        """
        exchange_name = config.get('name', '').lower()
        
        if exchange_name not in cls._exchanges:
            raise ValueError(
                f"不支持的交易所: {exchange_name}. "
                f"支持: {', '.join(cls._exchanges.keys())}"
            )
        
        exchange_class = cls._exchanges[exchange_name]
        return exchange_class(config)
    
    @classmethod
    def list_supported(cls) -> list:
        """列出支持的交易所"""
        return list(cls._exchanges.keys())

__all__ = ['ExchangeFactory', 'ExchangeBase']