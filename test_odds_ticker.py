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
                odds_ticker.display()
                time.sleep(2)
                print(f"Display iteration {i+1} complete")
        
        else:
            print("No games found. This might be normal if:")
            print("- No upcoming games in the next 7 days")
            print("- No favorite teams have upcoming games (if show_favorite_teams_only is True)")
            print("- API is not returning data")
        
        # Cleanup
        display_manager.cleanup()
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_odds_ticker() 