"""
信号生成器
根据情绪分析生成交易信号
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class SignalGenerator:
    """信号生成器"""
    
    def __init__(self, config: dict, db):
        self.config = config
        self.db = db
        self.thresholds = config['thresholds']
        self.reversal_config = config['reversal']
        self.resonance_config = config['resonance']
        self.strategy_config = config.get('strategy', {})
        self.windows_config = config.get('windows', {})
    
    def generate_signals(self, data: dict) -> List[Dict]:
        """
        生成交易信号
        :param data: 市场数据
        :return: 信号列表
        """
        signals = []
        
        if not self.strategy_config.get('use_fear_greed', True):
            logger.warning("恐慌指数已禁用，跳过信号生成")
            return signals
        
        if not data.get('fear_greed'):
            logger.warning("无恐慌指数数据，跳过信号生成")
            return signals
        
        fg_value = data['fear_greed']['value']
        
        # 为每个启用的币种生成信号
        for coin_symbol, coin_data in data.get('coins', {}).items():
            if not coin_data.get('price'):
                continue
            
            ts_val = data.get('timestamp')
            
            current_ts = ts_val.timestamp() if hasattr(ts_val, 'timestamp') else None
            
            signal = self._generate_coin_signal(
                coin_symbol, 
                coin_data, 
                fg_value, 
                data,
                current_ts
            )
            
            if signal:
                signals.append(signal)
        
        # 检测共振
        if self.strategy_config.get('use_resonance', True) and self.resonance_config['enabled']:
            resonance_count = len(signals)
            min_coins = self.resonance_config['min_coins']
            
            if resonance_count >= min_coins:
                logger.info(f"检测到{resonance_count}个币种共振")
                for signal in signals:
                    signal['tags'].append('#共振')
                    signal['strength'] = self._upgrade_strength(signal['strength'])
                    signal['reasons'].append(f"市场共振({resonance_count}个币种)")
        
        return signals
    
    def _generate_coin_signal(
        self, 
        coin: str, 
        coin_data: dict, 
        fg_value: int, 
        full_data: dict,
        current_timestamp: Optional[int] = None
    ) -> Optional[Dict]:
        """
        为单个币种生成信号
        """
        # 买入信号判断
        if fg_value < self.thresholds['fear_buy']:
            return self._generate_buy_signal(coin, coin_data, fg_value, full_data, current_timestamp)
        
        # 卖出信号判断
        elif fg_value > self.thresholds['greed_sell']:
            return self._generate_sell_signal(coin, coin_data, fg_value, full_data, current_timestamp)
        
        return None
    
    def _generate_buy_signal(
        self, 
        coin: str, 
        coin_data: dict, 
        fg_value: int, 
        full_data: dict,
        current_timestamp: Optional[int] = None
    ) -> Optional[Dict]:
        """生成买入信号"""
        
        strength = "弱"
        reasons = [f"恐慌指数: {fg_value}"]
        tags = ["#观察"]
        is_reversal = False
        
        # 检查拐点
        if self.strategy_config.get('use_reversal', True) and self.reversal_config['enabled']:
            is_reversal = self._check_reversal(fg_value, current_timestamp)
            if is_reversal:
                strength = "中等"
                reasons.append("✅ 恐慌拐点确认")
                tags = ["#拐点确认"]
        
        # 检查资金费率分位数
        if self.strategy_config.get('use_funding_percentile', True):
            funding = coin_data.get('funding_rate')
            if funding is not None:
                funding_pct = self._calculate_funding_percentile(coin, funding)
                
                if funding_pct and funding_pct < self.thresholds['funding_panic_percentile']:
                    strength = "强"
                    reasons.append(f"资金费率分位: {funding_pct:.1f}% (极端恐慌)")
                    tags = ["#抄底"]
        
        # 检查多空比
        if self.strategy_config.get('use_longshort', True):
            ls = coin_data.get('longshort')
            if ls:
                ratio = ls.get('ratio', 1)
                if ratio < self.thresholds['longshort_extreme']:
                    reasons.append(f"多空比: {ratio} (空头主导)")
                    if strength == "强":
                        strength = "极强"
        
        # 只在有强信号时才发出
        if strength in ["中等", "强", "极强"] or is_reversal:
            return {
                'coin': coin,
                'type': 'BUY',
                'strength': strength,
                'reasons': reasons,
                'tags': tags
            }
        
        return None
    
    def _generate_sell_signal(
        self, 
        coin: str, 
        coin_data: dict, 
        fg_value: int, 
        full_data: dict,
        current_timestamp: Optional[int] = None
    ) -> Optional[Dict]:
        """生成卖出信号"""
        
        strength = "弱"
        reasons = [f"贪婪指数: {fg_value}"]
        tags = ["#观察"]
        is_reversal = False
        funding_pct = None
        
        # 检查拐点
        if self.strategy_config.get('use_reversal', True) and self.reversal_config['enabled']:
            is_reversal = self._check_reversal(fg_value, current_timestamp)
            if is_reversal:
                strength = "中等"
                reasons.append("✅ 贪婪拐点确认")
                tags = ["#拐点确认", "#派发区"]
        
        # 检查资金费率
        if self.strategy_config.get('use_funding_percentile', True):
            funding = coin_data.get('funding_rate')
            if funding is not None:
                funding_pct = self._calculate_funding_percentile(coin, funding)
                
                if funding_pct and funding_pct > self.thresholds['funding_greed_percentile']:
                    strength = "强"
                    reasons.append(f"资金费率分位: {funding_pct:.1f}% (过热)")
                    tags = ["#派发区", "#过热"]
        
        # 只在有强信号时才发出（与买入逻辑对称）
        if strength in ["中等", "强", "极强"] or is_reversal:
            return {
                'coin': coin,
                'type': 'SELL',
                'strength': strength,
                'reasons': reasons,
                'tags': tags
            }
        
        return None
    
    def _check_reversal(self, current_fg: int, current_timestamp: Optional[int] = None) -> bool:
        """
        检查情绪拐点
        需要连续N次反转确认
        """
        if not self.reversal_config['enabled']:
            return False

        try:
            # 获取历史恐慌指数
            # Use configured history window or default to 72 hours
            history_hours = self.windows_config.get('reversal_history_hours', 72)
            full_history = self.db.get_fear_greed_history(hours=history_hours)
            
            # 过滤掉当前的数据点
            history = []
            if current_timestamp:
                values = []
                for item in full_history:
                    # 将DB时间字符串转为timestamp
                    try:
                        if isinstance(item['timestamp'], str):
                            # 修复：SQLite CURRENT_TIMESTAMP 格式为空格分隔，需转换为 ISO 格式
                            time_str = item['timestamp'].replace(' ', 'T')
                            dt = datetime.fromisoformat(time_str)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            ts = dt.timestamp()
                        else:
                            ts = item['timestamp']
                        
                        # 只有当记录时间早于当前时间(容差5秒)才算历史
                        if ts < current_timestamp - 5:
                            values.append(item['value'])
                    except Exception as e:
                        # 时间戳解析失败时，跳过该数据点（避免把当前点误加入历史）
                        # 如果需要调试，取消下面的注释
                        # logger.debug(f"跳过数据点，时间解析失败: {e}")
                        continue
                history = values
            else:
                # 兼容旧逻辑
                history = [item['value'] for item in full_history]

            # N次反转需要至少N个数据变化，即N+1个数据点
            # 由于我们使用history[-1]作为起始点，所以至少需要required_periods个历史数据
            required_periods = self.reversal_config.get('consecutive_periods', 2)
            if len(history) < required_periods:
                return False

            # 恐慌反转：连续上升（从恐慌转向贪婪）
            if current_fg < 30:
                # 确保最新的历史数据也在恐慌区域
                if history[-1] >= 30:
                    return False

                # 检查是否有required_periods次连续上升
                # 序列：history[-required_periods] -> ... -> history[-2] -> history[-1] -> current_fg
                # 或者：history[-required_periods+1] -> ... -> history[-1] -> current_fg （如果刚好够）

                # 获取要检查的历史数据范围
                check_range = required_periods  # 需要检查的历史数据点数
                if len(history) < check_range:
                    return False

                start_idx = len(history) - check_range
                for i in range(start_idx, len(history)):
                    # 检查所有历史数据是否都在恐慌区域
                    if history[i] >= 30:
                        return False

                # 检查连续上升
                # 从 start_idx 到 len(history)-1 检查历史数据中的连续上升
                for i in range(start_idx + 1, len(history)):
                    if history[i] <= history[i-1]:
                        return False  # 没有上升

                # 检查当前值是否继续上升
                if current_fg <= history[-1]:
                    return False  # 当前值没有上升

                return True  # 所有的上升检查都通过了

            # 贪婪反转：连续下降（从贪婪转向恐慌）
            if current_fg > 70:
                # 确保最新的历史数据也在贪婪区域
                if history[-1] <= 70:
                    return False

                # 检查是否有required_periods次连续下降
                check_range = required_periods
                if len(history) < check_range:
                    return False

                start_idx = len(history) - check_range
                for i in range(start_idx, len(history)):
                    # 检查所有历史数据是否都在贪婪区域
                    if history[i] <= 70:
                        return False

                # 检查连续下降
                # 从 start_idx 到 len(history)-1 检查历史数据中的连续下降
                for i in range(start_idx + 1, len(history)):
                    if history[i] >= history[i-1]:
                        return False  # 没有下降

                # 检查当前值是否继续下降
                if current_fg >= history[-1]:
                    return False  # 当前值没有下降

                return True  # 所有的下降检查都通过了

            return False

        except Exception as e:
            logger.error(f"检查拐点失败: {e}")
            return False
    
    def _calculate_funding_percentile(self, coin: str, current_rate: float) -> Optional[float]:
        """
        计算资金费率在历史中的分位数
        """
        try:
            # Use configured history window or default to 168 hours (7 days)
            history_hours = self.windows_config.get('funding_history_hours', 168)
            history = self.db.get_funding_history(coin, hours=history_hours)
            
            if len(history) < 24:  # 至少1天数据
                return None
            
            lower_count = sum(1 for x in history if x < current_rate)
            percentile = (lower_count / len(history)) * 100
            
            return round(percentile, 1)
        
        except Exception as e:
            logger.error(f"计算分位数失败: {e}")
            return None
    
    def _upgrade_strength(self, strength: str) -> str:
        """升级信号强度"""
        if "弱" in strength:
            return "中等"
        elif "中等" in strength:
            return "强"
        elif "强" in strength and "极" not in strength:
            return "极强"
        return strength