#!/usr/bin/env python3
"""
Test script for the new broadcast extraction logic
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from odds_ticker_manager import OddsTickerManager
from config_manager import ConfigManager

def test_broadcast_extraction():
    """Test the new broadcast extraction logic"""
    
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
    
    # Test the broadcast extraction logic with sample data from the API
    test_broadcasts = [
        # Sample from the API response
        [
            {'market': 'away', 'names': ['MLB.TV', 'MAS+', 'MASN2']},
            {'market': 'home', 'names': ['CLEGuardians.TV']}
        ],
        [
            {'market': 'away', 'names': ['MLB.TV', 'FanDuel SN DET']},
            {'market': 'home', 'names': ['SportsNet PIT']}
        ],
        [
            {'market': 'away', 'names': ['MLB.TV', 'Padres.TV']},
            {'market': 'home', 'names': ['FanDuel SN FL']}
        ],
        # Test with old format too
        [
            {'media': {'shortName': 'ESPN'}},
            {'media': {'shortName': 'FOX'}}
        ]
    ]
    
    for i, broadcasts in enumerate(test_broadcasts):
        print(f"\n--- Test Case {i+1} ---")
        print(f"Input broadcasts: {broadcasts}")
        
        # Simulate the extraction logic
        broadcast_info = []
        for broadcast in broadcasts:
            if 'names' in broadcast:
                # New format: broadcast names are in 'names' array
                broadcast_names = broadcast.get('names', [])
                broadcast_info.extend(broadcast_names)
            elif 'media' in broadcast and 'shortName' in broadcast['media']:
                # Old format: broadcast name is in media.shortName
                short_name = broadcast['media']['shortName']
                if short_name:
                    broadcast_info.append(short_name)
        
        # Remove duplicates and filter out empty strings
        broadcast_info = list(set([name for name in broadcast_info if name]))
        
        print(f"Extracted broadcast info: {broadcast_info}")
        
        # Test logo mapping
        if broadcast_info:
            logo_name = None
            sorted_keys = sorted(odds_ticker.BROADCAST_LOGO_MAP.keys(), key=len, reverse=True)
            
            for b_name in broadcast_info:
                for key in sorted_keys:
                    if key in b_name:
                        logo_name = odds_ticker.BROADCAST_LOGO_MAP[key]
                        print(f"  Matched '{key}' to '{logo_name}' for '{b_name}'")
                        break
                if logo_name:
                    break
            
            print(f"  Final mapped logo: '{logo_name}'")
            
            if logo_name:
                logo_path = os.path.join('assets', 'broadcast_logos', f"{logo_name}.png")
                print(f"  Logo file exists: {os.path.exists(logo_path)}")
        else:
            print("  No broadcast info extracted")

if __name__ == "__main__":
    print("Testing New Broadcast Extraction Logic")
    print("=" * 50)
    
    test_broadcast_extraction()
    
    print("\n" + "=" * 50)
    print("Test complete. Check if the broadcast extraction and mapping works correctly.") 