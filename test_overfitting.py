#!/usr/bin/env python
"""
测试过拟合检测功能
"""

import sys
sys.path.insert(0, '.')

from database.manager import DatabaseManager
from utils.helpers import format_percentage

def test_overfitting_detection():
    """测试过拟合检测"""
    
    db = DatabaseManager('crypto_sentiment_v3.db')
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

if __name__ == "__main__":
    from datetime import datetime
    test_overfitting_detection()
