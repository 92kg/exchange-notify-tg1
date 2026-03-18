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
    
    def __init__(self, coin: str, entry_price: float, entry_date: str, signal_reasons: List[str] = None, amount: float = 1.0):
        self.coin = coin
        self.entry_price = entry_price
        self.amount = amount
        self.entry_date = entry_date
        self.signal_reasons = signal_reasons or []
        self.max_price = entry_price  # 历史最高价
        self.current_price = entry_price
        self.status = "open"  # open / stopped / closed
        self.stop_triggered_at = None
        self.stop_price = None
        
    def add_amount(self, price: float, amount: float):
        """加仓：更新平均价格和数量"""
        total_value = (self.entry_price * self.amount) + (price * amount)
        self.amount += amount
        self.entry_price = total_value / self.amount
        # max_price 保持不变，还是取历史最高？
        # 如果加仓后均价变了，止损线也会变（如果是固定止损）。
        # 如果是移动止损，max_price 应该是基于"当前价格"的历史最高。
        # 加仓不影响历史最高价的记录，但会影响盈亏计算。
        # 重新评估当前价格是否高于 max_price (理论上实时更新会做，这里只做数据合并)
    
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
            'amount': self.amount,
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
            signal_reasons=data.get('signal_reasons', []),
            amount=data.get('amount', 1.0)
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
    
    def add_position(self, coin: str, price: float, reasons: List[str] = None, amount: float = 1.0):
        """添加或更新持仓 (支持加仓)"""
        if coin in self.positions:
            pos = self.positions[coin]
            old_price = pos.entry_price
            pos.add_amount(price, amount)
            if reasons:
                pos.signal_reasons.extend(reasons)
                # 去重
                pos.signal_reasons = list(set(pos.signal_reasons))
                
            self._save_positions()
            logger.info(f"➕ {coin} 加仓: ${price:.2f} (新均价: ${pos.entry_price:.2f})")
            return
        
        pos = Position(
            coin=coin,
            entry_price=price,
            entry_date=datetime.now().strftime('%Y-%m-%d'),
            signal_reasons=reasons,
            amount=amount
        )
        self.positions[coin] = pos
        self._save_positions()
        logger.info(f"📥 建仓: {coin} @ ${price:.2f}")
    
    def update_prices(self, prices: Dict[str, float]) -> Dict:
        """
        更新所有持仓价格
        返回事件字典: {'stopped': [...], 'new_highs': [...], 'stop_line_raised': [...]}
        """
        stopped = []
        new_highs = []
        stop_line_raised = []
        
        for coin, price in prices.items():
            if coin not in self.positions:
                continue
            
            pos = self.positions[coin]
            old_max = pos.max_price
            old_stop_line = self.get_stop_line(coin)
            
            pos.update_price(price)
            
            new_max = pos.max_price
            new_stop_line = self.get_stop_line(coin)
            
            # 检测新高突破 (首次超过旧最高价)
            if new_max > old_max and old_max == pos.entry_price:
                # 第一次新高，发送提醒
                new_highs.append({
                    'coin': coin,
                    'entry_price': pos.entry_price,
                    'new_high': new_max,
                    'return_pct': pos.get_return_pct(),
                })
                logger.info(f"🚀 {coin} 创新高: ${new_max:.2f} (+{pos.get_return_pct():.1f}%)")
            
            # 检测止损线上移 (涨幅>2%导致止损线上移)
            if old_stop_line and new_stop_line and new_stop_line > old_stop_line:
                raise_pct = (new_stop_line - old_stop_line) / old_stop_line * 100
                if raise_pct >= 2.0:  # 止损线上移超过2%才通知
                    stop_line_raised.append({
                        'coin': coin,
                        'old_stop': old_stop_line,
                        'new_stop': new_stop_line,
                        'raise_pct': raise_pct,
                        'current_price': price,
                    })
                    logger.info(f"📈 {coin} 止损线上移: ${old_stop_line:.2f} -> ${new_stop_line:.2f}")
            
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
        return {
            'stopped': stopped,
            'new_highs': new_highs,
            'stop_line_raised': stop_line_raised,
        }
    
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

    def sync_positions(self, exchange_positions: List[Dict]):
        """
        与交易所真实仓位对账
        :param exchange_positions: 交易所返回的持仓列表
        """
        logger.info("🔄 开始持仓对账...")
        
        # 1. 将交易所仓位转为 map 方便查找
        ex_map = {p['symbol']: p for p in exchange_positions}
        
        # 2. 检查本地记录，如果交易所已无此仓位，则本地也移除
        local_coins = list(self.positions.keys())
        removed_count = 0
        for coin in local_coins:
            if coin not in ex_map:
                logger.warning(f"⚠️ 对账差异: 发现本地记录 {coin} 但交易所无持仓，已自动同步移除")
                del self.positions[coin]
                removed_count += 1
        
        # 3. 检查交易所仓位，更新本地数据或新增
        added_count = 0
        synced_count = 0
        for coin, ex_pos in ex_map.items():
            if coin in self.positions:
                # 已有持仓，同步数量和价格（以此价格为基准？）
                # 通常我们保留本地的 entry_price 除非差异过大
                pos = self.positions[coin]
                if abs(pos.amount - abs(ex_pos['size'])) > 0.00001:
                    logger.info(f"📊 对账更新: {coin} 数量差异 {pos.amount} -> {abs(ex_pos['size'])}")
                    pos.amount = abs(ex_pos['size'])
                    synced_count += 1
            else:
                # 本地缺失，交易所持有：创建新记录
                logger.info(f"➕ 对账发现新仓位: {coin} @ ${ex_pos['entry_price']:.2f}")
                entry_price = ex_pos['entry_price']
                new_pos = Position(
                    coin=coin,
                    entry_price=entry_price,
                    entry_date=datetime.now().strftime('%Y-%m-%d'),
                    signal_reasons=["对账导入"],
                    amount=abs(ex_pos['size'])
                )
                new_pos.current_price = ex_pos.get('current_price', entry_price)
                new_pos.max_price = max(entry_price, new_pos.current_price)
                self.positions[coin] = new_pos
                added_count += 1
        
        if added_count > 0 or removed_count > 0 or synced_count > 0:
            self._save_positions()
            logger.info(f"✅ 对账完成: 新增 {added_count}, 移除 {removed_count}, 同步 {synced_count}")
        else:
            logger.info("✅ 对账完成: 本地与交易所数据完全一致")
