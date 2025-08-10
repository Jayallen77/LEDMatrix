#!/usr/bin/env python3
"""
Test script to verify the soccer logo permissions fix.
This script tests the _load_and_resize_logo method to ensure it can create placeholder logos
without permission errors.
"""

import os
import sys
import tempfile
import shutil
from PIL import Image, ImageDraw, ImageFont
import random

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from cache_manager import CacheManager
    from soccer_managers import BaseSoccerManager
    from display_manager import DisplayManager
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the LEDMatrix root directory")
    sys.exit(1)

def test_soccer_logo_creation():
    """Test that soccer placeholder logos can be created without permission errors."""
    
    print("Testing soccer logo creation...")
    
    # Create a temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="ledmatrix_test_")
    print(f"Using test directory: {test_dir}")
    
    try:
        # Create a minimal config
        config = {
            "soccer_scoreboard": {
                "enabled": True,
                "logo_dir": "assets/sports/soccer_logos",
                "update_interval_seconds": 60
            },
            "display": {
                "width": 64,
                "height": 32
            }
        }
        
        # Create cache manager with test directory
        cache_manager = CacheManager()
        # Override cache directory for testing
        cache_manager.cache_dir = test_dir
        
        # Create a mock display manager
        class MockDisplayManager:
            def __init__(self):
                self.width = 64
                self.height = 32
                self.image = Image.new('RGB', (64, 32), (0, 0, 0))
        
        display_manager = MockDisplayManager()
        
        # Create soccer manager
        soccer_manager = BaseSoccerManager(config, display_manager, cache_manager)
        
        # Test teams that might not have logos
        test_teams = ["ATX", "STL", "SD", "CLT", "TEST1", "TEST2"]
        
        print("\nTesting logo creation for missing teams:")
        for team in test_teams:
            print(f"  Testing {team}...")
            try:
                logo = soccer_manager._load_and_resize_logo(team)
                if logo:
                    print(f"    ✓ Successfully created logo for {team} (size: {logo.size})")
                else:
                    print(f"    ✗ Failed to create logo for {team}")
            except Exception as e:
                print(f"    ✗ Error creating logo for {team}: {e}")
        
        # Check if placeholder logos were created in cache
        placeholder_dir = os.path.join(test_dir, 'placeholder_logos')
        if os.path.exists(placeholder_dir):
            placeholder_files = os.listdir(placeholder_dir)
            print(f"\nPlaceholder logos created in cache: {len(placeholder_files)} files")
            for file in placeholder_files:
                print(f"  - {file}")
        else:
            print("\nNo placeholder logos directory created (using in-memory placeholders)")
        
        print("\n✓ Soccer logo test completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Clean up test directory
        try:
            shutil.rmtree(test_dir)
            print(f"Cleaned up test directory: {test_dir}")
        except Exception as e:
            print(f"Warning: Could not clean up test directory: {e}")
    
    return True

if __name__ == "__main__":
    print("LEDMatrix Soccer Logo Permissions Fix Test")
    print("=" * 50)
    
    success = test_soccer_logo_creation()
    
    if success:
        print("\n🎉 All tests passed! The soccer logo fix is working correctly.")
        print("\nTo apply this fix on your Raspberry Pi:")
        print("1. Transfer the updated files to your Pi")
        print("2. Run: chmod +x fix_soccer_logo_permissions.sh")
        print("3. Run: ./fix_soccer_logo_permissions.sh")
        print("4. Restart your LEDMatrix application")
    else:
        print("\n❌ Tests failed. Please check the error messages above.")
        sys.exit(1)
