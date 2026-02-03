"""
信号生成器
根据情绪分析生成交易信号
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class SignalGenerator:
    """信号生成器"""
    
    def __init__(self, config: dict, db):
        self.config = config
        self.db = db
        self.thresholds = config['thresholds']
        self.reversal_config = config['reversal']
        self.resonance_config = config['resonance']
    
    def generate_signals(self, data: dict) -> List[Dict]:
        """
        生成交易信号
        :param data: 市场数据
        :return: 信号列表
        """
        signals = []
        
        if not data.get('fear_greed'):
            logger.warning("无恐慌指数数据，跳过信号生成")
            return signals
        
        fg_value = data['fear_greed']['value']
        
        # 为每个启用的币种生成信号
        for coin_symbol, coin_data in data.get('coins', {}).items():
            if not coin_data.get('price'):
                continue
            
            signal = self._generate_coin_signal(
                coin_symbol, 
                coin_data, 
                fg_value, 
                data
            )
            
            if signal:
                signals.append(signal)
        
        # 检测共振
        if self.resonance_config['enabled']:
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
        full_data: dict
    ) -> Optional[Dict]:
        """
        为单个币种生成信号
        """
        # 买入信号判断
        if fg_value < self.thresholds['fear_buy']:
            return self._generate_buy_signal(coin, coin_data, fg_value, full_data)
        
        # 卖出信号判断
        elif fg_value > self.thresholds['greed_sell']:
            return self._generate_sell_signal(coin, coin_data, fg_value, full_data)
        
        return None
    
    def _generate_buy_signal(
        self, 
        coin: str, 
        coin_data: dict, 
        fg_value: int, 
        full_data: dict
    ) -> Optional[Dict]:
        """生成买入信号"""
        
        strength = "弱"
        reasons = [f"恐慌指数: {fg_value}"]
        tags = ["#观察"]
        
        # 检查拐点
        is_reversal = self._check_reversal(fg_value)
        if is_reversal:
            strength = "中等"
            reasons.append("✅ 恐慌拐点确认")
            tags = ["#拐点确认"]
        
        # 检查资金费率分位数
        funding = coin_data.get('funding_rate')
        if funding is not None:
            funding_pct = self._calculate_funding_percentile(coin, funding)
            
            if funding_pct and funding_pct < self.thresholds['funding_panic_percentile']:
                strength = "强"
                reasons.append(f"资金费率分位: {funding_pct:.1f}% (极端恐慌)")
                tags = ["#抄底"]
        
        # 检查多空比
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
        full_data: dict
    ) -> Optional[Dict]:
        """生成卖出信号"""
        
        strength = "中等"
        reasons = [f"贪婪指数: {fg_value}"]
        tags = ["#减仓观望"]
        
        # 检查拐点
        is_reversal = self._check_reversal(fg_value)
        if is_reversal:
            strength = "强"
            reasons.append("✅ 贪婪拐点确认")
            tags = ["#拐点确认", "#派发区"]
        
        # 检查资金费率
        funding = coin_data.get('funding_rate')
        if funding is not None:
            funding_pct = self._calculate_funding_percentile(coin, funding)
            
            if funding_pct and funding_pct > self.thresholds['funding_greed_percentile']:
                strength = "极强"
                reasons.append(f"资金费率分位: {funding_pct:.1f}% (过热)")
                tags = ["#派发区", "#过热"]
        
        # 只在有拐点或极端资金费率时发信号
        if is_reversal or (funding_pct and funding_pct > 85):
            return {
                'coin': coin,
                'type': 'SELL',
                'strength': strength,
                'reasons': reasons,
                'tags': tags
            }
        
        return None
    
    def _check_reversal(self, current_fg: int) -> bool:
        """
        检查情绪拐点
        需要连续N次反转确认
        """
        if not self.reversal_config['enabled']:
            return False
        
        try:
            # 获取历史恐慌指数
            history = self.db.get_fear_greed_history(hours=72)
            
            if len(history) < 3:
                return False
            
            # 恐慌反转：连续上升
            if current_fg < 30:
                if history[-1] > history[-2] and current_fg > history[-1]:
                    return True
            
            # 贪婪反转：连续下降
            if current_fg > 70:
                if history[-1] < history[-2] and current_fg < history[-1]:
                    return True
            
            return False
        
        except Exception as e:
            logger.error(f"检查拐点失败: {e}")
            return False
    
    def _calculate_funding_percentile(self, coin: str, current_rate: float) -> Optional[float]:
        """
        计算资金费率在历史中的分位数
        """
        try:
            history = self.db.get_funding_history(coin, hours=168)  # 7天
            
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