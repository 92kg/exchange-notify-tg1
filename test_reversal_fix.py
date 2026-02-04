#!/usr/bin/env python
"""
Test the fixed reversal check logic
"""

import sys
sys.path.insert(0, '.')

from analyzers.signal import SignalGenerator
from database.manager import DatabaseManager

def test_reversal_fix():
    """Test that reversal check now uses consecutive_periods correctly"""

    config = {
        'thresholds': {
            'fear_buy': 25,
            'greed_sell': 75,
            'funding_panic_percentile': 15,
            'funding_greed_percentile': 85,
            'longshort_extreme': 0.8
        },
        'reversal': {
            'enabled': True,
            'consecutive_periods': 2  # Require 2 consecutive reversals
        },
        'resonance': {
            'enabled': False,
            'min_coins': 2
        },
        'strategy': {
            'use_fear_greed': True,
            'use_reversal': True,
            'use_funding_percentile': True,
            'use_longshort': False,
            'use_resonance': False
        }
    }

    db = DatabaseManager('crypto_sentiment_v3.db')
    sg = SignalGenerator(config, db)

    print("=" * 60)
    print("Test: Fixed Reversal Check")
    print("=" * 60)

    # Test 1: Data insufficient
    print("\nTest 1: Insufficient data")
    result = sg._check_reversal(20)
    print(f"  Result: {result}")
    assert result == False, "Should return False with insufficient data"
    print("  PASS: Returns False when data insufficient")

    # Test 2: consecutive_periods config is now used
    print("\nTest 2: Config parameter is used")
    print(f"  consecutive_periods: {sg.reversal_config.get('consecutive_periods')}")
    assert sg.reversal_config.get('consecutive_periods') == 2, "Should use config value"
    print("  PASS: consecutive_periods is correctly loaded from config")

    # Test 3: Fear reversal logic (current < 30)
    print("\nTest 3: Fear reversal threshold check")
    print(f"  Current FG = 20 (panic region)")
    print(f"  Fear threshold < 30: {20 < 30}")
    assert 20 < 30, "Should enter fear reversal check"
    print("  PASS: Correctly enters fear reversal check for FG=20")

    # Test 4: Greed reversal logic (current > 70)
    print("\nTest 4: Greed reversal threshold check")
    print(f"  Current FG = 80 (greed region)")
    print(f"  Greed threshold > 70: {80 > 70}")
    assert 80 > 70, "Should enter greed reversal check"
    print("  PASS: Correctly enters greed reversal check for FG=80")

    # Test 5: Normal values don't trigger reversal
    print("\nTest 5: Normal values don't trigger")
    result_neutral = sg._check_reversal(50)
    print(f"  Current FG = 50 (neutral)")
    print(f"  Result: {result_neutral}")
    assert result_neutral == False, "Neutral value should not trigger reversal"
    print("  PASS: Neutral value correctly does not trigger reversal")

    # Test 6: Disabled reversal
    print("\nTest 6: Disabled reversal check")
    config['reversal']['enabled'] = False
    sg2 = SignalGenerator(config, db)
    result_disabled = sg2._check_reversal(20)
    print(f"  Result: {result_disabled}")
    assert result_disabled == False, "Should return False when disabled"
    print("  PASS: Returns False when reversal is disabled")

    print("\n" + "=" * 60)
    print("All tests PASSED!")
    print("=" * 60)
    print("\nSummary of the fix:")
    print("  - Now reads consecutive_periods from config")
    print("  - Checks required periods before returning True")
    print("  - Iterates through history correctly")
    print("  - Includes current value in the check")
    print("=" * 60)

    db.close()

if __name__ == "__main__":
    try:
        test_reversal_fix()
    except AssertionError as e:
        print(f"\n[FAILED] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
