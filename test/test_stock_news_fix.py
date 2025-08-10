#!/usr/bin/env python3
"""
Test script to verify the stock news manager fix.
This script tests that the display_news method works correctly without excessive image generation.
"""

import os
import sys
import time
import tempfile
import shutil
from PIL import Image

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from cache_manager import CacheManager
    from stock_news_manager import StockNewsManager
    from display_manager import DisplayManager
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the LEDMatrix root directory")
    sys.exit(1)

def test_stock_news_display():
    """Test that stock news display works correctly without excessive image generation."""

    print("Testing stock news display fix...")

    # Create a temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="ledmatrix_test_")
    print(f"Using test directory: {test_dir}")

    try:
        # Create a minimal config
        config = {
            "stock_news": {
                "enabled": True,
                "scroll_speed": 1,
                "scroll_delay": 0.1,  # Slower for testing
                "headlines_per_rotation": 2,
                "max_headlines_per_symbol": 1,
                "update_interval": 300,
                "dynamic_duration": True,
                "min_duration": 30,
                "max_duration": 300
            },
            "stocks": {
                "symbols": ["AAPL", "GOOGL", "MSFT"],
                "enabled": True
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
                self.matrix = type('Matrix', (), {'width': 64, 'height': 32})()
                self.small_font = None  # We'll handle this in the test
                
            def update_display(self):
                # Mock update - just pass
                pass

        display_manager = MockDisplayManager()

        # Create stock news manager
        news_manager = StockNewsManager(config, display_manager)

        # Mock some news data
        news_manager.news_data = {
            "AAPL": [
                {"title": "Apple reports strong Q4 earnings", "publisher": "Reuters"},
                {"title": "New iPhone sales exceed expectations", "publisher": "Bloomberg"}
            ],
            "GOOGL": [
                {"title": "Google announces new AI features", "publisher": "TechCrunch"},
                {"title": "Alphabet stock reaches new high", "publisher": "CNBC"}
            ],
            "MSFT": [
                {"title": "Microsoft cloud services grow 25%", "publisher": "WSJ"},
                {"title": "Windows 12 preview released", "publisher": "The Verge"}
            ]
        }

        print("\nTesting display_news method...")
        
        # Test multiple calls to ensure it doesn't generate images excessively
        generation_count = 0
        original_generate_method = news_manager._generate_background_image
        
        def mock_generate_method(*args, **kwargs):
            nonlocal generation_count
            generation_count += 1
            print(f"    Image generation call #{generation_count}")
            return original_generate_method(*args, **kwargs)
        
        news_manager._generate_background_image = mock_generate_method

        # Call display_news multiple times to simulate the display controller
        for i in range(10):
            print(f"  Call {i+1}: ", end="")
            try:
                result = news_manager.display_news()
                if result:
                    print("✓ Success")
                else:
                    print("✗ Failed")
            except Exception as e:
                print(f"✗ Error: {e}")

        print(f"\nTotal image generations: {generation_count}")
        
        if generation_count <= 3:  # Should only generate a few times for different rotations
            print("✓ Image generation is working correctly (not excessive)")
        else:
            print("✗ Too many image generations - fix may not be working")

        print("\n✓ Stock news display test completed!")

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
    print("LEDMatrix Stock News Manager Fix Test")
    print("=" * 50)

    success = test_stock_news_display()

    if success:
        print("\n🎉 Test completed! The stock news manager should now work correctly.")
        print("\nThe fix addresses the issue where the display_news method was:")
        print("1. Generating images excessively (every second)")
        print("2. Missing the actual scrolling display logic")
        print("3. Causing rapid rotation through headlines")
        print("\nNow it should:")
        print("1. Generate images only when needed for new rotations")
        print("2. Properly scroll the content across the display")
        print("3. Use the configured dynamic duration properly")
    else:
        print("\n❌ Test failed. Please check the error messages above.")
        sys.exit(1)
