"""
Binance交易所API实现
官方文档: https://binance-docs.github.io/apidocs/spot/en/
"""

import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
from .base import ExchangeBase

class BinanceExchange(ExchangeBase):
    """Binance交易所"""
    
    BASE_URL = "https://api.binance.com"
    FAPI_URL = "https://fapi.binance.com"
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.session = requests.Session()
    
    def get_spot_price(self, symbol: str) -> Optional[float]:
        """获取现货价格"""
        url = f"{self.BASE_URL}/api/v3/ticker/price"
        params = {'symbol': f'{symbol}USDT'}
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=30).json()
                return float(response['price'])
            except Exception as e:
                if attempt < 2:
                    print(f"Binance获取价格失败，重试 {attempt + 1}/3: {e}")
                    time.sleep(2)
                else:
                    print(f"Binance获取价格失败: {e}")
                    return None
        return None
    
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """获取资金费率"""
        url = f"{self.FAPI_URL}/fapi/v1/fundingRate"
        params = {'symbol': f'{symbol}USDT', 'limit': 1}
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=30).json()
                rate = float(response[0]['fundingRate']) * 100
                return round(rate, 4)
            except Exception as e:
                if attempt < 2:
                    print(f"Binance获取资金费率失败，重试 {attempt + 1}/3: {e}")
                    time.sleep(2)
                else:
                    print(f"Binance获取资金费率失败: {e}")
                    return None
        return None
    
    def get_longshort_ratio(self, symbol: str) -> Optional[Dict]:
        """获取多空比"""
        url = f"{self.FAPI_URL}/futures/data/topLongShortAccountRatio"
        params = {'symbol': f'{symbol}USDT', 'period': '1h', 'limit': 1}
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=30).json()
                if response:
                    latest = response[0]
                    long_ratio = float(latest['longAccount'])
                    short_ratio = float(latest['shortAccount'])
                    return {
                        'long': round(long_ratio * 100, 1),
                        'short': round(short_ratio * 100, 1),
                        'ratio': round(long_ratio / short_ratio, 2) if short_ratio > 0 else 0
                    }
            except Exception as e:
                if attempt < 2:
                    print(f"Binance获取多空比失败，重试 {attempt + 1}/3: {e}")
                    time.sleep(2)
                else:
                    print(f"Binance获取多空比失败: {e}")
        return None
    
    def get_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """获取历史K线"""
        url = f"{self.BASE_URL}/api/v3/klines"
        params = {
            'symbol': f'{symbol}USDT',
            'interval': interval.lower(),
            'startTime': int(start_time.timestamp() * 1000),
            'endTime': int(end_time.timestamp() * 1000),
            'limit': 1000
        }
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, timeout=30).json()
                return [{
                    'timestamp': datetime.fromtimestamp(k[0] / 1000),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                } for k in response]
            except Exception as e:
                if attempt < 2:
                    print(f"Binance获取K线失败，重试 {attempt + 1}/3: {e}")
                    time.sleep(2)
                else:
                    print(f"Binance获取K线失败: {e}")
                    return []