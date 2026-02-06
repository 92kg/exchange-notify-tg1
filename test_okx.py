
import yaml
from exchanges.okx import OKXExchange

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def test_okx():
    print("Testing OKX API...")
    config = load_config()
    
    # 打印部分 key 确认加载正确
    api_key = config['exchange'].get('api_key', '')
    if api_key:
        print(f"API Key loaded: {api_key[:4]}...{api_key[-4:]}")
    else:
        print("API Key NOT loaded!")
        
    exchange = OKXExchange(config['exchange'])
    
    # 1. Test Public API (Ticker)
    print("\n1. Testing Public API (Ticker)...")
    price = exchange.get_spot_price("BTC")
    if price:
        print(f"✅ BTC Price: ${price}")
    else:
        print("❌ Failed to get BTC price")

    # 2. Test Private API (Positions)
    print("\n2. Testing Private API (Positions)...")
    positions = exchange.get_positions()
    
    if positions is not None:
        print(f"✅ Positions API call successful. Found {len(positions)} positions.")
        for p in positions:
            print(f"  - {p['symbol']} ({p['side']}): {p['size']} @ {p['entry_price']} (PnL: {p['pnl_ratio']:.2f}%)")
    else:
        print("❌ Failed to get positions. Check API Key/Secret/Passphrase and Signature logic.")

if __name__ == "__main__":
    test_okx()
