#!/usr/bin/env python
"""
Test fixed reversal check logic with mock history data
"""

import sys
sys.path.insert(0, '.')

from unittest.mock import patch
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
            'consecutive_periods': 2
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
    print("Test: Fixed Reversal Check with Mock Data")
    print("=" * 60)

    # Test 1: Data insufficient (less than required_periods)
    print("\nTest 1: Insufficient data (< 2 periods)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[{'value': 15, 'timestamp': 1000}]):
        result = sg._check_reversal(20)
        print(f"  History: [15], Current: 20")
        print(f"  Required: {sg.reversal_config.get('consecutive_periods')} periods")
        print(f"  Available: 1 period")
        print(f"  Result: {result}")
        assert result == False, "Should return False with insufficient data"
        print("  PASS: Returns False when data < required_periods")

    # Test 2: consecutive_periods config is now used
    print("\nTest 2: Config parameter is used")
    print(f"  consecutive_periods: {sg.reversal_config.get('consecutive_periods')}")
    assert sg.reversal_config.get('consecutive_periods') == 2, "Should use config value"
    print("  PASS: consecutive_periods is correctly loaded from config")

    # Test 3: Fear reversal - 2 consecutive rises (should return True)
    print("\nTest 3: Fear reversal - 2 consecutive rises (True)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 10, 'timestamp': 1000},
        {'value': 15, 'timestamp': 1001},
        {'value': 20, 'timestamp': 1002},
        {'value': 25, 'timestamp': 1003}
    ]):
        result = sg._check_reversal(28)
        print(f"  History: [10, 15, 20, 25]")
        print(f"  Current: 28")
        print(f"  Check range: history[2]=20, history[3]=25")
        print(f"  All in panic region (<30): True")
        print(f"  20->25 rising: True")
        print(f"  25->28 rising: True")
        print(f"  Result: {result}")
        assert result == True, "Should return True with 2 consecutive rises"
        print("  PASS: Returns True with 2 consecutive rises")

    # Test 4: Fear reversal - descending (should return False)
    print("\nTest 4: Fear reversal - descending pattern (False)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 25, 'timestamp': 1000},
        {'value': 20, 'timestamp': 1001},
        {'value': 18, 'timestamp': 1002},
        {'value': 15, 'timestamp': 1003}
    ]):
        result = sg._check_reversal(20)
        print(f"  History: [25, 20, 18, 15]")
        print(f"  Current: 20")
        print(f"  Check range: history[2]=18, history[3]=15")
        print(f"  All in panic region (<30): True")
        print(f"  18->15 rising: False (18 > 15 is False)")
        print(f"  Result: {result}")
        assert result == False, "Should return False when not rising"
        print("  PASS: Returns False when not consecutive rising")

    # Test 5: Greed reversal - 2 consecutive drops (should return True)
    print("\nTest 5: Greed reversal - 2 consecutive drops (True)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 85, 'timestamp': 1000},
        {'value': 80, 'timestamp': 1001},
        {'value': 75, 'timestamp': 1002},
        {'value': 72, 'timestamp': 1003}
    ]):
        result = sg._check_reversal(68)  # Note: 68 is NOT > 70, so this won't trigger greed reversal
        print(f"  History: [85, 80, 75, 72]")
        print(f"  Current: 68")
        print(f"  Current > 70 (enter greed check): {68 > 70}")
        print(f"  Result: {result}")
        assert result == False, "Should return False because 68 is not > 70"
        print("  PASS: Correctly returns False when current not in greed region")

    # Test 5b: Greed reversal - 2 consecutive drops with current > 70 (True)
    print("\nTest 5b: Greed reversal - 2 consecutive drops with current > 70 (True)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 85, 'timestamp': 1000},
        {'value': 80, 'timestamp': 1001},
        {'value': 75, 'timestamp': 1002},
        {'value': 72, 'timestamp': 1003}
    ]):
        result = sg._check_reversal(71)  # Still > 70, continuing to drop
        print(f"  History: [85, 80, 75, 72]")
        print(f"  Current: 71")
        print(f"  Current > 70 (enter greed check): {71 > 70}")
        print(f"  Check range: history[2]=75, history[3]=72")
        print(f"  All in greed region (>70): True")
        print(f"  75->72 dropping: True")
        print(f"  72->71 dropping: True")
        print(f"  Result: {result}")
        assert result == True, "Should return True with 2 consecutive drops"
        print("  PASS: Returns True with 2 consecutive drops")

    # Test 6: Greed reversal - ascending (should return False)
    print("\nTest 6: Greed reversal - ascending pattern (False)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 72, 'timestamp': 1000},
        {'value': 75, 'timestamp': 1001},
        {'value': 80, 'timestamp': 1002},
        {'value': 85, 'timestamp': 1003}
    ]):
        result = sg._check_reversal(78)
        print(f"  History: [72, 75, 80, 85]")
        print(f"  Current: 78")
        print(f"  Check range: history[2]=80, history[3]=85")
        print(f"  All in greed region (>70): True")
        print(f"  80->85 dropping: False (80 < 85 is False)")
        print(f"  Result: {result}")
        assert result == False, "Should return False when not dropping"
        print("  PASS: Returns False when not consecutive dropping")

    # Test 7: Neutral values don't trigger reversal
    print("\nTest 7: Neutral values don't trigger (False)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 45, 'timestamp': 1000},
        {'value': 50, 'timestamp': 1001},
        {'value': 55, 'timestamp': 1002}
    ]):
        result = sg._check_reversal(52)
        print(f"  History: [45, 50, 55] (neutral 30-70)")
        print(f"  Current: 52 (neutral)")
        print(f"  Current FG < 30: False")
        print(f"  Current FG > 70: False")
        print(f"  Result: {result}")
        assert result == False, "Neutral value should not trigger reversal"
        print("  PASS: Neutral values correctly do not trigger reversal")

    # Test 8: Test with consecutive_periods = 3
    print("\nTest 8: Test with consecutive_periods = 3 (True)")
    config['reversal']['consecutive_periods'] = 3
    sg3 = SignalGenerator(config, db)
    with patch.object(sg3.db, 'get_fear_greed_history', return_value=[
        {'value': 10, 'timestamp': 1000},
        {'value': 15, 'timestamp': 1001},
        {'value': 20, 'timestamp': 1002},
        {'value': 25, 'timestamp': 1003}
    ]):
        result = sg3._check_reversal(28)
        print(f"  consecutive_periods: 3")
        print(f"  History: [10, 15, 20, 25]")
        print(f"  Current: 28")
        print(f"  Check range: history[1]=15, history[2]=20, history[3]=25")
        print(f"  All in panic region (<30): True")
        print(f"  15->20->25->28 all rising: True")
        print(f"  Result: {result}")
        assert result == True, "Should return True with 3 consecutive rises"
        print("  PASS: Works correctly with consecutive_periods=3")

    # Test 9: Disabled reversal
    print("\nTest 9: Disabled reversal check (False)")
    config['reversal']['enabled'] = False
    sg_disabled = SignalGenerator(config, db)
    with patch.object(sg_disabled.db, 'get_fear_greed_history', return_value=[
        {'value': 10, 'timestamp': 1000},
        {'value': 15, 'timestamp': 1001},
        {'value': 20, 'timestamp': 1002},
        {'value': 25, 'timestamp': 1003}
    ]):
        result = sg_disabled._check_reversal(28)
        print(f"  reversal.enabled: False")
        print(f"  Result: {result}")
        assert result == False, "Should return False when disabled"
        print("  PASS: Returns False when reversal is disabled")

    # Test 10: Fear reversal - last history not in panic region
    print("\nTest 10: Fear reversal - history leaves panic region (False)")
    config['reversal']['consecutive_periods'] = 2
    sg10 = SignalGenerator(config, db)
    with patch.object(sg10.db, 'get_fear_greed_history', return_value=[
        {'value': 10, 'timestamp': 1000},
        {'value': 15, 'timestamp': 1001},
        {'value': 20, 'timestamp': 1002},
        {'value': 32, 'timestamp': 1003}
    ]):
        result = sg10._check_reversal(28)
        print(f"  History: [10, 15, 20, 32]")
        print(f"  Current: 28")
        print(f"  History[-1]=32 >= 30: Not in panic region")
        print(f"  Result: {result}")
        assert result == False, "Should return False when last history not in panic"
        print("  PASS: Returns False when history not in panic region")

    # Test 11: Fear reversal - current doesn't rise
    print("\nTest 11: Fear reversal - current doesn't rise (False)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 10, 'timestamp': 1000},
        {'value': 15, 'timestamp': 1001},
        {'value': 20, 'timestamp': 1002},
        {'value': 25, 'timestamp': 1003}
    ]):
        result = sg._check_reversal(22)
        print(f"  History: [10, 15, 20, 25]")
        print(f"  Current: 22")
        print(f"  Check range: history[2]=20, history[3]=25")
        print(f"  20->25 rising: True")
        print(f"  25->22 rising: False (22 <= 25)")
        print(f"  Result: {result}")
        assert result == False, "Should return False when current doesn't rise"
        print("  PASS: Returns False when current doesn't continue the rise")

    # Test 12: Greed reversal - last history not in greed region
    print("\nTest 12: Greed reversal - history leaves greed region (False)")
    with patch.object(sg.db, 'get_fear_greed_history', return_value=[
        {'value': 85, 'timestamp': 1000},
        {'value': 80, 'timestamp': 1001},
        {'value': 75, 'timestamp': 1002},
        {'value': 68, 'timestamp': 1003}
    ]):
        result = sg._check_reversal(65)
        print(f"  History: [85, 80, 75, 68]")
        print(f"  Current: 65")
        print(f"  History[-1]=68 <= 70: Not in greed region")
        print(f"  Result: {result}")
        assert result == False, "Should return False when last history not in greed"
        print("  PASS: Returns False when history not in greed region")

    print("\n" + "=" * 60)
    print("All tests PASSED!")
    print("=" * 60)
    print("\nSummary of the fix:")
    print("  - Now reads consecutive_periods from config")
    print("  - Checks exactly consecutive_periods consecutive changes")
    print("  - All checked values must be in correct region (<30 or >70)")
    print("  - Current value must continue the trend")
    print("  - Works with different consecutive_periods values")
    print("  - Clear logic: check region -> check trend -> check current")
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
