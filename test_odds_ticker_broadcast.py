#!/usr/bin/env python3
"""
Test script to run the odds ticker and check for broadcast logos
"""

import sys
import os
import time
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from odds_ticker_manager import OddsTickerManager
from config_manager import ConfigManager

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_odds_ticker_broadcast():
    """Test the odds ticker with broadcast logo functionality"""
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Create a mock display manager
    class MockDisplayManager:
        def __init__(self):
            self.matrix = type('Matrix', (), {'width': 64, 'height': 32})()
            self.image = None
            self.draw = None
        
        def update_display(self):
            pass
    
    display_manager = MockDisplayManager()
    
    # Create odds ticker manager
    odds_ticker = OddsTickerManager(config, display_manager)
    
    print("=== Testing Odds Ticker with Broadcast Logos ===")
    print(f"Show channel logos enabled: {odds_ticker.show_channel_logos}")
    print(f"Enabled leagues: {odds_ticker.enabled_leagues}")
    print(f"Show favorite teams only: {odds_ticker.show_favorite_teams_only}")
    
    # Force an update to fetch fresh data
    print("\n--- Fetching games data ---")
    odds_ticker.update()
    
    if odds_ticker.games_data:
        print(f"\nFound {len(odds_ticker.games_data)} games")
        
        # Check each game for broadcast info
        for i, game in enumerate(odds_ticker.games_data[:5]):  # Check first 5 games
            print(f"\n--- Game {i+1}: {game.get('away_team')} @ {game.get('home_team')} ---")
            print(f"Game ID: {game.get('id')}")
            print(f"Broadcast info: {game.get('broadcast_info', [])}")
            
            # Test creating a display for this game
            try:
                game_image = odds_ticker._create_game_display(game)
                print(f"✓ Created game display: {game_image.size} pixels")
                
                # Save the image for inspection
                output_path = f'odds_ticker_game_{i+1}.png'
                game_image.save(output_path)
                print(f"✓ Saved to: {output_path}")
                
            except Exception as e:
                print(f"✗ Error creating game display: {e}")
                import traceback
                traceback.print_exc()
    else:
        print("No games data found")
        
        # Try to fetch some sample data
        print("\n--- Trying to fetch sample data ---")
        try:
            # Force a fresh update
            odds_ticker.last_update = 0
            odds_ticker.update()
            
            if odds_ticker.games_data:
                print(f"Found {len(odds_ticker.games_data)} games after fresh update")
            else:
                print("Still no games data found")
                
        except Exception as e:
            print(f"Error during update: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("Testing Odds Ticker Broadcast Logo Display")
    print("=" * 60)
    
    test_odds_ticker_broadcast()
    
    print("\n" + "=" * 60)
    print("Test complete. Check the generated PNG files to see if broadcast logos appear.")
    print("If broadcast logos are visible in the images, the fix is working!") 