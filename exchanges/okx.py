"""
OKX交易所API实现
官方文档: https://www.okx.com/docs-v5/en/
"""

import requests
import time
import hmac
import base64
import hashlib
import json
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
        
        # API Keys
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.passphrase = config.get('api_passphrase', '')
    
    def _get_timestamp(self) -> str:
        """获取ISO格式时间戳"""
        return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
        
    def _sign(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """生成签名"""
        if not self.api_secret:
            return ""
            
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.api_secret, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def _make_request(self, endpoint: str, params: dict = None, method: str = 'GET', max_retries=3) -> Optional[list]:
        """统一请求处理"""
        url = f"{self.BASE_URL}{endpoint}"
        
        # 准备请求头
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # 签名逻辑 (如果配置了API Key)
        if self.api_key and self.passphrase:
            timestamp = self._get_timestamp()
            
            # 处理参数
            request_path = endpoint
            body = ''
            
            if method == 'GET' and params:
                query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
                request_path = f"{endpoint}?{query_string}"
            elif method == 'POST' and params:
                body = json.dumps(params)
            
            # 生成签名
            signature = self._sign(timestamp, method, request_path, body)
            
            headers.update({
                'OK-ACCESS-KEY': self.api_key,
                'OK-ACCESS-SIGN': signature,
                'OK-ACCESS-TIMESTAMP': timestamp,
                'OK-ACCESS-PASSPHRASE': self.passphrase
            })

        for attempt in range(max_retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, params=params, headers=headers, timeout=30)
                else:
                    response = self.session.post(url, json=params, headers=headers, timeout=30)
                    
                response.raise_for_status()
                data = response.json()

                if isinstance(data, dict) and data.get('code') == '0':
                    return data.get('data', [])
                elif isinstance(data, list):
                    return data
                else:
                    msg = data.get('msg') if isinstance(data, dict) else "未知响应格式"
                    # print(f"OKX API错误: {msg}")  # 调试用
                    return None
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    print(f"OKX请求失败 ({endpoint}): {e}")
                    return None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return None
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
        
        OKX API 分页说明:
        - after: 获取比此时间戳更早的数据（往历史方向查）
        - before: 获取比此时间戳更新的数据（往当前方向查）
        """
        endpoint = "/api/v5/market/history-candles"

        # 转换时间戳（毫秒）
        # 修复：从 end_time 开始往回查，获取 [start_time, end_time] 范围的数据
        start_ms = int(start_time.timestamp() * 1000)
        after = str(int(end_time.timestamp() * 1000))

        params = {
            'instId': f'{symbol}-USDT',
            'bar': interval,
            'after': after,  # 从 end_time 开始往回查
            'limit': '300'
        }

        all_data = []

        while True:
            data = self._make_request(endpoint, params)

            if not data or len(data) == 0:
                break
            
            reached_start = False
            try:
                for candle in data:
                    candle_ts = int(candle[0])
                    
                    # 过滤：只保留 >= start_time 的数据
                    if candle_ts < start_ms:
                        reached_start = True
                        continue
                    
                    all_data.append({
                        'timestamp': datetime.fromtimestamp(candle_ts / 1000),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5])
                    })
            except (ValueError, IndexError) as e:
                print(f"解析K线数据失败: {e}")
                break

            # 如果已经到达 start_time 之前，停止获取
            if reached_start:
                break
            
            # 检查是否还有更多数据
            if len(data) < 300:
                break
            
            # 更新 after 参数继续往前获取更早的数据
            params['after'] = data[-1][0]
            time.sleep(0.5)
        
        # 按时间升序排列（OKX 返回的是降序）
        all_data.sort(key=lambda x: x['timestamp'])
        
        return all_data

    def get_positions(self) -> List[Dict]:
        """
        获取当前持仓
        """
        endpoint = "/api/v5/account/positions"
        # instType: MARGIN, SWAP, FUTURES, OPTION
        # 这里默认获取所有类型
        params = {}
        
        data = self._make_request(endpoint, params, method='GET')
        
        positions = []
        if data:
            for p in data:
                try:
                    positions.append({
                        'symbol': p['instId'].split('-')[0],
                        'instId': p['instId'],
                        'size': float(p['pos']),  # 持仓数量
                        'entry_price': float(p['avgPx']), # 开仓均价
                        'current_price': float(p.get('lastPx', 0)), # 最新价
                        'unrealized_pnl': float(p['upl']), # 未实现盈亏
                        'pnl_ratio': float(p.get('uplRatio', 0)) * 100, # 盈亏率 %
                        'side': p['posSide'], # long/short/net
                        'type': p['instType'] # SWAP/MARGIN
                    })
                except Exception as e:
                    print(f"解析持仓数据失败: {e}")
                    
        return positions

    def get_balance(self, ccy: str) -> float:
        """
        获取指定币种余额 (用于全仓卖出)
        :param ccy: 币种代码，如 BTC
        :return: 可用余额
        """
        try:
            data = self._make_request("/api/v5/account/balance", {"ccy": ccy})
            if data and len(data) > 0:
                details = data[0].get('details', [])
                for d in details:
                    if d.get('ccy') == ccy:
                        return float(d.get('availbal', 0))
            return 0.0
        except Exception as e:
            # print(f"获取余额失败: {e}")
            return 0.0

    def create_order(self, symbol: str, side: str, amount: float, order_type: str = 'market') -> Optional[Dict]:
        """
        创建订单
        :param symbol: 交易对，如 BTC
        :param side: buy 或 sell
        :param amount: 数量 (卖出时为币的数量，买入时为USDT数量-需注意市价买入单位)
                       注意：OKX市价卖出 sz 是币的数量
        :param order_type: limit 或 market
        :return: 订单结果
        """
        # 格式化交易对: BTC -> BTC-USDT
        inst_id = f"{symbol}-USDT"
        
        params = {
            "instId": inst_id,
            "tdMode": "cash",
            "side": side,
            "ordType": order_type,
            "sz": str(amount)
        }
        
        try:
            # print(f"提交订单: {params}")
            data = self._make_request("/api/v5/trade/order", params, method='POST')
            if data and len(data) > 0:
                return data[0]
            return None
        except Exception as e:
            # print(f"下单失败: {e}")
            return None