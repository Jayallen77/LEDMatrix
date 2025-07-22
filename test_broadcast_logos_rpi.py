#!/usr/bin/env python3
"""
Diagnostic script for broadcast logo display on Raspberry Pi
Run this on the Pi to test broadcast logo functionality
"""

import os
import sys
import logging
from PIL import Image

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import with proper error handling
try:
    from odds_ticker_manager import OddsTickerManager
    from config_manager import ConfigManager
    
    # Create a mock display manager to avoid hardware dependencies
    class MockDisplayManager:
        def __init__(self):
            self.matrix = type('Matrix', (), {'width': 64, 'height': 32})()
            self.image = None
            self.draw = None
        
        def update_display(self):
            pass
    
    display_manager = MockDisplayManager()
    
except ImportError as e:
    print(f"Import error: {e}")
    print("This script needs to be run from the LEDMatrix directory")
    sys.exit(1)

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_broadcast_logo_files():
    """Test if broadcast logo files exist and can be loaded"""
    print("=== Testing Broadcast Logo Files ===")
    
    broadcast_logos_dir = "assets/broadcast_logos"
    if not os.path.exists(broadcast_logos_dir):
        print(f"ERROR: Broadcast logos directory not found: {broadcast_logos_dir}")
        return False
    
    print(f"Found broadcast logos directory: {broadcast_logos_dir}")
    
    # Test a few key logos
    test_logos = ["espn", "fox", "cbs", "nbc", "tbs", "tnt"]
    
    for logo_name in test_logos:
        logo_path = os.path.join(broadcast_logos_dir, f"{logo_name}.png")
        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path)
                print(f"✓ {logo_name}.png - Size: {logo.size}")
            except Exception as e:
                print(f"✗ {logo_name}.png - Error loading: {e}")
        else:
            print(f"✗ {logo_name}.png - File not found")
    
    return True

def test_broadcast_logo_mapping():
    """Test the broadcast logo mapping logic"""
    print("\n=== Testing Broadcast Logo Mapping ===")
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # Create odds ticker manager
    odds_ticker = OddsTickerManager(config, display_manager)
    
    # Test various broadcast names that might appear in the API
    test_cases = [
        ["ESPN"],
        ["FOX"],
        ["CBS"],
        ["NBC"],
        ["ESPN2"],
        ["FS1"],
        ["ESPNEWS"],
        ["ESPN+"],
        ["ESPN Plus"],
        ["Peacock"],
        ["Paramount+"],
        ["ABC"],
        ["TBS"],
        ["TNT"],
        ["Unknown Channel"],
        []
    ]
    
    for broadcast_names in test_cases:
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
        
        print(f"  Mapped logo name: '{logo_name}'")
        
        if logo_name:
            # Test loading the actual logo
            logo_path = os.path.join('assets', 'broadcast_logos', f"{logo_name}.png")
            print(f"  Logo path: {logo_path}")
            print(f"  File exists: {os.path.exists(logo_path)}")
            
            if os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)
                    print(f"  ✓ Successfully loaded logo: {logo.size} pixels")
                except Exception as e:
                    print(f"  ✗ Error loading logo: {e}")
            else:
                print("  ✗ Logo file not found!")

def test_game_display_with_broadcast():
    """Test creating a game display with broadcast info"""
    print("\n=== Testing Game Display with Broadcast Info ===")
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # Create odds ticker manager
    odds_ticker = OddsTickerManager(config, display_manager)
    
    # Test cases with different broadcast info
    test_games = [
        {
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
        },
        {
            'id': 'test_game_2',
            'home_team': 'NY',
            'away_team': 'LA',
            'home_team_name': 'New York Yankees',
            'away_team_name': 'Los Angeles Dodgers',
            'start_time': '2024-01-15T20:00:00Z',
            'home_record': '82-80',
            'away_record': '100-62',
            'broadcast_info': ['FOX'],
            'logo_dir': 'assets/sports/mlb_logos'
        },
        {
            'id': 'test_game_3',
            'home_team': 'CHI',
            'away_team': 'MIA',
            'home_team_name': 'Chicago Cubs',
            'away_team_name': 'Miami Marlins',
            'start_time': '2024-01-15T21:00:00Z',
            'home_record': '83-79',
            'away_record': '84-78',
            'broadcast_info': [],  # No broadcast info
            'logo_dir': 'assets/sports/mlb_logos'
        }
    ]
    
    for i, test_game in enumerate(test_games):
        print(f"\n--- Test Game {i+1}: {test_game['away_team']} @ {test_game['home_team']} ---")
        print(f"Broadcast info: {test_game['broadcast_info']}")
        
        try:
            # Create the game display
            game_image = odds_ticker._create_game_display(test_game)
            print(f"✓ Successfully created game image: {game_image.size} pixels")
            
            # Save the image for inspection
            output_path = f'test_broadcast_logo_output_{i+1}.png'
            game_image.save(output_path)
            print(f"✓ Saved test image to: {output_path}")
            
        except Exception as e:
            print(f"✗ Error creating game display: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("=== Broadcast Logo Diagnostic Script ===\n")
    
    # Test 1: Check if broadcast logo files exist
    test_broadcast_logo_files()
    
    # Test 2: Test broadcast logo mapping
    test_broadcast_logo_mapping()
    
    # Test 3: Test game display with broadcast info
    test_game_display_with_broadcast()
    
    print("\n=== Diagnostic Complete ===")
    print("Check the generated PNG files to see if broadcast logos are being included.") 