#!/usr/bin/env python3
import time
import sys
import os
from src.config_manager import ConfigManager
from src.display_manager import DisplayManager
from src.stock_news_manager import StockNewsManager

print(f"Current working directory: {os.getcwd()}")

def main():
    """Test the StockNewsManager class directly."""
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        if not config:
            print("Error: Failed to load configuration")
            return
            
        display_config = config.get('display')
        if not display_config:
            print("Error: No display configuration found")
            return
        
        # Initialize display manager
        display_manager = DisplayManager(display_config)
        
        # Initialize news manager with the loaded config
        news_manager = StockNewsManager(config, display_manager)
        
        print("Testing news display. Press Ctrl+C to exit.")
        
        # Run the news display in a loop
        while True:
            news_manager.display_news()
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Test completed")

if __name__ == "__main__":
    main() 