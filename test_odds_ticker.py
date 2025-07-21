#!/usr/bin/env python3
"""
Test script for the OddsTickerManager
"""

import sys
import os
import time
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.display_manager import DisplayManager
from src.config_manager import ConfigManager
from src.odds_ticker_manager import OddsTickerManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%H:%M:%S'
)

def test_odds_ticker():
    """Test the odds ticker functionality."""
    print("Testing OddsTickerManager...")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()
        
        # Initialize display manager
        display_manager = DisplayManager(config)
        
        # Initialize odds ticker
        odds_ticker = OddsTickerManager(config, display_manager)
        
        print(f"Odds ticker enabled: {odds_ticker.is_enabled}")
        print(f"Enabled leagues: {odds_ticker.enabled_leagues}")
        print(f"Show favorite teams only: {odds_ticker.show_favorite_teams_only}")
        
        if not odds_ticker.is_enabled:
            print("Odds ticker is disabled in config. Enabling for test...")
            odds_ticker.is_enabled = True
        
        # Temporarily disable favorite teams filter for testing
        print("Temporarily disabling favorite teams filter to test display...")
        original_show_favorite = odds_ticker.show_favorite_teams_only
        odds_ticker.show_favorite_teams_only = False
        
        # Update odds ticker data
        print("Updating odds ticker data...")
        odds_ticker.update()
        
        print(f"Found {len(odds_ticker.games_data)} games")
        
        if odds_ticker.games_data:
            print("Sample game data:")
            for i, game in enumerate(odds_ticker.games_data[:3]):  # Show first 3 games
                print(f"  Game {i+1}: {game['away_team']} @ {game['home_team']}")
                print(f"    Time: {game['start_time']}")
                print(f"    League: {game['league']}")
                if game.get('odds'):
                    print(f"    Has odds: Yes")
                else:
                    print(f"    Has odds: No")
                print()
            
            # Test display
            print("Testing display...")
            for i in range(5):  # Display for 5 iterations
                print(f"  Display iteration {i+1} starting...")
                odds_ticker.display()
                print(f"  Display iteration {i+1} complete")
                time.sleep(2)
        
        else:
            print("No games found even with favorite teams filter disabled. This suggests:")
            print("- No upcoming MLB games in the next 3 days")
            print("- API is not returning data")
            print("- MLB league is disabled")
            
            # Test fallback message display
            print("Testing fallback message display...")
            odds_ticker._display_fallback_message()
            time.sleep(3)
        
        # Restore original setting
        odds_ticker.show_favorite_teams_only = original_show_favorite
        
        # Cleanup
        display_manager.cleanup()
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_odds_ticker() 