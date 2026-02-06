
import logging
from datetime import datetime
from main import CryptoSentimentMonitor

# Setup logging
logging.basicConfig(level=logging.INFO)

# Config with telegram enabled (but using fake token for dry run format check if verify=False)
# However, user wants to see the logic. We will mock the notifier.send to print the message.
print("Testing Notification Format...")

config = {
    'exchange': {'name': 'okx'},
    'coins': [{'symbol': 'BTC', 'enabled': True}],
    'risk': {'stop_loss_pct': -15},
    'runtime': {'db_file': ':memory:'},
    'telegram': {'enabled': True, 'bot_token': 'test', 'chat_id': 'test'},
    'thresholds': {'fear_buy': 20},'reversal':{'enabled':False},'ma':{'enabled':False}
}

class MockNotifier:
    def send(self, msg):
        print("\n[TELEGRAM MESSAGE PREVIEW]")
        print("-" * 40)
        print(msg)
        print("-" * 40)
        return True

monitor = CryptoSentimentMonitor()
monitor.config = config
monitor.notifier = MockNotifier()
monitor.exchange.name = "okx"

# Mock Data
data = {
    'timestamp': datetime.now(),
    'coins': {'BTC': {'price': 65000}},
    'fear_greed': {'value': 20, 'classification': 'Extreme Fear'}
}

signals = [
    {
        'coin': 'BTC',
        'type': 'BUY',
        'strength': 5,
        'tags': ['Test'],
        'reasons': ['Panic Buy']
    }
]

# Run format
msg = monitor._format_message(data, signals)
monitor.notifier.send(msg)
