#!/usr/bin/env python3
"""
Test script for the LED Matrix web interface
This script tests the basic functionality of the web interface
"""

import requests
import json
import time
import sys

def test_web_interface():
    """Test the web interface functionality"""
    base_url = "http://localhost:5000"
    
    print("Testing LED Matrix Web Interface...")
    print("=" * 50)
    
    # Test 1: Check if the web interface is running
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("✓ Web interface is running")
        else:
            print(f"✗ Web interface returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to web interface. Is it running?")
        print("  Start it with: python3 web_interface.py")
        return False
    except Exception as e:
        print(f"✗ Error connecting to web interface: {e}")
        return False
    
    # Test 2: Test schedule configuration
    print("\nTesting schedule configuration...")
    schedule_data = {
        'schedule_enabled': 'on',
        'start_time': '08:00',
        'end_time': '22:00'
    }
    
    try:
        response = requests.post(f"{base_url}/save_schedule", data=schedule_data, timeout=10)
        if response.status_code == 200:
            print("✓ Schedule configuration saved successfully")
        else:
            print(f"✗ Schedule configuration failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Error saving schedule: {e}")
    
    # Test 3: Test main configuration save
    print("\nTesting main configuration save...")
    test_config = {
        "weather": {
            "enabled": True,
            "units": "imperial",
            "update_interval": 1800
        },
        "location": {
            "city": "Test City",
            "state": "Test State"
        }
    }
    
    try:
        response = requests.post(f"{base_url}/save_config", data={
            'config_type': 'main',
            'config_data': json.dumps(test_config)
        }, timeout=10)
        if response.status_code == 200:
            print("✓ Main configuration saved successfully")
        else:
            print(f"✗ Main configuration failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Error saving main config: {e}")
    
    # Test 4: Test secrets configuration save
    print("\nTesting secrets configuration save...")
    test_secrets = {
        "weather": {
            "api_key": "test_api_key_123"
        },
        "youtube": {
            "api_key": "test_youtube_key",
            "channel_id": "test_channel"
        },
        "music": {
            "SPOTIFY_CLIENT_ID": "test_spotify_id",
            "SPOTIFY_CLIENT_SECRET": "test_spotify_secret",
            "SPOTIFY_REDIRECT_URI": "http://127.0.0.1:8888/callback"
        }
    }
    
    try:
        response = requests.post(f"{base_url}/save_config", data={
            'config_type': 'secrets',
            'config_data': json.dumps(test_secrets)
        }, timeout=10)
        if response.status_code == 200:
            print("✓ Secrets configuration saved successfully")
        else:
            print(f"✗ Secrets configuration failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Error saving secrets: {e}")
    
    # Test 5: Test action execution
    print("\nTesting action execution...")
    try:
        response = requests.post(f"{base_url}/run_action", 
                               json={'action': 'git_pull'}, 
                               timeout=15)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Action executed: {result.get('status', 'unknown')}")
            if result.get('stderr'):
                print(f"  Note: {result['stderr']}")
        else:
            print(f"✗ Action execution failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Error executing action: {e}")
    
    print("\n" + "=" * 50)
    print("Web interface testing completed!")
    print("\nTo start the web interface:")
    print("1. Make sure you're on the Raspberry Pi")
    print("2. Run: python3 web_interface.py")
    print("3. Open a web browser and go to: http://[PI_IP]:5000")
    print("\nFeatures available:")
    print("- Schedule configuration")
    print("- Display hardware settings")
    print("- Sports team configuration")
    print("- Weather settings")
    print("- Stocks & crypto configuration")
    print("- Music settings")
    print("- Calendar configuration")
    print("- API key management")
    print("- System actions (start/stop display, etc.)")
    
    return True

if __name__ == "__main__":
    success = test_web_interface()
    sys.exit(0 if success else 1) 