
import sys
import statistics
import logging
from backtest import EnhancedBacktester

# Configure logging to silence standard output
logging.basicConfig(level=logging.WARNING)

print('Running detailed analysis...')
config = {
    'thresholds': {'fear_buy': 15, 'greed_sell': 75},
    'reversal': {'enabled': True, 'consecutive_periods': 2},
    'ma': {'enabled': True, 'short_period': 7, 'long_period': 30},
    'filters': {'max_drop_7d': -30, 'require_price_recovery': True},
    'coins': ['BTC', 'ETH'],
    'hold_days': [30],
}

backtester = EnhancedBacktester(config)
backtester.fetch_all_data(2000)
backtester.simulate_signals()

def analyze_distribution(data, name):
    if not data:
        print(f"\n[{name}] No data")
        return
        
    print(f'\n[{name}] Analysis ({len(data)} signals)')
    print(f'Max Return: {max(data):.2f}%')
    print(f'Min Return: {min(data):.2f}%')
    print(f'Mean: {statistics.mean(data):.2f}%')
    print(f'Median: {statistics.median(data):.2f}%')
    
    buckets = {'<-20%': 0, '-20% to 0%': 0, '0% to 20%': 0, '20% to 50%': 0, '>50%': 0}
    for ret in data:
        if ret < -20: buckets['<-20%'] += 1
        elif ret < 0: buckets['-20% to 0%'] += 1
        elif ret < 20: buckets['0% to 20%'] += 1
        elif ret < 50: buckets['20% to 50%'] += 1
        else: buckets['>50%'] += 1
        
    print('Distribution:')
    for k, v in buckets.items():
        print(f'  {k}: {v} ({v/len(data)*100:.1f}%)')

# 1. 原始策略 (持有30天)
returns_raw = []
for signal in backtester.signals:
    if signal['type'] != 'BUY': continue
    price_30d = backtester._get_price_after_days(signal['coin'], signal['date'], 30)
    if price_30d:
        ret = (price_30d - signal['price']) / signal['price'] * 100
        returns_raw.append(ret)

# 2. 动态止损策略 (Trailing -15%)
returns_trailing = []
trailing_pct = -15

for signal in backtester.signals:
    if signal['type'] != 'BUY': continue
    
    buy_price = signal['price']
    max_price = buy_price
    exit_price = None
    
    # 模拟30天内的每一天
    for day in range(1, 31):
        curr_price = backtester._get_price_after_days(signal['coin'], signal['date'], day)
        if not curr_price: continue
        
        # 更新最高价
        max_price = max(max_price, curr_price)
        
        # 计算动态止损线
        stop_price = max_price * (1 + trailing_pct / 100)
        
        # 检查是否触发
        if curr_price <= stop_price:
            exit_price = curr_price  # 触发止损/止盈
            break
            
    # 如果没触发，按30天价格卖出
    if exit_price is None:
        exit_price = backtester._get_price_after_days(signal['coin'], signal['date'], 30)
        
    if exit_price:
        ret = (exit_price - buy_price) / buy_price * 100
        returns_trailing.append(ret)

# 对比输出
analyze_distribution(returns_raw, "Original (Hold 30d)")
analyze_distribution(returns_trailing, "Trailing Stop (-15%)")
