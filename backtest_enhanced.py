#!/usr/bin/env python
"""
增强版历史回测模块
特点：
1. 价格数据缓存（避免重复 API 调用）
2. 趋势确认（MA 分析）
3. 波动率分析
4. 更智能的信号生成
"""

import requests
import time
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(__file__), '.cache')


class PriceCache:
    """价格数据缓存管理"""
    
    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, coin: str, data_type: str) -> str:
        return os.path.join(self.cache_dir, f"{coin.lower()}_{data_type}.json")
    
    def is_valid(self, coin: str, data_type: str, max_age_hours: int = 24) -> bool:
        """检查缓存是否有效"""
        path = self._get_cache_path(coin, data_type)
        if not os.path.exists(path):
            return False
        
        # 检查文件修改时间
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        age = datetime.now() - mtime
        return age.total_seconds() < max_age_hours * 3600
    
    def load(self, coin: str, data_type: str) -> Optional[List[Dict]]:
        """加载缓存数据"""
        path = self._get_cache_path(coin, data_type)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"📦 从缓存加载 {coin} {data_type} 数据 ({len(data)} 条)")
                return data
        except Exception as e:
            logger.warning(f"缓存加载失败: {e}")
            return None
    
    def save(self, coin: str, data_type: str, data: List[Dict]):
        """保存数据到缓存"""
        path = self._get_cache_path(coin, data_type)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"💾 已缓存 {coin} {data_type} 数据")
        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")


class TechnicalAnalysis:
    """技术分析工具"""
    
    @staticmethod
    def calculate_ma(prices: List[float], period: int) -> List[Optional[float]]:
        """计算移动平均线"""
        ma = []
        for i in range(len(prices)):
            if i < period - 1:
                ma.append(None)
            else:
                avg = sum(prices[i - period + 1:i + 1]) / period
                ma.append(round(avg, 2))
        return ma
    
    @staticmethod
    def calculate_price_change(prices: List[float], days: int) -> List[Optional[float]]:
        """计算 N 天价格变化率"""
        changes = []
        for i in range(len(prices)):
            if i < days:
                changes.append(None)
            else:
                change = (prices[i] - prices[i - days]) / prices[i - days] * 100
                changes.append(round(change, 2))
        return changes
    
    @staticmethod
    def is_above_ma(price: float, ma: Optional[float]) -> bool:
        """价格是否在 MA 之上"""
        if ma is None:
            return False
        return price > ma
    
    @staticmethod
    def is_recovering(prices: List[float], lookback: int = 3) -> bool:
        """检查价格是否正在恢复（连续上涨）"""
        if len(prices) < lookback + 1:
            return False
        recent = prices[-lookback:]
        for i in range(1, len(recent)):
            if recent[i] <= recent[i-1]:
                return False
        return True


class EnhancedBacktester:
    """增强版回测器"""
    
    def __init__(self, config: dict = None):
        self.config = config or self._default_config()
        self.session = requests.Session()
        self.cache = PriceCache()
        self.ta = TechnicalAnalysis()
        
        # 数据存储
        self.fear_greed_data = []
        self.price_data = {}
        self.signals = []
        self.results = []
        
    def _default_config(self) -> dict:
        return {
            'thresholds': {
                'fear_buy': 25,
                'greed_sell': 75,
            },
            'reversal': {
                'enabled': True,
                'consecutive_periods': 2,
            },
            'ma': {
                'enabled': True,
                'short_period': 7,    # 短期 MA
                'long_period': 30,    # 长期 MA
            },
            'filters': {
                'max_drop_7d': -30,   # 7天最大跌幅限制，超过不入场
                'require_price_recovery': True,  # 要求价格开始恢复
            },
            'coins': ['BTC', 'ETH'],
            'hold_days': [7, 14, 30],
            'use_sell_signal': False,
        }
    
    # ==================== 数据获取 ====================
    
    def fetch_fear_greed_history(self, days: int = 365) -> List[Dict]:
        """获取历史恐慌指数（带缓存）"""
        # 检查缓存
        if self.cache.is_valid('fg', 'index', max_age_hours=12):
            cached = self.cache.load('fg', 'index')
            if cached and len(cached) >= days:
                self.fear_greed_data = cached[-days:]
                return self.fear_greed_data
        
        logger.info(f"正在获取恐慌指数历史数据 (目标: {days} 天)...")
        
        url = "https://api.alternative.me/fng/"
        params = {'limit': 0}
        
        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            records = []
            for item in data.get('data', []):
                timestamp = int(item['timestamp'])
                dt = datetime.fromtimestamp(timestamp)
                records.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'value': int(item['value']),
                    'classification': item['value_classification']
                })
            
            records.sort(key=lambda x: x['date'])
            
            # 缓存全部数据
            self.cache.save('fg', 'index', records)
            
            if days and len(records) > days:
                records = records[-days:]
            
            self.fear_greed_data = records
            logger.info(f"✅ 获取到 {len(records)} 条恐慌指数数据")
            
            return records
            
        except Exception as e:
            logger.error(f"获取恐慌指数失败: {e}")
            return []
    
    def fetch_price_history(self, coin: str, days: int = 365) -> List[Dict]:
        """获取历史价格（带缓存）"""
        # 检查缓存
        if self.cache.is_valid(coin, 'price', max_age_hours=24):
            cached = self.cache.load(coin, 'price')
            if cached and len(cached) >= days:
                self.price_data[coin] = cached[-days:]
                return self.price_data[coin]
        
        logger.info(f"正在获取 {coin} 历史价格...")
        
        url = "https://min-api.cryptocompare.com/data/v2/histoday"
        params = {
            'fsym': coin.upper(),
            'tsym': 'USD',
            'limit': 2000,  # 获取最多数据
        }
        
        try:
            response = self.session.get(url, params=params, timeout=60)
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
                        'open': item['open'],
                        'high': item['high'],
                        'low': item['low'],
                        'close': item['close'],
                        'volume': item['volumeto']
                    })
            
            # 缓存全部数据
            self.cache.save(coin, 'price', records)
            
            if days and len(records) > days:
                records = records[-days:]
            
            self.price_data[coin] = records
            logger.info(f"✅ 获取到 {coin} {len(records)} 条价格数据")
            
            return records
            
        except Exception as e:
            logger.error(f"获取 {coin} 价格失败: {e}")
            return []
    
    def fetch_all_data(self, days: int = 365) -> bool:
        """获取所有数据"""
        logger.info("=" * 60)
        logger.info("开始获取历史数据")
        logger.info("=" * 60)
        
        if not self.fetch_fear_greed_history(days):
            return False
        
        for coin in self.config['coins']:
            self.fetch_price_history(coin, days)
            time.sleep(0.5)
        
        return True
    
    # ==================== 增强信号生成 ====================
    
    def _prepare_price_analysis(self, coin: str) -> Dict:
        """准备价格分析数据"""
        if coin not in self.price_data:
            return {}
        
        prices = [p['close'] for p in self.price_data[coin]]
        dates = [p['date'] for p in self.price_data[coin]]
        
        ma_config = self.config['ma']
        
        return {
            'dates': dates,
            'prices': prices,
            'ma_short': self.ta.calculate_ma(prices, ma_config['short_period']),
            'ma_long': self.ta.calculate_ma(prices, ma_config['long_period']),
            'ma_trend': self.ta.calculate_ma(prices, ma_config.get('trend_period', 200)),
            'change_7d': self.ta.calculate_price_change(prices, 7),
        }
    
    def _get_price_index(self, coin: str, date: str) -> Optional[int]:
        """获取日期对应的价格索引"""
        if coin not in self.price_data:
            return None
        for i, p in enumerate(self.price_data[coin]):
            if p['date'] == date:
                return i
        return None
    
    def _check_buy_conditions(
        self, 
        fg_value: int, 
        fg_values: List[int], 
        fg_idx: int,
        coin: str,
        date: str,
        analysis: Dict
    ) -> Dict:
        """
        V8 策略：趋势突破
        核心理念：只关注价格动能，不强依赖情绪
        
        条件组合：
        1. 价格突破 MA7 和 MA30
        2. 7天涨幅为正
        3. 情绪不极端贪婪（FG<70）
        """
        result = {'valid': False, 'score': 0, 'reasons': [], 'quality': 'low'}
        
        # 过滤极端贪婪（容易追高）
        if fg_value > 70:
            return result
        
        # 获取价格数据
        price_idx = self._get_price_index(coin, date)
        if price_idx is None or not analysis or price_idx < 30:
            return result
        
        price = analysis['prices'][price_idx]
        ma_short = analysis['ma_short'][price_idx]
        ma_long = analysis['ma_long'][price_idx]
        change_7d = analysis['change_7d'][price_idx]
        
        if not ma_short or not ma_long:
            return result
        
        # 1. 价格必须高于两条 MA（上升趋势）
        if price <= ma_short or price <= ma_long:
            return result
        
        result['reasons'].append("价格>MA7>MA30")
        result['score'] += 2
        
        # 2. 短期 MA 高于长期 MA（金叉）
        if ma_short > ma_long:
            result['score'] += 2
        else:
            return result
        
        # 3. 近7天涨幅为正
        if change_7d is None or change_7d < 0:
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
        
        # 4. 情绪在恢复中加分
        if fg_value < 50 and fg_idx >= 3:
            if fg_values[fg_idx] > fg_values[fg_idx-1] > fg_values[fg_idx-2]:
                result['reasons'].append("情绪回升")
                result['score'] += 1
        
        result['valid'] = result['score'] >= 5
        return result
    
    def simulate_signals(self) -> List[Dict]:
        """增强版信号模拟"""
        logger.info("=" * 60)
        logger.info("开始增强信号模拟")
        logger.info("=" * 60)
        
        if not self.fear_greed_data:
            return []
        
        signals = []
        fg_values = [d['value'] for d in self.fear_greed_data]
        
        # 预计算所有币种的技术分析
        coin_analysis = {coin: self._prepare_price_analysis(coin) for coin in self.config['coins']}
        
        for i, fg_data in enumerate(self.fear_greed_data):
            date = fg_data['date']
            fg_value = fg_data['value']
            
            for coin in self.config['coins']:
                analysis = coin_analysis.get(coin, {})
                
                # 检查买入条件
                buy_check = self._check_buy_conditions(
                    fg_value, fg_values, i, coin, date, analysis
                )
                
                if buy_check['valid']:
                    price_idx = self._get_price_index(coin, date)
                    price = analysis['prices'][price_idx] if price_idx and analysis else None
                    
                    if price:
                        signals.append({
                            'date': date,
                            'coin': coin,
                            'type': 'BUY',
                            'fg_value': fg_value,
                            'price': price,
                            'score': buy_check['score'],
                            'reasons': buy_check['reasons']
                        })
        
        self.signals = signals
        logger.info(f"✅ 生成 {len(signals)} 个增强信号")
        
        # 按分数统计
        high_score = sum(1 for s in signals if s['score'] >= 5)
        mid_score = sum(1 for s in signals if 3 <= s['score'] < 5)
        logger.info(f"   高分信号(>=5): {high_score}, 中分信号(3-4): {mid_score}")
        
        return signals
    
    # ==================== 收益计算 ====================
    
    def _get_price_after_days(self, coin: str, date: str, days: int) -> Optional[float]:
        """获取 N 天后的价格"""
        if coin not in self.price_data:
            return None
        
        target_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')
        
        for p in self.price_data[coin]:
            if p['date'] == target_date:
                return p['close']
        return None
    
    def calculate_returns(self) -> List[Dict]:
        """计算收益"""
        logger.info("开始计算收益...")
        
        results = []
        
        for signal in self.signals:
            result = {**signal, 'returns': {}}
            
            for days in self.config['hold_days']:
                future_price = self._get_price_after_days(signal['coin'], signal['date'], days)
                if future_price:
                    ret = (future_price - signal['price']) / signal['price'] * 100
                    result['returns'][f'{days}d'] = round(ret, 2)
            
            results.append(result)
        
        self.results = results
        return results
    
    # ==================== 报告生成 ====================
    
    def generate_report(self) -> Dict:
        """生成报告"""
        if not self.results:
            return {}
        
        report = {
            'period': {
                'start': self.fear_greed_data[0]['date'],
                'end': self.fear_greed_data[-1]['date'],
                'days': len(self.fear_greed_data)
            },
            'signals': {
                'total': len(self.signals),
                'high_score': sum(1 for s in self.signals if s['score'] >= 5),
                'mid_score': sum(1 for s in self.signals if 3 <= s['score'] < 5),
            },
            'performance': {}
        }
        
        # 按分数分组统计
        for score_group, min_score, max_score in [('高分(>=5)', 5, 100), ('中分(3-4)', 3, 5)]:
            group_results = [r for r in self.results if min_score <= r['score'] < max_score]
            
            if not group_results:
                continue
            
            stats = {'count': len(group_results)}
            
            for days in self.config['hold_days']:
                day_key = f'{days}d'
                returns = [r['returns'].get(day_key) for r in group_results if r['returns'].get(day_key) is not None]
                
                if returns:
                    wins = sum(1 for r in returns if r > 0)
                    stats[day_key] = {
                        'avg_return': round(sum(returns) / len(returns), 2),
                        'max_return': round(max(returns), 2),
                        'min_return': round(min(returns), 2),
                        'win_rate': round(wins / len(returns) * 100, 1),
                        'sample_size': len(returns)
                    }
            
            report['performance'][score_group] = stats
        
        self._print_report(report)
        return report
    
    def _print_report(self, report: Dict):
        """打印报告"""
        print("\n" + "=" * 70)
        print("📊 增强版回测报告")
        print("=" * 70)
        
        print(f"\n📅 回测周期: {report['period']['start']} ~ {report['period']['end']} ({report['period']['days']} 天)")
        print(f"📈 信号总数: {report['signals']['total']} (高分: {report['signals']['high_score']}, 中分: {report['signals']['mid_score']})")
        
        print("\n" + "-" * 70)
        print("💰 收益统计（按信号质量分组）")
        print("-" * 70)
        
        for group, stats in report['performance'].items():
            print(f"\n【{group}】共 {stats['count']} 次信号")
            
            for days in self.config['hold_days']:
                day_key = f'{days}d'
                if day_key in stats:
                    s = stats[day_key]
                    emoji = "🟢" if s['win_rate'] >= 55 else ("🟡" if s['win_rate'] >= 45 else "🔴")
                    print(f"  {days}天: 平均 {s['avg_return']:+.2f}% | "
                          f"{emoji} 胜率 {s['win_rate']:.1f}% ({s['sample_size']}样本)")
        
        print("\n" + "=" * 70)
    
    def run(self, days: int = 2000) -> Dict:
        """执行回测"""
        print("\n" + "=" * 70)
        print("🚀 开始增强版回测")
        print("=" * 70)
        print(f"策略配置:")
        print(f"  - 恐慌买入阈值: < {self.config['thresholds']['fear_buy']}")
        print(f"  - 拐点确认: {self.config['reversal']['consecutive_periods']} 期")
        print(f"  - MA 趋势确认: MA{self.config['ma']['short_period']}/MA{self.config['ma']['long_period']}")
        print(f"  - 7天最大跌幅限制: {self.config['filters']['max_drop_7d']}%")
        print("=" * 70 + "\n")
        
        if not self.fetch_all_data(days):
            return {}
        
        self.simulate_signals()
        self.calculate_returns()
        report = self.generate_report()
        
        return report


def main():
    config = {
        'thresholds': {
            'fear_buy': 15,     # 极端恐慌阈值（更严格）
            'greed_sell': 75,
        },
        'reversal': {
            'enabled': True,
            'consecutive_periods': 2,
        },
        'ma': {
            'enabled': True,
            'short_period': 7,
            'long_period': 30,
        },
        'filters': {
            'max_drop_7d': -30,
            'require_price_recovery': True,
        },
        'coins': ['BTC', 'ETH'],
        'hold_days': [7, 14, 30],
        'use_sell_signal': False,
    }
    
    backtester = EnhancedBacktester(config)
    report = backtester.run(days=2000)
    
    if report:
        with open('backtest_enhanced_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("\n📁 报告已保存到 backtest_enhanced_report.json")


if __name__ == '__main__':
    main()
