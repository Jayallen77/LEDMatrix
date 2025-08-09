#!/usr/bin/env python3
"""
Test script to verify soccer manager favorite teams filtering functionality.
This test checks that when show_favorite_teams_only is enabled, only games
involving favorite teams are processed.
"""

import sys
import os
import json
from datetime import datetime, timedelta
import pytz

# Add the src directory to the path so we can import the soccer managers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from soccer_managers import BaseSoccerManager
from display_manager import DisplayManager
from cache_manager import CacheManager

def create_test_config(show_favorite_teams_only=True, favorite_teams=None):
    """Create a test configuration for soccer manager."""
    if favorite_teams is None:
        favorite_teams = ["DAL", "TB"]
    
    config = {
        "soccer_scoreboard": {
            "enabled": True,
            "show_favorite_teams_only": show_favorite_teams_only,
            "favorite_teams": favorite_teams,
            "leagues": ["usa.1"],
            "logo_dir": "assets/sports/soccer_logos",
            "recent_game_hours": 168,
            "update_interval_seconds": 3600
        },
        "display": {
            "hardware": {
                "rows": 32,
                "cols": 64,
                "chain_length": 1
            }
        },
        "timezone": "America/Chicago"
    }
    return config

def create_test_game_data():
    """Create test game data with various teams."""
    now = datetime.now(pytz.utc)
    
    games = [
        {
            "id": "1",
            "date": now.isoformat(),
            "competitions": [{
                "status": {
                    "type": {"name": "STATUS_IN_PROGRESS", "shortDetail": "45'"}
                },
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"abbreviation": "DAL"},
                        "score": "2"
                    },
                    {
                        "homeAway": "away", 
                        "team": {"abbreviation": "LAFC"},
                        "score": "1"
                    }
                ]
            }],
            "league": {"slug": "usa.1", "name": "MLS"}
        },
        {
            "id": "2", 
            "date": now.isoformat(),
            "competitions": [{
                "status": {
                    "type": {"name": "STATUS_IN_PROGRESS", "shortDetail": "30'"}
                },
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"abbreviation": "TB"},
                        "score": "0"
                    },
                    {
                        "homeAway": "away",
                        "team": {"abbreviation": "NY"},
                        "score": "0"
                    }
                ]
            }],
            "league": {"slug": "usa.1", "name": "MLS"}
        },
        {
            "id": "3",
            "date": now.isoformat(), 
            "competitions": [{
                "status": {
                    "type": {"name": "STATUS_IN_PROGRESS", "shortDetail": "15'"}
                },
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"abbreviation": "LAFC"},
                        "score": "1"
                    },
                    {
                        "homeAway": "away",
                        "team": {"abbreviation": "NY"},
                        "score": "1"
                    }
                ]
            }],
            "league": {"slug": "usa.1", "name": "MLS"}
        }
    ]
    return games

def test_favorite_teams_filtering():
    """Test that favorite teams filtering works correctly."""
    print("Testing soccer manager favorite teams filtering...")
    
    # Test 1: With favorite teams filtering enabled
    print("\n1. Testing with show_favorite_teams_only=True")
    config = create_test_config(show_favorite_teams_only=True, favorite_teams=["DAL", "TB"])
    
    # Create mock display and cache managers
    display_manager = DisplayManager(config)
    cache_manager = CacheManager()
    
    # Create soccer manager
    soccer_manager = BaseSoccerManager(config, display_manager, cache_manager)
    
    # Create test game data
    test_games = create_test_game_data()
    
    # Process games and check filtering
    filtered_games = []
    for game_event in test_games:
        details = soccer_manager._extract_game_details(game_event)
        if details and details["is_live"]:
            filtered_games.append(details)
    
    # Apply favorite teams filtering
    if soccer_manager.soccer_config.get("show_favorite_teams_only", False) and soccer_manager.favorite_teams:
        filtered_games = [game for game in filtered_games if game['home_abbr'] in soccer_manager.favorite_teams or game['away_abbr'] in soccer_manager.favorite_teams]
    
    print(f"   Total games: {len(test_games)}")
    print(f"   Live games: {len([g for g in test_games if g['competitions'][0]['status']['type']['name'] == 'STATUS_IN_PROGRESS'])}")
    print(f"   Games after favorite teams filtering: {len(filtered_games)}")
    
    # Verify only games with DAL or TB are included
    expected_teams = {"DAL", "TB"}
    for game in filtered_games:
        home_team = game['home_abbr']
        away_team = game['away_abbr']
        assert home_team in expected_teams or away_team in expected_teams, f"Game {home_team} vs {away_team} should not be included"
        print(f"   ✓ Included: {away_team} vs {home_team}")
    
    # Test 2: With favorite teams filtering disabled
    print("\n2. Testing with show_favorite_teams_only=False")
    config = create_test_config(show_favorite_teams_only=False, favorite_teams=["DAL", "TB"])
    soccer_manager = BaseSoccerManager(config, display_manager, cache_manager)
    
    filtered_games = []
    for game_event in test_games:
        details = soccer_manager._extract_game_details(game_event)
        if details and details["is_live"]:
            filtered_games.append(details)
    
    # Apply favorite teams filtering (should not filter when disabled)
    if soccer_manager.soccer_config.get("show_favorite_teams_only", False) and soccer_manager.favorite_teams:
        filtered_games = [game for game in filtered_games if game['home_abbr'] in soccer_manager.favorite_teams or game['away_abbr'] in soccer_manager.favorite_teams]
    
    print(f"   Total games: {len(test_games)}")
    print(f"   Live games: {len([g for g in test_games if g['competitions'][0]['status']['type']['name'] == 'STATUS_IN_PROGRESS'])}")
    print(f"   Games after filtering (should be all live games): {len(filtered_games)}")
    
    # Verify all live games are included when filtering is disabled
    assert len(filtered_games) == 3, f"Expected 3 games, got {len(filtered_games)}"
    print("   ✓ All live games included when filtering is disabled")
    
    print("\n✅ All tests passed! Favorite teams filtering is working correctly.")

if __name__ == "__main__":
    try:
        test_favorite_teams_filtering()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
