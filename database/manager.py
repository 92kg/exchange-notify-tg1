"""
数据库管理器
使用SQLite3存储历史数据和信号
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_file='crypto_sentiment_v3.db'):
        self.db_file = db_file
        self.conn = None
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def init_database(self):
        """初始化数据库表结构"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 市场数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                fear_greed_index INTEGER,
                coins_data TEXT  -- JSON格式存储所有币种数据
            )
        ''')
        
        # 信号表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                coin_symbol TEXT,
                signal_type TEXT,  -- BUY or SELL
                strength TEXT,
                price_at_signal REAL,
                fear_greed_at_signal INTEGER,
                reasons TEXT,  -- JSON
                tags TEXT,     -- JSON
                
                -- 回测字段
                price_7d REAL,
                price_14d REAL,
                price_30d REAL,
                return_7d REAL,
                return_14d REAL,
                return_30d REAL,
                is_successful BOOLEAN
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_market_timestamp 
            ON market_data(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_signal_timestamp 
            ON signals(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_signal_coin 
            ON signals(coin_symbol)
        ''')
        
        conn.commit()
        logger.info("数据库初始化完成")
    
    def save_market_data(self, data: dict):
        """
        保存市场数据
        :param data: 包含fear_greed和coins的字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # 序列化币种数据为JSON
            coins_json = json.dumps(data.get('coins', {}))
            
            cursor.execute('''
                INSERT INTO market_data (fear_greed_index, coins_data)
                VALUES (?, ?)
            ''', (
                data['fear_greed']['value'] if data.get('fear_greed') else None,
                coins_json
            ))
            
            conn.commit()
            logger.debug("市场数据已保存")
        
        except Exception as e:
            logger.error(f"保存市场数据失败: {e}")
            conn.rollback()
    
    def save_signal(self, signal: dict, data: dict):
        """
        保存交易信号
        :param signal: 信号字典
        :param data: 当前市场数据
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            coin_symbol = signal['coin']
            coin_data = data['coins'].get(coin_symbol, {})
            price = coin_data.get('price')
            
            cursor.execute('''
                INSERT INTO signals (
                    coin_symbol, signal_type, strength,
                    price_at_signal, fear_greed_at_signal,
                    reasons, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                coin_symbol,
                signal['type'],
                signal['strength'],
                price,
                data['fear_greed']['value'] if data.get('fear_greed') else None,
                json.dumps(signal['reasons']),
                json.dumps(signal['tags'])
            ))
            
            conn.commit()
            logger.info(f"信号已保存: {coin_symbol} {signal['type']}")
        
        except Exception as e:
            logger.error(f"保存信号失败: {e}")
            conn.rollback()
    
    def get_fear_greed_history(self, hours: int = 72) -> List[int]:
        """
        获取恐慌指数历史
        :param hours: 获取最近N小时的数据
        :return: 恐慌指数列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(f'''
                SELECT fear_greed_index FROM market_data
                WHERE fear_greed_index IS NOT NULL
                AND timestamp >= datetime('now', '-{hours} hours')
                ORDER BY timestamp
            ''')
            
            return [row[0] for row in cursor.fetchall()]
        
        except Exception as e:
            logger.error(f"获取恐慌指数历史失败: {e}")
            return []
    
    def get_funding_history(self, coin: str, hours: int = 168) -> List[float]:
        """
        获取资金费率历史
        :param coin: 币种符号
        :param hours: 获取最近N小时的数据
        :return: 资金费率列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(f'''
                SELECT coins_data FROM market_data
                WHERE timestamp >= datetime('now', '-{hours} hours')
                ORDER BY timestamp
            ''')
            
            rates = []
            for row in cursor.fetchall():
                try:
                    coins_data = json.loads(row[0])
                    if coin in coins_data:
                        funding = coins_data[coin].get('funding_rate')
                        if funding is not None:
                            rates.append(funding)
                except json.JSONDecodeError:
                    continue
            
            return rates
        
        except Exception as e:
            logger.error(f"获取资金费率历史失败: {e}")
            return []
    
    def get_signal_statistics(self) -> Dict:
        """
        获取信号统计
        :return: 统计信息字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_signals,
                    SUM(CASE WHEN is_successful = 1 THEN 1 ELSE 0 END) as winning_signals,
                    AVG(return_7d) as avg_return_7d,
                    MIN(return_7d) as min_return_7d,
                    MAX(return_7d) as max_return_7d,
                    coin_symbol,
                    signal_type
                FROM signals
                WHERE return_7d IS NOT NULL
                GROUP BY coin_symbol, signal_type
            ''')
            
            stats = {}
            for row in cursor.fetchall():
                key = f"{row[5]}_{row[6]}"
                total = row[0]
                wins = row[1]
                avg_return = row[2] if row[2] else 0
                min_return = row[3] if row[3] else 0
                max_return = row[4] if row[4] else 0
                
                # 计算风险指标
                volatility = (max_return - min_return) / 2 if total > 0 else 0
                
                stats[key] = {
                    'total': total,
                    'wins': wins,
                    'losses': total - wins,
                    'win_rate': (wins / total) * 100 if total > 0 else 0,
                    'avg_return': avg_return,
                    'min_return': min_return,
                    'max_return': max_return,
                    'volatility': volatility
                }
            
            return stats
        
        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            return {}
    
    def get_overfitting_warning(self, stats: Dict) -> dict:
        """
        生成过拟合警告
        :param stats: 统计信息
        :return: 警告信息
        """
        warnings = []
        risk_level = 0
        
        if not stats:
            return {'risk_level': 0, 'warnings': ['暂无回测数据']}
        
        # 检查样本量
        total_signals = sum(s['total'] for s in stats.values())
        if total_signals < 10:
            warnings.append(f"⚠️ 样本量过小 ({total_signals}个)，统计无意义")
            risk_level += 2
        elif total_signals < 30:
            warnings.append(f"⚠️ 样本量偏少 ({total_signals}个)，可信度低")
            risk_level += 1
        
        # 检查胜率异常
        for key, s in stats.items():
            if s['total'] >= 10 and s['win_rate'] > 80:
                warnings.append(f"⚠️ {key} 胜率过高 ({s['win_rate']:.1f}%)，可能过拟合")
                risk_level += 1
            elif s['total'] >= 10 and s['win_rate'] < 30:
                warnings.append(f"⚠️ {key} 胜率过低 ({s['win_rate']:.1f}%)，策略无效")
                risk_level += 1
        
        # 检查收益波动
        for key, s in stats.items():
            if s['volatility'] > 30:
                warnings.append(f"⚠️ {key} 波动过大 ({s['volatility']:.1f}%)，风险高")
                risk_level += 1
        
        # 检查买卖不平衡
        buy_signals = sum(s['total'] for key, s in stats.items() if 'BUY' in key)
        sell_signals = sum(s['total'] for key, s in stats.items() if 'SELL' in key)
        if buy_signals > 0 and sell_signals > 0:
            ratio = buy_signals / sell_signals
            if ratio > 3:
                warnings.append(f"⚠️ 买卖严重失衡 (买:卖 = {ratio:.1f}:1)")
                risk_level += 1
        
        return {'risk_level': risk_level, 'warnings': warnings}
    
    def get_pending_backtest_signals(self, days_list: List[int]) -> List[Dict]:
        """
        获取需要回测的信号
        :param days_list: 需要回测的天数列表，如 [7, 14, 30]
        :return: 信号列表
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT id, timestamp, coin_symbol, signal_type, price_at_signal
                FROM signals
                WHERE return_7d IS NULL
                ORDER BY timestamp
            ''')
            
            signals = []
            for row in cursor.fetchall():
                signals.append({
                    'id': row[0],
                    'timestamp': datetime.fromisoformat(row[1].replace(' ', 'T')) if isinstance(row[1], str) else row[1],
                    'coin': row[2],
                    'type': row[3],
                    'price': row[4]
                })
            
            return signals
        
        except Exception as e:
            logger.error(f"获取待回测信号失败: {e}")
            return []
    
    def update_backtest_results(self, signal_id: int, results: Dict):
        """
        更新回测结果
        :param signal_id: 信号ID
        :param results: 回测结果字典
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE signals SET
                    price_7d = ?,
                    price_14d = ?,
                    price_30d = ?,
                    return_7d = ?,
                    return_14d = ?,
                    return_30d = ?,
                    is_successful = ?
                WHERE id = ?
            ''', (
                results.get('price_7d'),
                results.get('price_14d'),
                results.get('price_30d'),
                results.get('return_7d'),
                results.get('return_14d'),
                results.get('return_30d'),
                results.get('is_successful'),
                signal_id
            ))
            
            conn.commit()
            logger.info(f"回测结果已更新: 信号ID {signal_id}")
        
        except Exception as e:
            logger.error(f"更新回测结果失败: {e}")
            conn.rollback()
    
    def get_price_at_time(self, coin: str, timestamp: datetime) -> Optional[float]:
        """
        从历史数据中获取指定时间的价格
        :param coin: 币种
        :param timestamp: 时间戳
        :return: 价格
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT coins_data FROM market_data
                WHERE timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (timestamp.isoformat(),))
            
            row = cursor.fetchone()
            if row:
                coins_data = json.loads(row[0])
                if coin in coins_data:
                    return coins_data[coin].get('price')
        
        except Exception as e:
            logger.error(f"获取历史价格失败: {e}")
        
        return None
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("数据库连接已关闭")