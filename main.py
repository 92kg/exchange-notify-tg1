"""
加密货币情绪监控系统 v3.4
模块化、多交易所、多币种支持
支持动态止损 (Trailing Stop)
"""

import yaml
import time
import logging
from datetime import datetime
from pathlib import Path

from exchanges import ExchangeFactory
from database.manager import DatabaseManager
from analyzers.sentiment import SentimentAnalyzer
from analyzers.signal import SignalGenerator
from analyzers.position_tracker import PositionTracker
from notifiers.telegram import TelegramNotifier
from utils.helpers import format_price, format_percentage
from datetime import timedelta

class CryptoSentimentMonitor:
    """加密货币情绪监控主类"""
    
    def __init__(self, config_file='config.yaml'):
        """初始化系统"""
        
        # 加载配置
        self.config = self._load_config(config_file)
        
        # 配置日志
        self._setup_logging()
        
        # 初始化组件
        self.logger = logging.getLogger(__name__)
        self.logger.info("="*60)
        self.logger.info("加密货币情绪监控系统 v3.4 初始化中...")
        self.logger.info("="*60)
        
        try:
            # 交易所
            self.exchange = ExchangeFactory.create(self.config['exchange'])
            self.logger.info(f"✅ 交易所: {self.exchange.name.upper()}")
            
            # 数据库
            self.db = DatabaseManager(self.config['runtime']['db_file'])
            self.logger.info(f"✅ 数据库: {self.config['runtime']['db_file']}")
            
            # 分析器
            self.sentiment_analyzer = SentimentAnalyzer(self.config, self.db)
            self.signal_generator = SignalGenerator(self.config, self.db)
            self.logger.info("✅ 分析器已加载")
            
            # 持仓追踪器（动态止损）
            self.position_tracker = PositionTracker(self.config, self.db)
            risk_config = self.config.get('risk', {})
            self.logger.info(f"✅ 持仓追踪: {risk_config.get('stop_loss_type', 'fixed')} 止损 {risk_config.get('stop_loss_pct', -15)}%")
            
            # 通知器
            if self.config['telegram']['enabled']:
                self.notifier = TelegramNotifier(
                    self.config['telegram']['bot_token'],
                    self.config['telegram']['chat_id']
                )
                # 测试连接
                if self.notifier.test_connection():
                    self.logger.info("✅ Telegram连接成功")
                else:
                    self.logger.warning("⚠️ Telegram连接失败")
            else:
                self.notifier = None
                self.logger.info("ℹ️ Telegram通知已禁用")
            
            # 获取启用的币种
            self.enabled_coins = [
                coin['symbol'] for coin in self.config['coins']
                if coin.get('enabled', True)
            ]
            self.logger.info(f"✅ 监控币种: {', '.join(self.enabled_coins)}")
            
            self.logger.info("="*60)
            self.logger.info("系统初始化完成！")
            self.logger.info("="*60)
        
        except Exception as e:
            self.logger.error(f"❌ 初始化失败: {e}", exc_info=True)
            raise
    
    def _load_config(self, config_file: str) -> dict:
        """加载配置文件"""
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _calculate_strategy_complexity(self) -> dict:
        """计算策略复杂度，评估过拟合风险"""
        strategy = self.config.get('strategy', {})
        
        enabled_features = []
        feature_weights = {
            'use_fear_greed': 5,     # 核心，权重最高
            'use_reversal': 4,       # 拐点确认，非常重要
            'use_funding_percentile': 3,  # 资金费率，中等重要
            'use_longshort': 2,       # 多空比，较低重要
            'use_resonance': 1        # 共振检测，最低重要
        }
        
        if strategy.get('use_fear_greed', True):
            enabled_features.append(('恐慌指数', 5))
        if strategy.get('use_funding_percentile', True):
            enabled_features.append(('资金费率分位', 3))
        if strategy.get('use_longshort', True):
            enabled_features.append(('多空比', 2))
        if strategy.get('use_reversal', True):
            enabled_features.append(('拐点确认', 4))
        if strategy.get('use_resonance', True):
            enabled_features.append(('共振检测', 1))
        
        # 按重要度排序
        enabled_features.sort(key=lambda x: x[1], reverse=True)
        feature_count = len(enabled_features)
        total_weight = sum(w for _, w in enabled_features)
        
        if feature_count >= 5:
            complexity = "极高风险"
            risk_level = 3
            warning = "⚠️ 启用全部条件，严重过度拟合风险！"
        elif feature_count >= 4:
            complexity = "高风险"
            risk_level = 2
            warning = "⚠️ 条件过多，存在过拟合风险"
        elif feature_count >= 3:
            complexity = "中等风险"
            risk_level = 1
            warning = "ℹ️ 策略较为复杂，建议简化"
        else:
            complexity = "低风险"
            risk_level = 0
            warning = "✅ 策略简洁，过拟合风险低"
        
        return {
            'feature_count': feature_count,
            'total_weight': total_weight,
            'enabled_features': enabled_features,
            'complexity': complexity,
            'risk_level': risk_level,
            'warning': warning
        }
    
    def _get_strategy_summary(self) -> str:
        """获取策略摘要"""
        complexity = self._calculate_strategy_complexity()
        
        summary = "\n📊 策略复杂度分析:\n"
        summary += f"  启用条件数: {complexity['feature_count']}/5\n"
        summary += f"  综合权重: {complexity['total_weight']}/15\n"
        summary += f"  风险等级: {complexity['complexity']}\n"
        summary += f"  {complexity['warning']}\n"
        summary += f"  条件: {', '.join([name for name, _ in complexity['enabled_features']])}\n"
        
        return summary
    
    def _setup_logging(self):
        """配置日志系统"""
        log_level = self.config['runtime'].get('log_level', 'INFO')
        log_file = self.config['runtime'].get('log_file', 'monitor.log')
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def collect_market_data(self) -> dict:
        """收集市场数据"""
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info(f"开始收集数据: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("="*60)
        
        # 获取恐慌指数
        fear_greed = self.sentiment_analyzer.get_fear_greed_index()
        if fear_greed:
            self.logger.info(f"恐慌指数: {fear_greed['value']} ({fear_greed['classification']})")
        else:
            self.logger.warning("⚠️ 无法获取恐慌指数")
        
        data = {
            'timestamp': datetime.now(),
            'fear_greed': fear_greed,
            'coins': {}
        }
        
        # 收集每个币种数据
        for symbol in self.enabled_coins:
            self.logger.info(f"收集 {symbol} 数据...")
            
            try:
                price = self.exchange.get_spot_price(symbol)
                funding = self.exchange.get_funding_rate(symbol)
                longshort = self.exchange.get_longshort_ratio(symbol)
                
                data['coins'][symbol] = {
                    'price': price,
                    'funding_rate': funding,
                    'longshort': longshort
                }
                
                if price:
                    self.logger.info(f"  价格: {format_price(price)}")
                if funding is not None:
                    self.logger.info(f"  资金费率: {format_percentage(funding)}")
                if longshort:
                    self.logger.info(f"  多空比: {longshort['ratio']}")
                
                time.sleep(0.5)  # 避免API限流
            
            except Exception as e:
                self.logger.error(f"  ❌ 获取{symbol}数据失败: {e}")
                data['coins'][symbol] = {
                    'price': None,
                    'funding_rate': None,
                    'longshort': None
                }
        
        # 保存到数据库
        try:
            self.db.save_market_data(data)
            self.logger.info("✅ 数据已保存到数据库")
        except Exception as e:
            self.logger.error(f"❌ 保存数据失败: {e}")
        
        return data
    
    def analyze_and_signal(self):
        """分析数据并生成信号"""
        
        # 收集数据
        data = self.collect_market_data()
        
        # 检查止损
        self._check_stop_loss(data)
        
        # 生成信号
        self.logger.info("")
        self.logger.info("开始生成交易信号...")
        
        signals = []
        try:
            signals = self.signal_generator.generate_signals(data)
            
            if signals:
                self.logger.info(f"✅ 生成了 {len(signals)} 个信号")
                
                # 保存信号并处理持仓逻辑
                for signal in signals:
                    try:
                        # 检查是否为加仓机会
                        is_add = False
                        if signal['type'] == 'BUY':
                            pos = self.position_tracker.get_position(signal['coin'])
                            # 如果已有持仓
                            if pos:
                                pyramiding_config = self.config.get('position', {}).get('pyramiding', {})
                                if pyramiding_config.get('enabled', False):
                                    # 检查浮盈是否满足加仓条件
                                    profit_pct = pos.get('return_pct', 0)
                                    min_profit = pyramiding_config.get('min_profit_pct', 5.0)
                                    
                                    if profit_pct >= min_profit:
                                        signal['type'] = 'ADD'  # 升级为加仓信号
                                        signal['reasons'].append(f"浮盈加仓(当前收益{profit_pct:.1f}%)")
                                        is_add = True
                                    else:
                                        # 有持仓但未达到加仓条件，标记为HOLD（仅日志，不存信号库或按需处理）
                                        # 这里选择不保存重复信号，避免干扰
                                        self.logger.info(f"  {signal['coin']} 已有持仓且未达加仓浮盈({profit_pct:.1f}%)，跳过")
                                        continue
                                else:
                                    # 未开启加仓，跳过
                                    self.logger.info(f"  {signal['coin']} 已有持仓，跳过")
                                    continue

                        self.db.save_signal(signal, data)
                        log_icon = "➕" if is_add else " "
                        self.logger.info(
                            f"{log_icon} {signal['coin']} {signal['type']} "
                            f"强度:{signal['strength']} "
                            f"标签:{' '.join(signal['tags'])}"
                        )
                        
                        # 买入或加仓信号时更新持仓
                        if signal['type'] in ['BUY', 'ADD']:
                            price = data['coins'][signal['coin']].get('price')
                            if price:
                                # add_position 内部会自动处理加仓逻辑（更新均价或仅记录）
                                # 目前简单处理：如果是新开仓则添加，如果是加仓也调用add_position刷新止损基准或不做操作
                                # 考虑到 PositionTracker 当前逻辑可能不支持复杂仓位合并，我们暂时只更新追踪
                                if is_add:
                                     # 对于加仓，我们可能希望重置止损线或者更新平均成本
                                     # 简单起见，加仓也是一种"买入"，让 PositionTracker 决定如何处理
                                     # 假设 PositionTracker 目前主要是追踪初始的一笔，这里我们暂不改变持仓成本逻辑
                                     # 仅发送信号。如果需要改成本，需要升级 PositionTracker。
                                     pass 
                                else:
                                    self.position_tracker.add_position(
                                        signal['coin'], 
                                        price, 
                                        signal.get('reasons', [])
                                    )
                    except Exception as e:
                        self.logger.error(f"保存信号失败: {e}")
                
                # 发送Telegram通知
                if self.notifier:
                    message = self._format_message(data, signals)
                    if self.notifier.send(message):
                        self.logger.info("✅ 已发送Telegram通知")
                    else:
                        self.logger.error("❌ Telegram通知发送失败")
            else:
                self.logger.debug("ℹ️ 当前无交易信号")
        
        except Exception as e:
            self.logger.error(f"❌ 信号生成失败: {e}", exc_info=True)
        
        self.logger.info("="*60)
        
        return data, signals
    
    def _check_stop_loss(self, data: dict):
        """检查持仓止损"""
        # 收集当前价格
        prices = {}
        for coin, coin_data in data.get('coins', {}).items():
            price = coin_data.get('price')
            if price:
                prices[coin] = price
        
        if not prices:
            return
        
        # 检查止损触发
        stopped = self.position_tracker.update_prices(prices)
        
        # 发送止损通知
        if stopped and self.notifier:
            for s in stopped:
                msg = (
                    f"🛑 <b>止损触发</b>\n\n"
                    f"币种: {s['coin']}\n"
                    f"买入价: ${s['entry_price']:.2f}\n"
                    f"止损价: ${s['stop_price']:.2f}\n"
                    f"收益: {s['return_pct']:+.1f}%\n"
                    f"最高价: ${s['max_price']:.2f}\n"
                    f"回撤: {s['drawdown']:.1f}%\n\n"
                    f"⚠️ 建议执行止损操作"
                )
                self.notifier.send(msg)
                self.logger.warning(f"🛑 已发送止损通知: {s['coin']}")
    
    def _format_message(self, data: dict, signals: list) -> str:
        """格式化Telegram消息"""
        
        complexity = self._calculate_strategy_complexity()
        risk_emoji = {"极高风险": "🔴", "高风险": "🟠", "中等风险": "🟡", "低风险": "🟢"}
        
        msg = f"<b>🚨 情绪警报 v3.2</b>\n"
        msg += f"⏰ {data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        msg += f"📡 交易所: {self.exchange.name.upper()}\n"
        msg += f"🎯 策略风险: {risk_emoji.get(complexity['complexity'], '⚪')} {complexity['complexity']}\n\n"
        
        # 信号详情
        for signal in signals:
            coin = signal['coin']
            action = "📈 买入" if signal['type'] == 'BUY' else "📉 卖出"
            
            msg += f"<b>{action}信号 - {coin}</b>\n"
            msg += f"强度: {signal['strength']}\n"
            
            # 当前价格
            price = data['coins'][coin].get('price')
            if price:
                msg += f"价格: {format_price(price)}\n"
            
            msg += f"原因:\n"
            for reason in signal['reasons']:
                msg += f"  • {reason}\n"
            
            msg += f"标签: {' '.join(signal['tags'])}\n\n"
        
        # 市场概况
        if data.get('fear_greed'):
            fg = data['fear_greed']
            msg += f"<b>📊 市场概况</b>\n"
            msg += f"恐慌指数: {fg['value']} ({fg['classification']})\n\n"
        
        # 所有币种价格
        msg += f"<b>💰 币种价格</b>\n"
        for symbol, coin_data in data['coins'].items():
            price = coin_data.get('price')
            if price:
                msg += f"{symbol}: {format_price(price)}\n"
        
        return msg
    
    def run(self):
        """运行监控循环"""
        
        interval = self.config['runtime']['check_interval']
        backtest_days = self.config.get('backtest', {}).get('profit_days', [7, 14, 30])
        
        # 计算策略复杂度
        complexity = self._calculate_strategy_complexity()
        strategy_summary = self._get_strategy_summary()
        
        # 发送启动消息
        start_msg = (
            f"🤖 <b>情绪监控系统 v3.2 启动</b>\n\n"
            f"📡 交易所: {self.exchange.name.upper()}\n"
            f"💰 监控币种: {', '.join(self.enabled_coins)}\n"
            f"⏱ 检查间隔: {interval//60}分钟\n"
            f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{strategy_summary}"
        )
        
        if self.notifier:
            self.notifier.send(start_msg)
        
        self.logger.info(start_msg.replace('<b>', '').replace('</b>', ''))
        
        # 警告高风险策略
        if complexity['risk_level'] >= 2:
            self.logger.warning(f"⚠️ 策略风险: {complexity['complexity']} - 建议简化策略参数")
        
        # 主循环
        while True:
            try:
                # 分析并生成信号
                self.analyze_and_signal()
                
                # 执行回测
                self.run_backtest(backtest_days)
                
                # 等待下次检查
                self.logger.info(f"\n⏳ 等待 {interval//60} 分钟后下次检查...\n")
                time.sleep(interval)
            
            except KeyboardInterrupt:
                self.logger.info("\n✋ 收到停止信号")
                if self.notifier:
                    self.notifier.send("🛑 <b>监控系统已停止</b>")
                self.db.close()
                self.logger.info("👋 系统已关闭")
                break
            
            except Exception as e:
                self.logger.error(f"❌ 运行错误: {e}", exc_info=True)
                if self.notifier:
                    self.notifier.send(f"⚠️ <b>系统错误</b>\n<code>{str(e)}</code>")
                
                # 出错后等待5分钟再重试
                self.logger.info("等待5分钟后重试...")
                time.sleep(300)
    
    def run_backtest(self, days_list: list):
        """执行回测任务"""
        signals = self.db.get_pending_backtest_signals(days_list)
        
        if not signals:
            return
        
        self.logger.info(f"开始回测 {len(signals)} 个历史信号...")
        
        for signal in signals:
            try:
                results = self._backtest_signal(signal, days_list)
                if results:
                    self.db.update_backtest_results(signal['id'], results)
                    time.sleep(0.5)
            except Exception as e:
                self.logger.error(f"回测信号失败 ID:{signal['id']} {e}")
    
    def _backtest_signal(self, signal: dict, days_list: list) -> dict:
        """回测单个信号"""
        results = {}
        signal_time = signal['timestamp']
        coin = signal['coin']
        signal_type = signal['type']
        entry_price = signal['price']
        
        if not entry_price:
            return None
        
        for days in days_list:
            target_time = signal_time + timedelta(days=days)
            
            klines = self.exchange.get_historical_klines(
                coin, '1D', target_time - timedelta(hours=1), target_time + timedelta(hours=1)
            )
            
            if klines:
                price_key = f'price_{days}d'
                return_key = f'return_{days}d'
                target_price = klines[-1]['close']
                
                results[price_key] = target_price
                if signal_type == 'BUY':
                    results[return_key] = ((target_price - entry_price) / entry_price) * 100
                else:
                    results[return_key] = ((entry_price - target_price) / entry_price) * 100
        
        if 'return_7d' in results:
            results['is_successful'] = 1 if results['return_7d'] > 0 else 0
        
        return results


def show_statistics():
    """显示统计信息和过拟合警告"""
    import yaml
    from database.manager import DatabaseManager
    from utils.helpers import format_percentage
    
    config_path = Path('config.yaml')
    if not config_path.exists():
        print("❌ 配置文件不存在")
        return
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    db = DatabaseManager(config['runtime']['db_file'])
    stats = db.get_signal_statistics()
    warning_info = db.get_overfitting_warning(stats)
    
    print("\n" + "="*60)
    print("📊 信号回测统计报告")
    print("="*60)
    
    if not stats:
        print("\n暂无回测数据，请先运行系统收集信号")
    else:
        print(f"\n回测周期: 7天收益统计")
        print(f"数据截止: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        for key, s in stats.items():
            coin, sig_type = key.split('_')
            print(f"【{coin} - {sig_type}】")
            print(f"  总信号数: {s['total']}")
            print(f"  盈亏: {s['wins']}胜 / {s['losses']}负")
            print(f"  胜率: {s['win_rate']:.1f}%")
            print(f"  平均收益: {format_percentage(s['avg_return'])}")
            print(f"  最大盈利: {format_percentage(s['max_return'])}")
            print(f"  最大亏损: {format_percentage(s['min_return'])}")
            print(f"  波动率: {s['volatility']:.1f}%")
            print()
        
        print("="*60)
        print("⚠️ 过拟合风险分析")
        print("="*60)
        
        if warning_info['warnings']:
            for w in warning_info['warnings']:
                print(w)
        else:
            print("✅ 未发现明显的过拟合问题")
        
        risk_levels = ["🟢 低风险", "🟡 中风险", "🟠 高风险", "🔴 极高风险"]
        print(f"\n综合风险评级: {risk_levels[min(warning_info['risk_level'], 3)]}")
        
        if warning_info['risk_level'] >= 2:
            print("\n💡 建议:")
            print("  1. 简化策略配置，减少启用条件")
            print("  2. 收集更多样本数据（至少30个）")
            print("  3. 在不同市场环境下测试")
    
    print("="*60 + "\n")
    db.close()

def main():
    """主函数"""
    
    import sys
    
    # 检查是否显示统计
    if len(sys.argv) > 1 and sys.argv[1] == '--stats':
        show_statistics()
        return
    
    print("""
    ╔════════════════════════════════════════════════════╗
    ║   加密货币情绪监控系统 v3.2                        ║
    ║   Crypto Sentiment Monitor                         ║
    ╚════════════════════════════════════════════════════╝
    
    核心特性：
    ✓ 多交易所支持 (OKX / Binance)
    ✓ 灵活币种配置 (BTC/ETH/山寨币)
    ✓ 情绪拐点确认
    ✓ 资金费率分位数
    ✓ 信号共振检测
    ✓ Telegram实时推送
    ✓ SQLite3持久化
    ✓ 模块化架构
    ✓ 历史信号回测
    ✓ 策略复杂度评估
    
    使用方法：
    python main.py          # 启动监控系统
    python main.py --stats  # 查看回测统计和过拟合分析
    
    作者: Claude
    版本: 3.2.0
    日期: 2026-02-03
    """)
    
    try:
        monitor = CryptoSentimentMonitor('config.yaml')
        monitor.run()
    
    except FileNotFoundError as e:
        print(f"\n❌ 错误: {e}")
        print("请确保config.yaml文件存在于当前目录")
    
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()