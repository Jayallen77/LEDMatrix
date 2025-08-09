#!/usr/bin/env python3
"""
Test script to debug MiLB cache issues.
This script will check the cache data structure and identify any corrupted data.
"""

import sys
import os
import json
import logging
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cache_manager import CacheManager
from config_manager import ConfigManager

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_milb_cache():
    """Check the MiLB cache data structure."""
    try:
        # Initialize managers
        config_manager = ConfigManager()
        cache_manager = CacheManager()
        
        # Check the MiLB cache key
        cache_key = "milb_live_api_data"
        
        logger.info(f"Checking cache for key: {cache_key}")
        
        # Try to get cached data
        cached_data = cache_manager.get_with_auto_strategy(cache_key)
        
        if cached_data is None:
            logger.info("No cached data found")
            return
        
        logger.info(f"Cached data type: {type(cached_data)}")
        
        if isinstance(cached_data, dict):
            logger.info(f"Number of games in cache: {len(cached_data)}")
            
            # Check each game
            for game_id, game_data in cached_data.items():
                logger.info(f"Game ID: {game_id} (type: {type(game_id)})")
                logger.info(f"Game data type: {type(game_data)}")
                
                if isinstance(game_data, dict):
                    logger.info(f"  - Valid game data with {len(game_data)} fields")
                    # Check for required fields
                    required_fields = ['away_team', 'home_team', 'start_time']
                    for field in required_fields:
                        if field in game_data:
                            logger.info(f"  - {field}: {game_data[field]} (type: {type(game_data[field])})")
                        else:
                            logger.warning(f"  - Missing required field: {field}")
                else:
                    logger.error(f"  - INVALID: Game data is not a dictionary: {type(game_data)}")
                    logger.error(f"  - Value: {game_data}")
                    
                    # Try to understand what this value is
                    if isinstance(game_data, (int, float)):
                        logger.error(f"  - This appears to be a numeric value: {game_data}")
                    elif isinstance(game_data, str):
                        logger.error(f"  - This appears to be a string: {game_data}")
                    else:
                        logger.error(f"  - Unknown type: {type(game_data)}")
        else:
            logger.error(f"Cache data is not a dictionary: {type(cached_data)}")
            logger.error(f"Value: {cached_data}")
            
            # Try to understand what this value is
            if isinstance(cached_data, (int, float)):
                logger.error(f"This appears to be a numeric value: {cached_data}")
            elif isinstance(cached_data, str):
                logger.error(f"This appears to be a string: {cached_data}")
            else:
                logger.error(f"Unknown type: {type(cached_data)}")
        
    except Exception as e:
        logger.error(f"Error checking MiLB cache: {e}", exc_info=True)

def clear_milb_cache():
    """Clear the MiLB cache."""
    try:
        config_manager = ConfigManager()
        cache_manager = CacheManager()
        
        cache_key = "milb_live_api_data"
        logger.info(f"Clearing cache for key: {cache_key}")
        
        cache_manager.clear_cache(cache_key)
        logger.info("Cache cleared successfully")
        
    except Exception as e:
        logger.error(f"Error clearing MiLB cache: {e}", exc_info=True)

if __name__ == "__main__":
    print("MiLB Cache Debug Tool")
    print("=====================")
    print()
    
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_milb_cache()
    else:
        check_milb_cache()
        
    print()
    print("Debug complete.")
