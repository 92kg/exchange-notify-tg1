
import logging
from unittest.mock import MagicMock
from main import CryptoSentimentMonitor

# Setup logging
logging.basicConfig(level=logging.INFO)

# Config with pyramiding enabled
config = {
    'exchange': {'name': 'okx'},
    'coins': [{'symbol': 'BTC', 'enabled': True}],
    'position': {
        'pyramiding': {
            'enabled': True,
            'min_profit_pct': 5.0
        }
    },
    'risk': {'stop_loss_type': 'trailing', 'stop_loss_pct': -15},
    'telegram': {'enabled': False}, # Disable telegram for test
    'runtime': {'db_file': ':memory:'}, # Use memory db
    # Minimal other configs
    'thresholds': {'fear_buy': 20, 'greed_sell': 80},
    'resonance': {'enabled': False},
    'reversal': {'enabled': False},
    'ma': {'enabled': False}
}

def mock_load_config(self, file):
    return config

print("Testing Pyramiding Logic...")

# Mock methods
CryptoSentimentMonitor._load_config = mock_load_config
CryptoSentimentMonitor._setup_logging = MagicMock()
monitor = CryptoSentimentMonitor()

# Mock dependencies
monitor.db = MagicMock()
monitor.exchange = MagicMock()
monitor.sentiment_analyzer = MagicMock()
monitor.signal_generator = MagicMock()
monitor.signal_generator.generate_signals.return_value = [{'coin': 'BTC', 'type': 'BUY', 'strength': 5, 'tags': [], 'reasons': ['Test']}]
monitor.collect_market_data = MagicMock(return_value={
    'coins': {'BTC': {'price': 100000}}, 
    'timestamp': 1234567890
})
monitor._check_stop_loss = MagicMock()

# 1. Test First BUY (No position)
print("\n[Test 1] Initial BUY (No position)")
monitor.position_tracker.get_position = MagicMock(return_value=None)
monitor.analyze_and_signal()
# 期望：保存信号，add_position被调用
print("Signals saved:", monitor.db.save_signal.call_count)
# We expect 1 call.
if monitor.db.save_signal.call_count == 1:
    args = monitor.db.save_signal.call_args[0]
    print(f"Signal Type: {args[0]['type']}") # Should be BUY

# 2. Test HOLD (Position exists but low profit)
print("\n[Test 2] HOLD (Position exists, Profit 2% < 5%)")
monitor.db.save_signal.reset_mock()
monitor.position_tracker.get_position = MagicMock(return_value={'coin': 'BTC', 'return_pct': 2.0})
monitor.analyze_and_signal()
# 期望：跳过，不保存信号
print("Signals saved:", monitor.db.save_signal.call_count)

# 3. Test ADD (Position exists, Profit 10% > 5%)
print("\n[Test 3] ADD (Position exists, Profit 10% > 5%)")
monitor.db.save_signal.reset_mock()
monitor.position_tracker.get_position = MagicMock(return_value={'coin': 'BTC', 'return_pct': 10.0})
monitor.analyze_and_signal()
# 期望：保存信号，类型为 ADD
print("Signals saved:", monitor.db.save_signal.call_count)
if monitor.db.save_signal.call_count == 1:
    args = monitor.db.save_signal.call_args[0]
    print(f"Signal Type: {args[0]['type']}") # Should be ADD
