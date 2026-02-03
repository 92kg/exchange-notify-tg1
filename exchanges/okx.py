"""
OKX交易所API实现
官方文档: https://www.okx.com/docs-v5/en/
"""

import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
from .base import ExchangeBase

class OKXExchange(ExchangeBase):
    """OKX交易所"""
    
    BASE_URL = "https://www.okx.com"
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def _make_request(self, endpoint: str, params: dict = None) -> Optional[list]:
        """统一请求处理"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 增加对 data 是否为字典的检查，防止 code 解析错误
            if isinstance(data, dict) and data.get('code') == '0':
                return data.get('data', [])
            elif isinstance(data, list):
                # 有些特殊接口可能直接返回列表
                return data
            else:
                msg = data.get('msg') if isinstance(data, dict) else "未知响应格式"
                print(f"OKX API错误: {msg}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"OKX请求失败: {e}")
            return None
        except Exception as e:
            print(f"OKX异常: {e}")
            return None
    def get_spot_price(self, symbol: str) -> Optional[float]:
        """获取现货价格"""
        endpoint = "/api/v5/market/ticker"
        params = {'instId': f'{symbol}-USDT'}
        
        data = self._make_request(endpoint, params)
        if data and len(data) > 0:
            try:
                return float(data[0]['last'])
            except (KeyError, ValueError, IndexError):
                return None
        return None
    
    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """获取资金费率"""
        endpoint = "/api/v5/public/funding-rate"
        params = {'instId': f'{symbol}-USDT-SWAP'}
        data = self._make_request(endpoint, params)
        if data and len(data) > 0:
            try:
                rate = float(data[0]['fundingRate']) * 100
                return round(rate, 4)
            except (KeyError, ValueError, IndexError):
                return None
        return None
    
    def get_longshort_ratio(self, symbol: str) -> Optional[Dict]:
        """
        获取多空比
        OKX API: Long/Short Account Ratio
        返回格式通常为: [["ts", "ratio"], ["ts", "ratio"], ...]
        """
        endpoint = "/api/v5/rubik/stat/contracts/long-short-account-ratio"
        params = {
            'ccy': symbol,
            'period': '1H'
        }
        
        data = self._make_request(endpoint, params)
        if isinstance(data, list) and len(data) > 0:
            try:
                latest = data[0]
                # OKX Rubik 接口通常返回数组: [ts, ratio]
                if isinstance(latest, list) and len(latest) >= 2:
                    ts = latest[0]
                    ratio = float(latest[1])
                    # 既然接口只给了一个比例 (Long/Short)，我们推算百分比
                    # Long / Short = ratio  => Long = ratio * Short
                    # Long + Short = 1      => ratio * Short + Short = 1 => Short = 1 / (ratio + 1)
                    short_p = 1 / (ratio + 1)
                    long_p = ratio / (ratio + 1)
                    
                    return {
                        'long': round(long_p * 100, 1),
                        'short': round(short_p * 100, 1),
                        'ratio': round(ratio, 2),
                        'timestamp': ts
                    }
                # 如果返回的是字典格式（部分 API 或未来版本）
                elif isinstance(latest, dict):
                    long_ratio = float(latest.get('longRatio', 0))
                    short_ratio = float(latest.get('shortRatio', 0))
                    ratio = float(latest.get('ratio', long_ratio/short_ratio if short_ratio > 0 else 0))
                    
                    return {
                        'long': round(long_ratio * 100, 1) if long_ratio < 1 else long_ratio,
                        'short': round(short_ratio * 100, 1) if short_ratio < 1 else short_ratio,
                        'ratio': round(ratio, 2),
                        'timestamp': latest.get('ts', '')
                    }
            except Exception as e:
                print(f"解析多空比数据详情失败: {e}, 数据样例: {latest}")
                return None
        return None


    def get_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        获取历史K线
        interval: '1D', '1H', '4H' 等
        """
        endpoint = "/api/v5/market/history-candles"

        # 转换时间戳（毫秒）
        after = str(int(start_time.timestamp() * 1000))
        before = str(int(end_time.timestamp() * 1000))

        params = {
            'instId': f'{symbol}-USDT',
            'bar': interval,
            'after': after,
            'before': before,
            'limit': '300'
        }

        all_data = []

        while True:
            data = self._make_request(endpoint, params)

            if not data or len(data) == 0:
                break
            
            try:
                for candle in data:
                    all_data.append({
                        'timestamp': datetime.fromtimestamp(int(candle[0]) / 1000),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5])
                    })
            except (ValueError, IndexError) as e:
                print(f"解析K线数据失败: {e}")
                break

            # 检查是否还有更多数据
            if len(data) < 300:
                break
            
            # 更新after参数继续获取
            params['after'] = data[-1][0]
            time.sleep(0.5)
        
        return all_data