"""
情绪分析器
负责获取和分析市场情绪指标
"""

import requests
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """情绪分析器"""
    
    def __init__(self, config: dict, db):
        self.config = config
        self.db = db
        self.session = requests.Session()
    
    def get_fear_greed_index(self) -> Optional[Dict]:
        """
        获取恐慌贪婪指数
        数据源: Alternative.me
        """
        try:
            url = "https://api.alternative.me/fng/?limit=1"
            response = self.session.get(url, timeout=10).json()
            
            data = response['data'][0]
            return {
                'value': int(data['value']),
                'classification': data['value_classification'],
                'timestamp': data['timestamp']
            }
        except Exception as e:
            logger.error(f"获取恐慌指数失败: {e}")
            return None
    
    def analyze_market_sentiment(self, data: dict) -> Dict:
        """
        综合分析市场情绪
        :param data: 市场数据
        :return: 情绪分析结果
        """
        analysis = {
            'overall_sentiment': 'neutral',
            'fear_greed_status': None,
            'funding_status': {},
            'longshort_status': {}
        }
        
        # 恐慌贪婪指数分析
        if data.get('fear_greed'):
            fg_value = data['fear_greed']['value']
            
            if fg_value < 25:
                analysis['overall_sentiment'] = 'extreme_fear'
                analysis['fear_greed_status'] = 'buy_opportunity'
            elif fg_value < 45:
                analysis['overall_sentiment'] = 'fear'
                analysis['fear_greed_status'] = 'cautious_buy'
            elif fg_value > 75:
                analysis['overall_sentiment'] = 'extreme_greed'
                analysis['fear_greed_status'] = 'sell_signal'
            elif fg_value > 55:
                analysis['overall_sentiment'] = 'greed'
                analysis['fear_greed_status'] = 'cautious_sell'
            else:
                analysis['overall_sentiment'] = 'neutral'
                analysis['fear_greed_status'] = 'hold'
        
        # 资金费率分析
        for coin, coin_data in data.get('coins', {}).items():
            funding = coin_data.get('funding_rate')
            if funding is not None:
                if funding < -0.02:
                    analysis['funding_status'][coin] = 'extreme_negative'
                elif funding < 0:
                    analysis['funding_status'][coin] = 'negative'
                elif funding > 0.05:
                    analysis['funding_status'][coin] = 'extreme_positive'
                elif funding > 0.02:
                    analysis['funding_status'][coin] = 'positive'
                else:
                    analysis['funding_status'][coin] = 'neutral'
        
        # 多空比分析
        for coin, coin_data in data.get('coins', {}).items():
            ls = coin_data.get('longshort')
            if ls:
                ratio = ls.get('ratio', 1)
                if ratio < 0.7:
                    analysis['longshort_status'][coin] = 'extreme_short'
                elif ratio < 0.9:
                    analysis['longshort_status'][coin] = 'short_dominated'
                elif ratio > 1.5:
                    analysis['longshort_status'][coin] = 'extreme_long'
                elif ratio > 1.2:
                    analysis['longshort_status'][coin] = 'long_dominated'
                else:
                    analysis['longshort_status'][coin] = 'balanced'
        
        return analysis