from backtest import EnhancedBacktester
import json
import logging

# Configure logging to suppress verbose output, show only essential info
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("backtest")

def run_backtest():
    # Configuration for long-term multi-coin backtest
    config = {
        'thresholds': {
            'fear_buy': 25, 
            'greed_sell': 75
        },
        'reversal': {
            'enabled': True, 
            'consecutive_periods': 2
        },
        'ma': {
            'enabled': True, 
            'short_period': 7, 
            'long_period': 30
        },
        'filters': {
            'max_drop_7d': -30, 
            'require_price_recovery': True
        },
        'coins': ['BTC', 'ETH', 'SOL', 'BNB', 'DOGE', 'XRP', 'ADA'],
        'hold_days': [7, 14, 30],
        'use_sell_signal': False,
        'risk': {
            'stop_loss_type': 'trailing',
            'stop_loss_pct': -15
        },
        'position': {}
    }

    print(f"🚀 Starting 4-Year Historical Backtest (1460 days)")
    print(f"   Coins: {', '.join(config['coins'])}")
    print(f"   Strategy: V8 Trend (Price > MA7 > MA30, FG < 70)")
    print(f"   Stop Loss: Trailing 15%")
    print("=" * 60)

    tester = EnhancedBacktester(config)
    
    # Run backtest for 4 years (1460 days)
    report = tester.run(days=1460)
    
    # Simplify and save report
    if report:
        output_file = 'backtest_historical_result.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Detailed results saved to {output_file}")

if __name__ == "__main__":
    run_backtest()
