#!/usr/bin/env python
"""
历史回测模块
使用项目策略对历史数据进行回测
"""

import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HistoricalBacktester:
    """历史回测器"""
    
    def __init__(self, config: dict = None):
        self.config = config or self._default_config()
        self.session = requests.Session()
        
        # 数据存储
        self.fear_greed_data = []  # [{date, value}, ...]
        self.price_data = {}       # {coin: [{date, price}, ...]}
        self.signals = []          # 生成的信号
        self.results = []          # 回测结果
        
    def _default_config(self) -> dict:
        """默认配置"""
        return {
            'thresholds': {
                'fear_buy': 25,
                'greed_sell': 75,
            },
            'reversal': {
                'enabled': True,
                'consecutive_periods': 2,
            },
            'coins': ['BTC', 'ETH'],
            'hold_days': [7, 14, 30],  # 持仓天数
        }
    
    # ==================== 数据获取 ====================
    
    def fetch_fear_greed_history(self, days: int = 365) -> List[Dict]:
        """
        获取历史恐慌指数
        数据源: alternative.me (limit=0 获取全部)
        """
        logger.info(f"正在获取恐慌指数历史数据 (目标: {days} 天)...")
        
        url = "https://api.alternative.me/fng/"
        params = {'limit': 0}  # 0 = 获取全部历史
        
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
                    'datetime': dt,
                    'value': int(item['value']),
                    'classification': item['value_classification']
                })
            
            # 按日期排序（从旧到新）
            records.sort(key=lambda x: x['date'])
            
            # 限制天数
            if days and len(records) > days:
                records = records[-days:]
            
            self.fear_greed_data = records
            logger.info(f"✅ 获取到 {len(records)} 条恐慌指数数据")
            logger.info(f"   日期范围: {records[0]['date']} ~ {records[-1]['date']}")
            
            return records
            
        except Exception as e:
            logger.error(f"获取恐慌指数失败: {e}")
            return []
    
    def fetch_price_history(self, coin: str, days: int = 365) -> List[Dict]:
        """
        获取历史价格
        数据源: CryptoCompare (免费 API，无需认证)
        """
        logger.info(f"正在获取 {coin} 历史价格 (目标: {days} 天)...")
        
        url = "https://min-api.cryptocompare.com/data/v2/histoday"
        params = {
            'fsym': coin.upper(),
            'tsym': 'USD',
            'limit': days,
        }
        
        try:
            response = self.session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if data.get('Response') != 'Success':
                logger.error(f"CryptoCompare API 错误: {data.get('Message')}")
                return []
            
            records = []
            for item in data.get('Data', {}).get('Data', []):
                timestamp = item['time']
                dt = datetime.fromtimestamp(timestamp)
                records.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'datetime': dt,
                    'price': item['close']  # 使用收盘价
                })
            
            # 过滤掉价格为0的数据
            records = [r for r in records if r['price'] > 0]
            
            self.price_data[coin] = records
            logger.info(f"✅ 获取到 {coin} {len(records)} 条价格数据")
            if records:
                logger.info(f"   日期范围: {records[0]['date']} ~ {records[-1]['date']}")
            
            return records
            
        except Exception as e:
            logger.error(f"获取 {coin} 价格失败: {e}")
            return []
    
    def fetch_all_data(self, days: int = 365) -> bool:
        """获取所有必需数据"""
        logger.info("=" * 60)
        logger.info("开始获取历史数据")
        logger.info("=" * 60)
        
        # 获取恐慌指数
        if not self.fetch_fear_greed_history(days):
            return False
        
        # 获取各币种价格
        for coin in self.config['coins']:
            self.fetch_price_history(coin, days)
            time.sleep(1.5)  # CoinGecko 限流
        
        return True
    
    # ==================== 信号模拟 ====================
    
    def _check_reversal(self, fg_values: List[int], current_idx: int, direction: str) -> bool:
        """
        检查拐点
        direction: 'up' (恐慌反转) 或 'down' (贪婪反转)
        """
        if not self.config['reversal']['enabled']:
            return False
        
        periods = self.config['reversal']['consecutive_periods']
        if current_idx < periods:
            return False
        
        # 获取检查范围
        check_values = fg_values[current_idx - periods:current_idx + 1]
        
        if direction == 'up':
            # 恐慌反转：需要连续上升
            for i in range(1, len(check_values)):
                if check_values[i] <= check_values[i-1]:
                    return False
            return True
        else:
            # 贪婪反转：需要连续下降
            for i in range(1, len(check_values)):
                if check_values[i] >= check_values[i-1]:
                    return False
            return True
    
    def simulate_signals(self) -> List[Dict]:
        """模拟生成交易信号"""
        logger.info("=" * 60)
        logger.info("开始模拟信号生成")
        logger.info("=" * 60)
        
        if not self.fear_greed_data:
            logger.error("无恐慌指数数据")
            return []
        
        signals = []
        fg_values = [d['value'] for d in self.fear_greed_data]
        thresholds = self.config['thresholds']
        
        for i, fg_data in enumerate(self.fear_greed_data):
            date = fg_data['date']
            fg_value = fg_data['value']
            
            # 买入信号检测
            if fg_value < thresholds['fear_buy']:
                if self._check_reversal(fg_values, i, 'up'):
                    for coin in self.config['coins']:
                        price = self._get_price_on_date(coin, date)
                        if price:
                            signals.append({
                                'date': date,
                                'coin': coin,
                                'type': 'BUY',
                                'fg_value': fg_value,
                                'price': price,
                                'reason': f'恐慌拐点确认 (FG={fg_value})'
                            })
            
            # 卖出信号检测（可通过配置禁用）
            elif fg_value > thresholds['greed_sell']:
                if self.config.get('use_sell_signal', True):
                    if self._check_reversal(fg_values, i, 'down'):
                        for coin in self.config['coins']:
                            price = self._get_price_on_date(coin, date)
                            if price:
                                signals.append({
                                    'date': date,
                                    'coin': coin,
                                    'type': 'SELL',
                                    'fg_value': fg_value,
                                    'price': price,
                                    'reason': f'贪婪拐点确认 (FG={fg_value})'
                                })
        
        self.signals = signals
        logger.info(f"✅ 生成 {len(signals)} 个信号")
        
        # 统计
        buy_count = sum(1 for s in signals if s['type'] == 'BUY')
        sell_count = sum(1 for s in signals if s['type'] == 'SELL')
        logger.info(f"   买入信号: {buy_count}, 卖出信号: {sell_count}")
        
        return signals
    
    def _get_price_on_date(self, coin: str, date: str) -> Optional[float]:
        """获取指定日期的价格"""
        if coin not in self.price_data:
            return None
        
        for p in self.price_data[coin]:
            if p['date'] == date:
                return p['price']
        return None
    
    def _get_price_after_days(self, coin: str, date: str, days: int) -> Optional[float]:
        """获取 N 天后的价格"""
        if coin not in self.price_data:
            return None
        
        target_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')
        
        for p in self.price_data[coin]:
            if p['date'] == target_date:
                return p['price']
        return None
    
    # ==================== 收益计算 ====================
    
    def calculate_returns(self) -> List[Dict]:
        """计算每个信号的收益"""
        logger.info("=" * 60)
        logger.info("开始计算收益")
        logger.info("=" * 60)
        
        results = []
        hold_days = self.config['hold_days']
        
        for signal in self.signals:
            result = {
                **signal,
                'returns': {}
            }
            
            for days in hold_days:
                future_price = self._get_price_after_days(signal['coin'], signal['date'], days)
                if future_price:
                    if signal['type'] == 'BUY':
                        ret = (future_price - signal['price']) / signal['price'] * 100
                    else:  # SELL
                        ret = (signal['price'] - future_price) / signal['price'] * 100
                    result['returns'][f'{days}d'] = round(ret, 2)
                else:
                    result['returns'][f'{days}d'] = None
            
            results.append(result)
        
        self.results = results
        logger.info(f"✅ 计算完成，{len(results)} 条结果")
        
        return results
    
    # ==================== 报告生成 ====================
    
    def generate_report(self) -> Dict:
        """生成回测报告"""
        logger.info("=" * 60)
        logger.info("生成回测报告")
        logger.info("=" * 60)
        
        if not self.results:
            return {}
        
        report = {
            'period': {
                'start': self.fear_greed_data[0]['date'] if self.fear_greed_data else None,
                'end': self.fear_greed_data[-1]['date'] if self.fear_greed_data else None,
                'days': len(self.fear_greed_data)
            },
            'signals': {
                'total': len(self.signals),
                'buy': sum(1 for s in self.signals if s['type'] == 'BUY'),
                'sell': sum(1 for s in self.signals if s['type'] == 'SELL')
            },
            'performance': {}
        }
        
        # 按币种和类型统计
        for coin in self.config['coins']:
            coin_results = [r for r in self.results if r['coin'] == coin]
            
            for signal_type in ['BUY', 'SELL']:
                type_results = [r for r in coin_results if r['type'] == signal_type]
                if not type_results:
                    continue
                
                key = f"{coin}_{signal_type}"
                stats = {'count': len(type_results)}
                
                for days in self.config['hold_days']:
                    day_key = f'{days}d'
                    returns = [r['returns'].get(day_key) for r in type_results if r['returns'].get(day_key) is not None]
                    
                    if returns:
                        wins = sum(1 for r in returns if r > 0)
                        stats[day_key] = {
                            'avg_return': round(sum(returns) / len(returns), 2),
                            'max_return': round(max(returns), 2),
                            'min_return': round(min(returns), 2),
                            'win_rate': round(wins / len(returns) * 100, 1),
                            'sample_size': len(returns)
                        }
                
                report['performance'][key] = stats
        
        self._print_report(report)
        return report
    
    def _print_report(self, report: Dict):
        """打印报告"""
        print("\n" + "=" * 70)
        print("📊 历史回测报告")
        print("=" * 70)
        
        print(f"\n📅 回测周期: {report['period']['start']} ~ {report['period']['end']} ({report['period']['days']} 天)")
        print(f"📈 信号总数: {report['signals']['total']} (买入: {report['signals']['buy']}, 卖出: {report['signals']['sell']})")
        
        print("\n" + "-" * 70)
        print("💰 收益统计")
        print("-" * 70)
        
        for key, stats in report['performance'].items():
            print(f"\n【{key}】共 {stats['count']} 次信号")
            
            for days in self.config['hold_days']:
                day_key = f'{days}d'
                if day_key in stats:
                    s = stats[day_key]
                    win_emoji = "🟢" if s['win_rate'] >= 50 else "🔴"
                    print(f"  {days}天持有: 平均 {s['avg_return']:+.2f}% | "
                          f"最高 {s['max_return']:+.2f}% | 最低 {s['min_return']:+.2f}% | "
                          f"{win_emoji} 胜率 {s['win_rate']:.1f}% ({s['sample_size']}样本)")
        
        print("\n" + "=" * 70)
    
    # ==================== 主流程 ====================
    
    def run(self, days: int = 365) -> Dict:
        """执行完整回测"""
        print("\n" + "=" * 70)
        print("🚀 开始历史回测")
        print("=" * 70)
        print(f"策略配置:")
        print(f"  - 恐慌买入阈值: < {self.config['thresholds']['fear_buy']}")
        print(f"  - 贪婪卖出阈值: > {self.config['thresholds']['greed_sell']}")
        print(f"  - 拐点确认: {self.config['reversal']['enabled']} (需连续 {self.config['reversal']['consecutive_periods']} 次)")
        print(f"  - 回测币种: {', '.join(self.config['coins'])}")
        print(f"  - 持仓周期: {self.config['hold_days']} 天")
        print("=" * 70 + "\n")
        
        # 1. 获取数据
        if not self.fetch_all_data(days):
            logger.error("数据获取失败，回测终止")
            return {}
        
        # 2. 模拟信号
        self.simulate_signals()
        
        # 3. 计算收益
        self.calculate_returns()
        
        # 4. 生成报告
        report = self.generate_report()
        
        return report


def main():
    """主函数"""
    # 平衡策略配置（避免过拟合，同时保证足够信号）
    config = {
        'thresholds': {
            'fear_buy': 25,     # 标准恐慌阈值
            'greed_sell': 75,   # 标准贪婪阈值（但禁用卖出）
        },
        'reversal': {
            'enabled': True,
            'consecutive_periods': 2,  # 2期确认，平衡信号数量与准确性
        },
        'coins': ['BTC', 'ETH'],
        'hold_days': [7, 14, 30],
        'use_sell_signal': False,  # 禁用卖出信号（关键优化）
    }
    
    backtester = HistoricalBacktester(config)
    report = backtester.run(days=2000)  # 约 5.5 年历史数据
    
    # 保存结果
    if report:
        with open('backtest_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("\n📁 报告已保存到 backtest_report.json")


if __name__ == '__main__':
    main()
