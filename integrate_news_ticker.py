#!/usr/bin/env python3
import time
import sys
import os
from src.config_manager import ConfigManager
from src.display_manager import DisplayManager
from src.stock_news_manager import StockNewsManager
from src.stock_manager import StockManager

def main():
    """Integrate news ticker with the existing display system."""
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.config
        
        # Initialize display manager
        display_manager = DisplayManager(config.get('display', {}))
        
        # Initialize stock manager
        stock_manager = StockManager(config, display_manager)
        
        # Initialize news manager
        news_manager = StockNewsManager(config, display_manager)
        
        print("News ticker integration test started. Press Ctrl+C to exit.")
        print("Displaying stock data and news headlines...")
        
        # Display stock data and news headlines in a loop
        while True:
            # Display stock data
            stock_manager.display_stocks()
            
            # Display news headlines for a limited time (30 seconds)
            start_time = time.time()
            while time.time() - start_time < 30:
                news_manager.display_news()
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        if 'display_manager' in locals():
            display_manager.clear()
            display_manager.update_display()
            display_manager.cleanup()

if __name__ == "__main__":
    main() 