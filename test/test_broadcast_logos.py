#!/usr/bin/env python3
"""
Test script to debug broadcast logo display in odds ticker
"""

import os
import sys
import logging
from PIL import Image

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from odds_ticker_manager import OddsTickerManager
from display_manager import DisplayManager
from config_manager import ConfigManager

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_broadcast_logo_loading():
    """Test broadcast logo loading functionality"""
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
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
    
    # Test broadcast logo mapping
    print("Testing broadcast logo mapping...")
    test_broadcast_names = [
        ["ESPN"],
        ["FOX"],
        ["CBS"],
        ["NBC"],
        ["ESPN2"],
        ["FS1"],
        ["ESPNEWS"],
        ["ABC"],
        ["TBS"],
        ["TNT"],
        ["Unknown Channel"],
        []
    ]
    
    for broadcast_names in test_broadcast_names:
        print(f"\nTesting broadcast names: {broadcast_names}")
        
        # Simulate the logo mapping logic
        logo_name = None
        sorted_keys = sorted(odds_ticker.BROADCAST_LOGO_MAP.keys(), key=len, reverse=True)
        
        for b_name in broadcast_names:
            for key in sorted_keys:
                if key in b_name:
                    logo_name = odds_ticker.BROADCAST_LOGO_MAP[key]
                    break
            if logo_name:
                break
        
        print(f"Mapped logo name: '{logo_name}'")
        
        if logo_name:
            # Test loading the actual logo
            logo_path = os.path.join('assets', 'broadcast_logos', f"{logo_name}.png")
            print(f"Logo path: {logo_path}")
            print(f"File exists: {os.path.exists(logo_path)}")
            
            if os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)
                    print(f"Successfully loaded logo: {logo.size} pixels")
                except Exception as e:
                    print(f"Error loading logo: {e}")
            else:
                print("Logo file not found!")

def test_game_with_broadcast_info():
    """Test creating a game display with broadcast info"""
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
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
    
    # Create a test game with broadcast info
    test_game = {
        'id': 'test_game_1',
        'home_team': 'TB',
        'away_team': 'BOS',
        'home_team_name': 'Tampa Bay Rays',
        'away_team_name': 'Boston Red Sox',
        'start_time': '2024-01-15T19:00:00Z',
        'home_record': '95-67',
        'away_record': '78-84',
        'broadcast_info': ['ESPN'],
        'logo_dir': 'assets/sports/mlb_logos'
    }
    
    print(f"\nTesting game display with broadcast info: {test_game['broadcast_info']}")
    
    try:
        # Create the game display
        game_image = odds_ticker._create_game_display(test_game)
        print(f"Successfully created game image: {game_image.size} pixels")
        
        # Save the image for inspection
        output_path = 'test_broadcast_logo_output.png'
        game_image.save(output_path)
        print(f"Saved test image to: {output_path}")
        
    except Exception as e:
        print(f"Error creating game display: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== Testing Broadcast Logo Functionality ===\n")
    
    # Test 1: Logo loading
    test_broadcast_logo_loading()
    
    # Test 2: Game display with broadcast info
    test_game_with_broadcast_info()
    
    print("\n=== Test Complete ===") 