"""
趋势分析模块
提供价格缓存和技术分析功能
"""

import os
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', '.cache')


class PriceCache:
    """价格数据缓存管理"""
    
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_path(self, coin: str, data_type: str) -> str:
        return os.path.join(self.cache_dir, f"{coin.lower()}_{data_type}.json")
    
    def is_valid(self, coin: str, data_type: str, max_age_hours: int = 24) -> bool:
        """检查缓存是否有效"""
        path = self._get_cache_path(coin, data_type)
        if not os.path.exists(path):
            return False
        
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        age = datetime.now() - mtime
        return age.total_seconds() < max_age_hours * 3600
    
    def load(self, coin: str, data_type: str) -> Optional[List[Dict]]:
        """加载缓存数据"""
        path = self._get_cache_path(coin, data_type)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def save(self, coin: str, data_type: str, data: List[Dict]):
        """保存数据到缓存"""
        path = self._get_cache_path(coin, data_type)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")


class TechnicalAnalysis:
    """技术分析工具"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.cache = PriceCache()
        self.session = requests.Session()
        self.price_data = {}  # {coin: [{date, price}, ...]}
    
    def fetch_price_history(self, coin: str, days: int = 60) -> List[Dict]:
        """获取历史价格（带缓存）"""
        # 检查缓存
        if self.cache.is_valid(coin, 'price', max_age_hours=6):
            cached = self.cache.load(coin, 'price')
            if cached and len(cached) >= days:
                self.price_data[coin] = cached[-days:]
                return self.price_data[coin]
        
        logger.info(f"获取 {coin} 历史价格...")
        
        url = "https://min-api.cryptocompare.com/data/v2/histoday"
        params = {
            'fsym': coin.upper(),
            'tsym': 'USD',
            'limit': days,
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get('Response') != 'Success':
                logger.error(f"API 错误: {data.get('Message')}")
                return []
            
            records = []
            for item in data.get('Data', {}).get('Data', []):
                if item['close'] > 0:
                    dt = datetime.fromtimestamp(item['time'])
                    records.append({
                        'date': dt.strftime('%Y-%m-%d'),
                        'close': item['close'],
                    })
            
            # 缓存
            self.cache.save(coin, 'price', records)
            self.price_data[coin] = records
            
            return records
            
        except Exception as e:
            logger.error(f"获取 {coin} 价格失败: {e}")
            return []
    
    def calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
        """计算当前 MA"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def calculate_7d_change(self, prices: List[float]) -> Optional[float]:
        """计算7天涨跌幅"""
        if len(prices) < 8:
            return None
        return (prices[-1] - prices[-8]) / prices[-8] * 100
    
    def check_trend_signal(self, coin: str, current_price: float, fg_value: int) -> Dict:
        """
        检查趋势买入信号 (V8 策略)
        
        返回: {
            'valid': bool,
            'score': int,
            'reasons': list,
            'quality': str
        }
        """
        result = {'valid': False, 'score': 0, 'reasons': [], 'quality': 'low'}
        
        trend_config = self.config.get('trend_strategy', {})
        ma_short_period = trend_config.get('ma_short', 7)
        ma_long_period = trend_config.get('ma_long', 30)
        max_fg = trend_config.get('max_fg_value', 70)
        min_7d_change = trend_config.get('min_7d_change', 0)
        
        # 1. 过滤极端贪婪
        if fg_value > max_fg:
            return result
        
        # 获取价格数据
        if coin not in self.price_data:
            self.fetch_price_history(coin, 60)
        
        if coin not in self.price_data or len(self.price_data[coin]) < 30:
            return result
        
        prices = [p['close'] for p in self.price_data[coin]]
        
        # 2. 计算 MA
        ma_short = self.calculate_ma(prices, ma_short_period)
        ma_long = self.calculate_ma(prices, ma_long_period)
        
        if not ma_short or not ma_long:
            return result
        
        # 3. 价格必须高于两条 MA
        if current_price <= ma_short or current_price <= ma_long:
            return result
        
        result['reasons'].append(f"价格>{ma_short:.0f}(MA{ma_short_period})>{ma_long:.0f}(MA{ma_long_period})")
        result['score'] += 2
        
        # 4. 短期 MA 高于长期 MA（金叉）
        if ma_short > ma_long:
            result['score'] += 2
        else:
            return result
        
        # 5. 7天涨幅为正
        change_7d = self.calculate_7d_change(prices)
        if change_7d is None or change_7d < min_7d_change:
            return result
        
        if change_7d >= 10:
            result['reasons'].append(f"📈 强势 7d+{change_7d:.1f}%")
            result['score'] += 3
            result['quality'] = 'high'
        elif change_7d >= 5:
            result['reasons'].append(f"7d+{change_7d:.1f}%")
            result['score'] += 2
        else:
            result['reasons'].append(f"7d+{change_7d:.1f}%")
            result['score'] += 1
        
        # 6. 情绪恢复加分
        if fg_value < 50:
            result['reasons'].append(f"FG={fg_value} (情绪偏低)")
            result['score'] += 1
        
        result['valid'] = result['score'] >= 5
        return result
