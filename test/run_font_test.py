#!/usr/bin/env python3
import sys
import os
import time
import json
import logging

# Add the parent directory to the Python path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.display_manager import DisplayManager
from src.font_test_manager import FontTestManager
from src.config_manager import ConfigManager

# Configure logging to match main application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    """Run the font test display."""
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize display manager
        display_manager = DisplayManager(config)
        
        # Initialize font test manager
        font_test_manager = FontTestManager(config, display_manager)
        
        logger.info("Starting static font test display. Press Ctrl+C to exit.")
        
        # Display all font sizes at once
        font_test_manager.display()
        
        # Keep the display running until user interrupts
        try:
            while True:
                time.sleep(1)  # Sleep to prevent CPU hogging
                
        except KeyboardInterrupt:
            logger.info("Font test display stopped by user.")
        finally:
            # Clean up
            display_manager.clear()
            display_manager.cleanup()
            
    except Exception as e:
        logger.error(f"Error running font test display: {e}", exc_info=True)

if __name__ == "__main__":
    main() 