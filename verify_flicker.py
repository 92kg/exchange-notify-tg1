from backtest import EnhancedBacktester
import pandas as pd
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("flicker")

def calculate_ma(prices, period):
    return pd.Series(prices).rolling(window=period).mean()

def run_flicker_analysis():
    print("🔬 Starting Signal Flicker Analysis (Intra-day Fakeouts)")
    print("   Goal: Identify days where High > MA (Triggered) but Close < MA (Failed)")
    print("=" * 70)

    # Use same config as main backtest
    config = {
        'coins': ['BTC', 'ETH', 'SOL'], # Test major coins
        'thresholds': {'fear_buy': 25, 'greed_sell': 75},
        'ma': {'short_period': 7, 'long_period': 30},
    }
    
    tester = EnhancedBacktester(config)
    # Fetch data (will use cache if available)
    tester.fetch_all_data(days=1460)
    
    total_fakeouts = 0
    total_valid = 0
    fakeout_pnl = []
    
    for coin in config['coins']:
        if coin not in tester.price_data:
            continue
            
        data = tester.price_data[coin]
        df = pd.DataFrame(data)
        
        # Calculate Indicators based on Close price
        # IMPORTANT: In a 5-min live loop, if the previous candle closed, the MA is fixed or slowly moving.
        # We simulate the worst case: We decide based on moving MA, but let's approximate with previous day MA stability.
        # A simpler robust check: Price > MA7 AND Price > MA30
        
        df['ma7'] = df['close'].rolling(window=7).mean()
        df['ma30'] = df['close'].rolling(window=30).mean()
        
        # Shift MA to represent "MA at start of day" (based on previous days) 
        # or keep current if we assume live calculation updates.
        # Live script uses CURRENT incomplete candle for MA. 
        # So we keep unshifted MA (approximation of end-of-day value, but Close is used).
        
        flicker_count = 0
        valid_count = 0
        
        print(f"\nAnalyzing {coin}...")
        
        for i in range(30, len(df)):
            row = df.iloc[i]
            
            # 1. Condition Triggered Intra-day?
            # Approximation: High price broke above MAs
            # Note: We use the final MA of the day as a proxy for the 'hurdle'
            ma7 = row['ma7']
            ma30 = row['ma30']
            
            if pd.isna(ma7) or pd.isna(ma30):
                continue
                
            # Simulate "Buy Trigger"
            # Require High to be comfortably above MAs (e.g. valid breakout)
            # Live logic: Price > MA7 and Price > MA30
            
            intra_day_buy = (row['high'] > ma7) and (row['high'] > ma30) and (ma7 > ma30)
            
            # 2. Condition Failed at Close? (The "Flicker")
            # The candle closed below one of the MAs, or MA cross failed
            daily_close_valid = (row['close'] > ma7) and (row['close'] > ma30) and (ma7 > ma30)
            
            if intra_day_buy:
                if daily_close_valid:
                    valid_count += 1
                else:
                    flicker_count += 1
                    # Simulate Loss: Bought at Breakout (MA price), Sold at Close (Fakeout)
                    # Entry: Max(ma7, ma30) (Breakout point)
                    entry_price = max(ma7, ma30)
                    # Or worse: Bought at High (FOMO)
                    # Let's average Entry = Breakout Point
                    if entry_price < row['low']: # Gap up opening
                        entry_price = row['open']
                        
                    exit_price = row['close']
                    pnl = (exit_price - entry_price) / entry_price * 100
                    fakeout_pnl.append(pnl)
                    # print(f"  Flash Buy: Date={row['date']} PnL={pnl:.2f}%")
        
        total_fakeouts += flicker_count
        total_valid += valid_count
        
        print(f"  Valid Days (Close > MAs): {valid_count}")
        print(f"  Fakeout Days (High > MAs > Close): {flicker_count}")
        if valid_count > 0:
            ratio = flicker_count / (valid_count + flicker_count) * 100
            print(f"  Flicker Risk Rate: {ratio:.1f}%")

    print("\n" + "=" * 70)
    print("📉 Flicker Impact Summary")
    print(f"Total Fakeout Trades: {total_fakeouts}")
    if fakeout_pnl:
        avg_loss = sum(fakeout_pnl) / len(fakeout_pnl)
        print(f"Average Fakeout PnL: {avg_loss:.2f}% (Loss due to buying breakout that failed)")
        print(f"Max Fakeout Loss: {min(fakeout_pnl):.2f}%")
    
    print("\n💡 Conclusion:")
    print("If these fakeouts were traded, they would add losses not seen in the daily backtest.")
    print("However, valid trends often generate enough profit to cover these 'whipsaws'.")

if __name__ == "__main__":
    run_flicker_analysis()
