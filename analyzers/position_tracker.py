"""
持仓追踪模块
管理买入信号后的持仓状态，实现动态止损
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class Position:
    """单个持仓"""
    
    def __init__(self, coin: str, entry_price: float, entry_date: str, signal_reasons: List[str] = None):
        self.coin = coin
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.signal_reasons = signal_reasons or []
        self.max_price = entry_price  # 历史最高价
        self.current_price = entry_price
        self.status = "open"  # open / stopped / closed
        self.stop_triggered_at = None
        self.stop_price = None
    
    def update_price(self, price: float) -> bool:
        """更新价格，返回是否触发止损"""
        self.current_price = price
        if price > self.max_price:
            self.max_price = price
        return False  # 实际止损检查在 PositionTracker 中
    
    def get_return_pct(self) -> float:
        """获取当前收益率"""
        return (self.current_price - self.entry_price) / self.entry_price * 100
    
    def get_drawdown_from_max(self) -> float:
        """获取从最高点的回撤"""
        if self.max_price == 0:
            return 0
        return (self.current_price - self.max_price) / self.max_price * 100
    
    def to_dict(self) -> dict:
        return {
            'coin': self.coin,
            'entry_price': self.entry_price,
            'entry_date': self.entry_date,
            'signal_reasons': self.signal_reasons,
            'max_price': self.max_price,
            'current_price': self.current_price,
            'status': self.status,
            'stop_triggered_at': self.stop_triggered_at,
            'stop_price': self.stop_price,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        pos = cls(
            coin=data['coin'],
            entry_price=data['entry_price'],
            entry_date=data['entry_date'],
            signal_reasons=data.get('signal_reasons', [])
        )
        pos.max_price = data.get('max_price', pos.entry_price)
        pos.current_price = data.get('current_price', pos.entry_price)
        pos.status = data.get('status', 'open')
        pos.stop_triggered_at = data.get('stop_triggered_at')
        pos.stop_price = data.get('stop_price')
        return pos


class PositionTracker:
    """持仓追踪器"""
    
    def __init__(self, config: dict, db=None):
        self.config = config
        self.db = db
        self.positions: Dict[str, Position] = {}  # coin -> Position
        
        # 风控配置
        risk_config = config.get('risk', {})
        self.stop_type = risk_config.get('stop_loss_type', 'trailing')
        self.stop_pct = risk_config.get('stop_loss_pct', -15)
        self.initial_stop = risk_config.get('initial_stop', -20)
        self.notify_on_stop = risk_config.get('notify_on_stop', True)
        
        # 加载持仓
        self._load_positions()
    
    def _get_positions_file(self) -> str:
        return os.path.join(os.path.dirname(__file__), '..', '.positions.json')
    
    def _load_positions(self):
        """从文件加载持仓"""
        path = self._get_positions_file()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for pos_data in data.get('positions', []):
                        pos = Position.from_dict(pos_data)
                        if pos.status == 'open':
                            self.positions[pos.coin] = pos
                logger.info(f"📂 加载 {len(self.positions)} 个持仓")
            except Exception as e:
                logger.warning(f"加载持仓失败: {e}")
    
    def _save_positions(self):
        """保存持仓到文件"""
        path = self._get_positions_file()
        try:
            data = {
                'updated_at': datetime.now().isoformat(),
                'positions': [p.to_dict() for p in self.positions.values()]
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"保存持仓失败: {e}")
    
    def add_position(self, coin: str, price: float, reasons: List[str] = None):
        """添加新持仓"""
        if coin in self.positions:
            logger.info(f"⚠️ {coin} 已有持仓，跳过")
            return
        
        pos = Position(
            coin=coin,
            entry_price=price,
            entry_date=datetime.now().strftime('%Y-%m-%d'),
            signal_reasons=reasons
        )
        self.positions[coin] = pos
        self._save_positions()
        logger.info(f"📥 添加持仓: {coin} @ ${price:.2f}")
    
    def update_prices(self, prices: Dict[str, float]) -> List[Dict]:
        """
        更新所有持仓价格
        返回触发止损的列表
        """
        stopped = []
        
        for coin, price in prices.items():
            if coin not in self.positions:
                continue
            
            pos = self.positions[coin]
            pos.update_price(price)
            
            # 检查止损
            stop_triggered = self._check_stop_loss(pos)
            if stop_triggered:
                pos.status = 'stopped'
                pos.stop_triggered_at = datetime.now().isoformat()
                pos.stop_price = price
                
                stopped.append({
                    'coin': coin,
                    'entry_price': pos.entry_price,
                    'stop_price': price,
                    'return_pct': pos.get_return_pct(),
                    'max_price': pos.max_price,
                    'drawdown': pos.get_drawdown_from_max(),
                })
                
                logger.warning(f"🛑 {coin} 触发止损: ${pos.entry_price:.2f} -> ${price:.2f} ({pos.get_return_pct():+.1f}%)")
        
        self._save_positions()
        return stopped
    
    def _check_stop_loss(self, pos: Position) -> bool:
        """检查是否触发止损"""
        if pos.status != 'open':
            return False
        
        if self.stop_type == 'trailing':
            # 动态止损：从最高价回撤
            drawdown = pos.get_drawdown_from_max()
            return drawdown <= self.stop_pct
        else:
            # 固定止损：从买入价
            ret = pos.get_return_pct()
            return ret <= self.initial_stop
    
    def get_stop_line(self, coin: str) -> Optional[float]:
        """获取某币种当前止损线价格"""
        if coin not in self.positions:
            return None
        
        pos = self.positions[coin]
        if self.stop_type == 'trailing':
            return pos.max_price * (1 + self.stop_pct / 100)
        else:
            return pos.entry_price * (1 + self.initial_stop / 100)
    
    def get_status(self) -> Dict:
        """获取持仓状态摘要"""
        total_return = 0
        for pos in self.positions.values():
            if pos.status == 'open':
                total_return += pos.get_return_pct()
        
        return {
            'open_positions': len([p for p in self.positions.values() if p.status == 'open']),
            'total_return_pct': round(total_return, 2),
            'positions': {k: v.to_dict() for k, v in self.positions.items() if v.status == 'open'}
        }
    
    def remove_position(self, coin: str):
        """移除持仓（手动平仓）"""
        if coin in self.positions:
            del self.positions[coin]
            self._save_positions()
            logger.info(f"📤 移除持仓: {coin}")
