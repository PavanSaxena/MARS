"""
Test TPM Tracking Implementation

Verifies that the TPM tracker correctly:
1. Tracks token usage in a rolling 60-second window
2. Calculates wait times when budget would be exceeded
3. Prunes old records
4. Provides accurate usage statistics
"""

import time
from app.llm.tpm_tracker import TPMTracker


def test_basic_tracking():
    """Test basic token tracking"""
    print("\n" + "="*60)
    print("Test 1: Basic Token Tracking")
    print("="*60)
    
    tracker = TPMTracker(tpm_budget=10000)
    
    # Record some usage
    tracker.record_usage(1000, 2000)  # 3000 tokens
    tracker.record_usage(1500, 2500)  # 4000 tokens
    
    current_usage = tracker.get_current_usage()
    remaining = tracker.get_remaining_budget()
    
    print(f"Current Usage: {current_usage}")
    print(f"Remaining Budget: {remaining}")
    print(f"Expected Usage: 7000")
    print(f"Expected Remaining: 3000")
    
    assert current_usage == 7000, f"Expected 7000, got {current_usage}"
    assert remaining == 3000, f"Expected 3000, got {remaining}"
    print("✓ Basic tracking works correctly")


def test_budget_checking():
    """Test budget checking logic"""
    print("\n" + "="*60)
    print("Test 2: Budget Checking")
    print("="*60)
    
    tracker = TPMTracker(tpm_budget=10000)
    
    # Use 8000 tokens
    tracker.record_usage(3000, 5000)
    
    # Check if 3000 more would exceed (should exceed)
    would_exceed = tracker.would_exceed_budget(1000, 2000)
    print(f"Would 3000 more tokens exceed budget? {would_exceed}")
    print(f"Current usage: {tracker.get_current_usage()}")
    print(f"Expected: True (8000 + 3000 = 11000 > 10000)")
    
    assert would_exceed, "Should detect budget would be exceeded"
    print("✓ Budget checking works correctly")


def test_wait_time_calculation():
    """Test wait time calculation"""
    print("\n" + "="*60)
    print("Test 3: Wait Time Calculation")
    print("="*60)
    
    tracker = TPMTracker(tpm_budget=10000)
    
    # Use 8000 tokens
    tracker.record_usage(3000, 5000)
    
    # Calculate wait time for 3000 more tokens
    wait_time = tracker.calculate_wait_time(1000, 2000)
    print(f"Wait time needed: {wait_time:.2f} seconds")
    print(f"Expected: ~60 seconds (need oldest record to age out)")
    
    assert wait_time > 0, "Should require waiting"
    assert wait_time <= 60, "Wait time should not exceed window size"
    print("✓ Wait time calculation works correctly")


def test_rolling_window():
    """Test rolling window pruning"""
    print("\n" + "="*60)
    print("Test 4: Rolling Window Pruning")
    print("="*60)
    
    tracker = TPMTracker(tpm_budget=10000)
    
    # Record usage
    tracker.record_usage(1000, 2000)
    print(f"Initial usage: {tracker.get_current_usage()}")
    
    # Wait 2 seconds and record more
    time.sleep(2)
    tracker.record_usage(1000, 2000)
    print(f"After 2s, usage: {tracker.get_current_usage()}")
    
    # Both records should still be in window
    assert tracker.get_current_usage() == 6000, "Both records should be counted"
    print("✓ Rolling window maintains recent records")


def test_no_wait_when_budget_available():
    """Test that no wait is needed when budget is available"""
    print("\n" + "="*60)
    print("Test 5: No Wait When Budget Available")
    print("="*60)
    
    tracker = TPMTracker(tpm_budget=10000)
    
    # Use only 3000 tokens
    tracker.record_usage(1000, 2000)
    
    # Check if 3000 more would exceed (should not)
    would_exceed = tracker.would_exceed_budget(1000, 2000)
    wait_time = tracker.calculate_wait_time(1000, 2000)
    
    print(f"Would 3000 more tokens exceed budget? {would_exceed}")
    print(f"Wait time: {wait_time}")
    print(f"Current usage: {tracker.get_current_usage()}")
    
    assert not would_exceed, "Should not exceed budget"
    assert wait_time == 0, "Should not need to wait"
    print("✓ No wait needed when budget available")


def test_usage_stats():
    """Test usage statistics"""
    print("\n" + "="*60)
    print("Test 6: Usage Statistics")
    print("="*60)
    
    tracker = TPMTracker(tpm_budget=10000)
    
    # Record usage
    tracker.record_usage(2000, 3000)  # 5000 tokens
    
    stats = tracker.get_usage_stats()
    print(f"Stats: {stats}")
    
    assert stats['rolling_tpm_usage'] == 5000
    assert stats['tpm_budget'] == 10000
    assert stats['remaining_budget'] == 5000
    assert stats['utilization_percent'] == 50.0
    assert stats['records_in_window'] == 1
    print("✓ Usage statistics are accurate")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TPM Tracker Test Suite")
    print("="*60)
    
    try:
        test_basic_tracking()
        test_budget_checking()
        test_wait_time_calculation()
        test_rolling_window()
        test_no_wait_when_budget_available()
        test_usage_stats()
        
        print("\n" + "="*60)
        print("✓ All TPM Tracker Tests Passed")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n✗ Test Failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())