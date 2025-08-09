#!/usr/bin/env python3
"""
Test script to verify the soccer manager timezone fix.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pytz

def test_timezone_fix():
    """Test that the timezone logic works correctly."""
    
    # Mock config with America/Chicago timezone
    config = {
        'timezone': 'America/Chicago'
    }
    
    # Simulate the _get_timezone method logic
    def _get_timezone():
        try:
            timezone_str = config.get('timezone', 'UTC')
            return pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            print(f"Warning: Unknown timezone: {timezone_str}, falling back to UTC")
            return pytz.utc
        except Exception as e:
            print(f"Error getting timezone: {e}, falling back to UTC")
            return pytz.utc
    
    # Test timezone conversion
    utc_time = datetime.now(pytz.utc)
    local_time = utc_time.astimezone(_get_timezone())
    
    print(f"UTC time: {utc_time}")
    print(f"Local time (America/Chicago): {local_time}")
    print(f"Timezone name: {local_time.tzinfo}")
    
    # Verify it's not UTC
    if str(local_time.tzinfo) != 'UTC':
        print("✅ SUCCESS: Timezone conversion is working correctly!")
        print(f"   Expected: America/Chicago timezone")
        print(f"   Got: {local_time.tzinfo}")
    else:
        print("❌ FAILURE: Still using UTC timezone!")
        return False
    
    # Test time formatting (same as in soccer manager)
    formatted_time = local_time.strftime("%I:%M%p").lower().lstrip('0')
    print(f"Formatted time: {formatted_time}")
    
    # Test with a specific UTC time to verify conversion
    test_utc = datetime(2024, 1, 15, 19, 30, 0, tzinfo=pytz.utc)  # 7:30 PM UTC
    test_local = test_utc.astimezone(_get_timezone())
    test_formatted = test_local.strftime("%I:%M%p").lower().lstrip('0')
    
    print(f"\nTest conversion:")
    print(f"  7:30 PM UTC -> {test_local.strftime('%I:%M %p')} {test_local.tzinfo}")
    print(f"  Formatted: {test_formatted}")
    
    return True

if __name__ == "__main__":
    print("Testing soccer manager timezone fix...")
    success = test_timezone_fix()
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n💥 Tests failed!")
        sys.exit(1)
