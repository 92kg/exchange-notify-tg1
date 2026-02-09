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
import statistics
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
        
        # 使用可配置的动量阈值（避免硬编码过拟合）
        ma_config = self.config.get('ma', {})
        high_momentum = ma_config.get('high_momentum_7d', 10)
        medium_momentum = ma_config.get('medium_momentum_7d', 5)
        score_threshold = ma_config.get('score_threshold', 5)
        
        if change_7d >= high_momentum:
            result['reasons'].append(f"📈 强势 7d+{change_7d:.1f}%")
            result['score'] += 3
            result['quality'] = 'high'
        elif change_7d >= medium_momentum:
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
        
        result['valid'] = result['score'] >= score_threshold
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
                
                # 注意：不再生成主动卖出信号
                # 回测证明情绪卖出信号无效（正确率仅38%）
                # 实际交易中应使用止损线（如-15%）代替
        
        self.signals = signals
        
        # 统计
        buy_signals = [s for s in signals if s['type'] == 'BUY']
        sell_signals = [s for s in signals if s['type'] == 'SELL']
        logger.info(f"✅ 生成 {len(signals)} 个信号 (买入: {len(buy_signals)}, 卖出: {len(sell_signals)})")
        
        # 按分数统计买入信号
        high_score = sum(1 for s in buy_signals if s['score'] >= 5)
        mid_score = sum(1 for s in buy_signals if 3 <= s['score'] < 5)
        logger.info(f"   买入 - 高分(>=5): {high_score}, 中分(3-4): {mid_score}")
        
        return signals
    
    def _check_sell_conditions(
        self,
        fg_value: int,
        fg_values: List[int],
        fg_idx: int,
        coin: str,
        date: str,
        analysis: Dict
    ) -> Dict:
        """
        卖出信号检测 - 纯情绪版
        核心理念：贪婪见顶 + 情绪反转
        不依赖技术指标，只看市场情绪
        """
        result = {'valid': False, 'score': 0, 'reasons': []}
        
        # 条件 1: 当前处于贪婪区域 (FG > 60)
        if fg_value < 60:
            return result
        
        result['reasons'].append(f"FG={fg_value} (贪婪)")
        result['score'] += 1
        
        # 条件 2: 情绪从高位开始下跌
        if fg_idx >= 3:
            # 检查过去3天的最高点
            recent = fg_values[fg_idx-3:fg_idx+1]
            max_recent = max(recent[:-1])  # 不含今天
            
            # 曾经达到极度贪婪 (>75) 且现在开始下跌
            if max_recent >= 75 and fg_value < max_recent - 5:
                result['reasons'].append(f"情绪拐点 {max_recent}->{fg_value}")
                result['score'] += 3
            # 曾经达到贪婪 (>65) 且连续下跌
            elif max_recent >= 65:
                if all(recent[i] > recent[i+1] for i in range(len(recent)-1)):
                    result['reasons'].append(f"连续下跌 {recent[0]}->{fg_value}")
                    result['score'] += 2
        
        # 条件 3: 7天前也是贪婪（持续贪婪后见顶）
        if fg_idx >= 7:
            fg_7d_ago = fg_values[fg_idx - 7]
            if fg_7d_ago >= 55:
                result['reasons'].append("持续贪婪期")
                result['score'] += 1
        
        # 分数 >= 3 才生成卖出信号
        result['valid'] = result['score'] >= 3
        return result
    
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
        """计算收益（含动态止损分析 V2 + 手续费）"""
        logger.info("开始计算收益...")
        
        # 获取风控配置 (支持 trailing stop)
        risk_config = self.config.get('risk', {})
        stop_type = risk_config.get('stop_loss_type', 'trailing') # fixed / trailing
        stop_pct = risk_config.get('stop_loss_pct', -15)          # 止损比例
        
        # 获取手续费配置 (单边费率，双向需要 x2)
        fee_rate = self.config.get('fee_rate', 0.1)  # 默认 0.1%
        slippage = self.config.get('slippage', 0.1)  # 默认 0.1% 滑点
        execution_delay = self.config.get('execution_delay', 0)  # 执行延迟成本
        round_trip_fee = fee_rate * 2  # 买入 + 卖出
        total_cost = round_trip_fee + slippage + execution_delay  # 总交易成本
        
        results = []
        
        for signal in self.signals:
            if signal['type'] != 'BUY':
                continue
                
            entry_price = signal['price']
            result = {
                **signal, 
                'returns': {}, 
                'max_drawdown': 0, 
                'exit_reason': 'hold', # hold / stop_loss / profit
                'exit_price': 0,
                'exit_day': 0,
                'fee_deducted': round_trip_fee  # 记录扣除的手续费
            }
            
            # 模拟持仓过程
            max_price = entry_price
            current_stop_price = 0
            
            # 初始化止损线
            if stop_type == 'trailing':
                current_stop_price = entry_price * (1 + stop_pct / 100)
            else:
                current_stop_price = entry_price * (1 + stop_pct / 100)
            
            is_stopped = False
            
            # 遍历持有期（最大30天）
            max_hold_days = max(self.config['hold_days'])
            
            for day in range(1, max_hold_days + 1):
                day_price = self._get_price_after_days(signal['coin'], signal['date'], day)
                if not day_price:
                    continue
                
                # 1. 更新最高价
                if day_price > max_price:
                    max_price = day_price
                    # 如果是移动止损，抬高止损线
                    if stop_type == 'trailing':
                        new_stop = max_price * (1 + stop_pct / 100)
                        current_stop_price = max(current_stop_price, new_stop)
                
                # 2. 检查由最高点回撤幅度（用于统计最大回撤）
                drawdown_from_max = (day_price - max_price) / max_price * 100
                result['max_drawdown'] = min(result['max_drawdown'], drawdown_from_max)
                
                # 3. 检查是否触及止损线
                if day_price <= current_stop_price:
                    is_stopped = True
                    result['exit_reason'] = 'stop_loss'
                    result['exit_price'] = current_stop_price # 近似以止损价成交
                    result['exit_day'] = day
                    break
                
                # 记录特定天数的持有收益（如果还没止损）- 扣除交易成本
                if day in self.config['hold_days']:
                    gross_ret = (day_price - entry_price) / entry_price * 100
                    net_ret = gross_ret - total_cost  # 扣除手续费+滑点
                    result['returns'][f'{day}d'] = round(net_ret, 2)
                    result['returns'][f'{day}d_gross'] = round(gross_ret, 2)  # 保留毛收益供对比
            
            # 如果持有期结束还没止损，则以最后一天价格平仓
            if not is_stopped:
                final_price = self._get_price_after_days(signal['coin'], signal['date'], max_hold_days)
                if final_price:
                    result['exit_price'] = final_price
                    result['exit_day'] = max_hold_days
            
            # 计算最终交易收益（基于退出价格）- 扣除交易成本
            gross_return = (result['exit_price'] - entry_price) / entry_price * 100
            net_return = gross_return - total_cost  # 扣除手续费+滑点
            result['final_return'] = round(net_return, 2)
            result['final_return_gross'] = round(gross_return, 2)  # 保留毛收益供对比
            result['total_cost'] = total_cost  # 记录总成本
            
            results.append(result)
        
        self.results = results
        logger.info(f"✅ 交易成本: 手续费 {round_trip_fee}% + 滑点 {slippage}% = 总计 {total_cost}%")
        return results
    
    # ==================== 报告生成 ====================
    
    def generate_report(self) -> Dict:
        """生成报告 (V2: 基于真实模拟结果 + 手续费)"""
        if not self.results:
            return {}
        
        buy_results = self.results
        
        # 1. 基础统计
        total_signals = len(buy_results)
        hit_stop = sum(1 for r in buy_results if r.get('exit_reason') == 'stop_loss')
        avg_drawdown = statistics.mean([r.get('max_drawdown', 0) for r in buy_results]) if buy_results else 0
        
        # 2. 收益统计 (基于 final_return - 已扣手续费)
        final_returns = [r.get('final_return', 0) for r in buy_results]
        final_returns_gross = [r.get('final_return_gross', 0) for r in buy_results]
        
        win_count = sum(1 for r in final_returns if r > 0)
        win_rate = win_count / total_signals * 100 if total_signals > 0 else 0
        avg_return = statistics.mean(final_returns) if final_returns else 0
        avg_return_gross = statistics.mean(final_returns_gross) if final_returns_gross else 0
        total_return = sum(final_returns)
        total_return_gross = sum(final_returns_gross)
        
        # 3. 交易成本影响 (手续费 + 滑点 + 执行延迟)
        fee_rate = self.config.get('fee_rate', 0.1)
        slippage = self.config.get('slippage', 0.1)
        execution_delay = self.config.get('execution_delay', 0)
        round_trip_fee = fee_rate * 2
        total_cost_per_trade = round_trip_fee + slippage + execution_delay
        total_trading_cost = total_cost_per_trade * total_signals  # 总交易成本
        
        # 4. 风险配置回顾
        risk_config = self.config.get('risk', {})
        stop_desc = f"{risk_config.get('stop_loss_type')} ({risk_config.get('stop_loss_pct')}%)"

        report = {
            'period': {
                'start': self.fear_greed_data[0]['date'],
                'end': self.fear_greed_data[-1]['date'],
                'days': len(self.fear_greed_data)
            },
            'signals': {
                'total': total_signals,
                'stopped': hit_stop,
                'stop_rate': round(hit_stop / total_signals * 100, 1) if total_signals else 0
            },
            'performance': {
                'avg_return': round(avg_return, 2),           # 净收益（扣手续费+滑点）
                'avg_return_gross': round(avg_return_gross, 2), # 毛收益
                'total_return': round(total_return, 2),
                'total_return_gross': round(total_return_gross, 2),
                'win_rate': round(win_rate, 1),
                'max_return': round(max(final_returns), 2) if final_returns else 0,
                'min_return': round(min(final_returns), 2) if final_returns else 0,
            },
            'costs': {
                'fee_rate': fee_rate,
                'round_trip_fee': round_trip_fee,
                'slippage': slippage,
                'execution_delay': execution_delay,
                'total_per_trade': total_cost_per_trade,
                'total_cost': round(total_trading_cost, 2),
                'cost_drag_pct': round(total_trading_cost / total_return_gross * 100, 1) if total_return_gross > 0 else 0
            },
            'risk': {
                'stop_loss_config': stop_desc,
                'avg_max_drawdown': round(avg_drawdown, 2),
            }
        }
        
        self._print_report(report)
        return report
    
    def _print_report(self, report: Dict):
        """打印报告"""
        print("\n" + "=" * 70)
        print("📊 增强版回测报告 (V8 趋势策略 + 动态止损 + 手续费)")
        print("=" * 70)
        
        print(f"\n📅 回测周期: {report['period']['start']} ~ {report['period']['end']} ({report['period']['days']} 天)")
        print(f"📈 信号统计: 共 {report['signals']['total']} 次买入")
        print(f"🛑 止损触发: {report['signals']['stopped']} 次 (触发率 {report['signals']['stop_rate']}%)")
        
        print("\n" + "-" * 70)
        print("💰 收益表现 (模拟持仓)")
        print("-" * 70)
        p = report['performance']
        c = report.get('costs', {})
        
        # 显示毛收益 vs 净收益对比
        print(f"  平均单次收益 (毛): {p.get('avg_return_gross', p['avg_return']):+.2f}%")
        print(f"  平均单次收益 (净): {p['avg_return']:+.2f}%  ← 扣除交易成本")
        print(f"  累计名义收益 (毛): {p.get('total_return_gross', p['total_return']):+.2f}%")
        print(f"  累计名义收益 (净): {p['total_return']:+.2f}%  ← 扣除交易成本")
        print(f"  胜率            : {p['win_rate']}%")
        print(f"  最佳/最差        : {p['max_return']:+.2f}% / {p['min_return']:+.2f}%")
        
        # 交易成本统计
        if c:
            print("\n" + "-" * 70)
            print("💸 交易成本分析")
            print("-" * 70)
            print(f"  双向手续费  : {c.get('round_trip_fee', 0.2)}%")
            print(f"  滑点成本    : {c.get('slippage', 0.1)}%")
            print(f"  执行延迟成本: {c.get('execution_delay', 0)}%")
            print(f"  单次总成本  : {c.get('total_per_trade', 0.3)}%")
            print(f"  累计成本    : {c.get('total_cost', 0):.2f}%")
            if c.get('cost_drag_pct', 0) > 0:
                print(f"  成本拖累    : {c['cost_drag_pct']:.1f}% (占毛收益)")
        
        print("\n" + "-" * 70)
        print("🛡️ 风险分析")
        print("-" * 70)
        print(f"  止损配置: {report['risk']['stop_loss_config']}")
        print(f"  平均最大回撤: {report['risk']['avg_max_drawdown']:.2f}%")
        print("\n" + "=" * 70)
    
    def _calc_performance(self, results: List[Dict], label: str, invert: bool = False) -> Dict:
        # Deprecated by new logic
        return {}
        print("📥 买入信号效果")
        print("-" * 70)
        buy_stats = report.get('buy_performance', {})
        if buy_stats.get('count', 0) > 0:
            for days in self.config['hold_days']:
                day_key = f'{days}d'
                if day_key in buy_stats:
                    s = buy_stats[day_key]
                    emoji = "🟢" if s['win_rate'] >= 55 else ("🟡" if s['win_rate'] >= 45 else "🔴")
                    print(f"  {days}天: 平均 {s['avg_return']:+.2f}% | "
                          f"{emoji} 胜率 {s['win_rate']:.1f}% ({s['sample_size']}样本)")
        
        # 风险统计
        print("\n" + "-" * 70)
        print("⚠️ 风险统计（止损线: {}%）".format(report['risk']['stop_loss_line']))
        print("-" * 70)
        risk = report['risk']
        print(f"  触发止损: {risk['hit_stop_loss']} 次 ({risk['hit_rate']:.1f}%)")
        print(f"  平均最大回撤: {risk['avg_max_drawdown']:.2f}%")
        
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
        
        # 检查是否启用样本外验证
        validate_oos = self.config.get('validate_out_of_sample', False)
        train_ratio = self.config.get('train_test_split', 0.7)
        
        if validate_oos and self.results:
            report = self._run_train_test_validation(train_ratio)
        else:
            report = self.generate_report()
        
        return report
    
    def _run_train_test_validation(self, train_ratio: float = 0.7) -> Dict:
        """执行训练集/测试集分离验证（防过拟合）"""
        print("\n" + "=" * 70)
        print("🔬 样本外验证 (Out-of-Sample Validation)")
        print("=" * 70)
        
        if not self.results:
            return {}
        
        # 按日期排序
        sorted_results = sorted(self.results, key=lambda x: x['date'])
        
        # 分割点
        split_idx = int(len(sorted_results) * train_ratio)
        train_results = sorted_results[:split_idx]
        test_results = sorted_results[split_idx:]
        
        train_start = train_results[0]['date'] if train_results else 'N/A'
        train_end = train_results[-1]['date'] if train_results else 'N/A'
        test_start = test_results[0]['date'] if test_results else 'N/A'
        test_end = test_results[-1]['date'] if test_results else 'N/A'
        
        print(f"\n📊 数据分割:")
        print(f"  训练集: {len(train_results)} 信号 ({train_start} ~ {train_end})")
        print(f"  测试集: {len(test_results)} 信号 ({test_start} ~ {test_end})")
        
        # 计算训练集统计
        train_stats = self._calculate_subset_stats(train_results, "训练集 (In-Sample)")
        
        # 计算测试集统计
        test_stats = self._calculate_subset_stats(test_results, "测试集 (Out-of-Sample)")
        
        # 对比分析
        print("\n" + "-" * 70)
        print("📈 训练集 vs 测试集 对比")
        print("-" * 70)
        
        train_return = train_stats.get('avg_return', 0)
        test_return = test_stats.get('avg_return', 0)
        train_winrate = train_stats.get('win_rate', 0)
        test_winrate = test_stats.get('win_rate', 0)
        
        degradation = train_return - test_return
        winrate_drop = train_winrate - test_winrate
        
        print(f"  {'指标':<15} {'训练集':>12} {'测试集':>12} {'差异':>12}")
        print(f"  {'-'*51}")
        print(f"  {'平均收益':<15} {train_return:>+11.2f}% {test_return:>+11.2f}% {-degradation:>+11.2f}%")
        print(f"  {'胜率':<15} {train_winrate:>11.1f}% {test_winrate:>11.1f}% {-winrate_drop:>+11.1f}%")
        
        # 过拟合警告
        if degradation > 2.0:
            print("\n  ⚠️  警告: 测试集收益显著低于训练集，可能存在过拟合!")
        elif degradation > 1.0:
            print("\n  ⚡ 注意: 测试集表现略逊于训练集，建议关注")
        else:
            print("\n  ✅ 测试集表现稳健，策略泛化能力良好")
        
        if winrate_drop > 10:
            print("  ⚠️  警告: 胜率下降超过10%，策略可能过度拟合历史数据!")
        
        print("\n" + "=" * 70)
        
        # 返回完整报告
        report = self.generate_report()
        report['validation'] = {
            'enabled': True,
            'train_ratio': train_ratio,
            'train': {
                'count': len(train_results),
                'period': f"{train_start} ~ {train_end}",
                'avg_return': round(train_return, 2),
                'win_rate': round(train_winrate, 1)
            },
            'test': {
                'count': len(test_results),
                'period': f"{test_start} ~ {test_end}",
                'avg_return': round(test_return, 2),
                'win_rate': round(test_winrate, 1)
            },
            'degradation': round(degradation, 2),
            'winrate_drop': round(winrate_drop, 1),
            'overfitting_risk': 'HIGH' if degradation > 2.0 else ('MEDIUM' if degradation > 1.0 else 'LOW')
        }
        
        return report
    
    def _calculate_subset_stats(self, results: List[Dict], label: str) -> Dict:
        """计算子集统计"""
        if not results:
            return {}
        
        final_returns = [r.get('final_return', 0) for r in results]
        win_count = sum(1 for r in final_returns if r > 0)
        total = len(results)
        
        stats = {
            'count': total,
            'avg_return': statistics.mean(final_returns) if final_returns else 0,
            'total_return': sum(final_returns),
            'win_rate': win_count / total * 100 if total > 0 else 0,
            'max_return': max(final_returns) if final_returns else 0,
            'min_return': min(final_returns) if final_returns else 0,
        }
        
        print(f"\n📊 {label}:")
        print(f"   信号数: {stats['count']}")
        print(f"   平均收益: {stats['avg_return']:+.2f}%")
        print(f"   胜率: {stats['win_rate']:.1f}%")
        
        return stats


def main():
    import yaml
    
    # Load config from file
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            file_config = yaml.safe_load(f)
            
        print("✅ 已加载 config.yaml")
        
        # Extract relevant sections for backtester
        config = {
            'thresholds': file_config.get('thresholds', {}),
            'reversal': file_config.get('reversal', {}),
            'ma': file_config.get('trend_strategy', {}), # Map trend_strategy to ma
            'filters': {'max_drop_7d': -30, 'require_price_recovery': True}, # Keep defaults for internal filters
            'coins': [c['symbol'] for c in file_config.get('coins', []) if c.get('enabled')],
            'hold_days': file_config.get('backtest', {}).get('profit_days', [7, 14, 30]),
            'use_sell_signal': file_config.get('strategy', {}).get('use_sell_signal', False),
            'risk': file_config.get('risk', {'stop_loss_type': 'trailing', 'stop_loss_pct': -15}),
            'position': file_config.get('position', {}),
            'fee_rate': file_config.get('backtest', {}).get('fee_rate', 0.1),  # 手续费配置
            'slippage': file_config.get('backtest', {}).get('slippage', 0.1),  # 滑点配置
            'execution_delay': file_config.get('backtest', {}).get('execution_delay', 0),  # 执行延迟成本
            'train_test_split': file_config.get('backtest', {}).get('train_test_split', 0.7),  # 训练/测试分割比例
            'validate_out_of_sample': file_config.get('backtest', {}).get('validate_out_of_sample', False),  # 是否启用样本外验证
        }
        
        # Map MA config keys if needed (trend_strategy uses ma_short/ma_long)
        if 'ma_short' in config['ma']:
            config['ma']['short_period'] = config['ma']['ma_short']
        if 'ma_long' in config['ma']:
            config['ma']['long_period'] = config['ma']['ma_long']
        config['ma']['enabled'] = True
            
    except Exception as e:
        print(f"⚠️ 加载 config.yaml 失败: {e}, 使用默认配置")
        config = {
            'thresholds': {'fear_buy': 20, 'greed_sell': 75},
            'reversal': {'enabled': True, 'consecutive_periods': 2},
            'ma': {'enabled': True, 'short_period': 7, 'long_period': 30},
            'filters': {'max_drop_7d': -30, 'require_price_recovery': True},
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


def optimize_stop_loss():
    """优化止损参数"""
    print("\n" + "=" * 70)
    print("🔍 止损参数优化回测")
    print("=" * 70)
    
    config = {
        'thresholds': {'fear_buy': 15, 'greed_sell': 75},
        'reversal': {'enabled': True, 'consecutive_periods': 2},
        'ma': {'enabled': True, 'short_period': 7, 'long_period': 30},
        'filters': {'max_drop_7d': -30, 'require_price_recovery': True},
        'coins': ['BTC', 'ETH'],
        'hold_days': [7, 14, 30],
    }
    
    backtester = EnhancedBacktester(config)
    
    # 获取数据
    if not backtester.fetch_all_data(2000):
        return
    
    backtester.simulate_signals()
    
    # 测试不同止损比例
    stop_levels = [-5, -8, -10, -12, -15, -18, -20, -25]
    
    results = []
    
    for stop_loss in stop_levels:
        backtester.config['stop_loss'] = stop_loss
        backtester.calculate_returns()
        
        # 统计
        hit_count = sum(1 for r in backtester.results if r.get('hit_stop_loss', False))
        hit_rate = hit_count / len(backtester.results) * 100 if backtester.results else 0
        
        # 计算如果止损后不持有的收益
        total_return = 0
        count = 0
        for r in backtester.results:
            ret_30d = r['returns'].get('30d')
            if ret_30d is not None:
                if r.get('hit_stop_loss'):
                    # 止损执行，收益为止损线
                    total_return += stop_loss
                else:
                    total_return += ret_30d
                count += 1
        
        avg_return = total_return / count if count else 0
        
        results.append({
            'stop_loss': stop_loss,
            'hit_rate': round(hit_rate, 1),
            'avg_return_with_stop': round(avg_return, 2),
        })
    
    # 打印结果
    print("\n" + "-" * 70)
    print("📊 固定止损测试结果 (30天持有期)")
    print("-" * 70)
    print(f"{'止损线':>10} | {'触发率':>10} | {'平均收益(含止损)':>20}")
    print("-" * 50)
    
    best = None
    best_return = -999
    
    for r in results:
        print(f"{r['stop_loss']:>10}% | {r['hit_rate']:>9}% | {r['avg_return_with_stop']:>19}%")
        if r['avg_return_with_stop'] > best_return:
            best_return = r['avg_return_with_stop']
            best = r
    
    print("-" * 50)
    print(f"✅ 最佳止损线: {best['stop_loss']}% (收益 {best['avg_return_with_stop']}%)")
    
    # 测试动态止损（Trailing Stop）
    print("\n" + "-" * 70)
    print("📊 动态止损测试 (Trailing Stop)")
    print("-" * 70)
    
    trailing_levels = [-5, -8, -10, -12, -15]
    
    for trail_pct in trailing_levels:
        total_return = 0
        count = 0
        
        for signal in backtester.signals:
            if signal['type'] != 'BUY':
                continue
            
            buy_price = signal['price']
            max_price = buy_price
            exit_price = None
            
            # 模拟每天价格
            for day in range(1, 31):
                day_price = backtester._get_price_after_days(signal['coin'], signal['date'], day)
                if not day_price:
                    continue
                
                max_price = max(max_price, day_price)
                trailing_stop = max_price * (1 + trail_pct / 100)
                
                if day_price <= trailing_stop:
                    exit_price = day_price
                    break
            
            if exit_price is None:
                # 持有到30天
                exit_price = backtester._get_price_after_days(signal['coin'], signal['date'], 30)
            
            if exit_price:
                ret = (exit_price - buy_price) / buy_price * 100
                total_return += ret
                count += 1
        
        avg_return = total_return / count if count else 0
        print(f"  Trailing {trail_pct}%: 平均收益 {avg_return:+.2f}%")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--optimize-stop':
        optimize_stop_loss()
    else:
        main()

