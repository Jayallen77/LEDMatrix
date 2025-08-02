#!/usr/bin/env python3
"""
Simple test script to debug MILB live manager
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.milb_manager import MiLBLiveManager
from src.config_manager import ConfigManager
from src.display_manager import DisplayManager

def test_milb_live():
    print("Testing MILB Live Manager...")
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # Create a mock display manager
    class MockDisplayManager:
        def __init__(self):
            self.matrix = type('Matrix', (), {'width': 64, 'height': 32})()
            self.image = None
            self.draw = None
            self.font = None
            self.calendar_font = None
        
        def update_display(self):
            pass
        
        def get_text_width(self, text, font):
            return len(text) * 6  # Rough estimate
        
        def _draw_bdf_text(self, text, x, y, color, font):
            pass
    
    display_manager = MockDisplayManager()
    
    # Create MILB live manager
    milb_manager = MiLBLiveManager(config, display_manager)
    
    print(f"Test mode: {milb_manager.test_mode}")
    print(f"Favorite teams: {milb_manager.favorite_teams}")
    print(f"Update interval: {milb_manager.update_interval}")
    
    # Test the update method
    print("\nCalling update method...")
    milb_manager.update()
    
    print(f"Live games found: {len(milb_manager.live_games)}")
    if milb_manager.live_games:
        for i, game in enumerate(milb_manager.live_games):
            print(f"Game {i+1}: {game['away_team']} @ {game['home_team']}")
            print(f"  Status: {game['status']}")
            print(f"  Status State: {game['status_state']}")
            print(f"  Scores: {game['away_score']} - {game['home_score']}")
            print(f"  Inning: {game.get('inning', 'N/A')}")
            print(f"  Inning Half: {game.get('inning_half', 'N/A')}")
    else:
        print("No live games found")
    
    print(f"Current game: {milb_manager.current_game}")
    
    # Test the display method
    if milb_manager.current_game:
        print("\nTesting display method...")
        try:
            milb_manager.display()
            print("Display method completed successfully")
        except Exception as e:
            print(f"Display method failed: {e}")

if __name__ == "__main__":
    test_milb_live() 