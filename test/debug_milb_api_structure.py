#!/usr/bin/env python3
"""
Debug script to examine the exact structure of MiLB API responses
for the specific live game that's showing N/A scores.
"""

import requests
import json
from datetime import datetime

def debug_live_game_structure():
    """Debug the structure of a specific live game."""
    print("Debugging MiLB API Structure")
    print("=" * 60)
    
    # Test the specific live game from the output
    game_pk = 785631  # Tampa Tarpons @ Lakeland Flying Tigers
    
    print(f"Examining game: {game_pk}")
    
    # Test 1: Get the schedule data for this game
    print(f"\n1. Testing schedule API for game {game_pk}")
    print("-" * 40)
    
    # Find which date this game is on
    test_dates = [
        datetime.now().strftime('%Y-%m-%d'),
        (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
    ]
    
    for date in test_dates:
        for sport_id in [10, 11, 12, 13, 14, 15]:
            url = f"http://statsapi.mlb.com/api/v1/schedule?sportId={sport_id}&date={date}"
            
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if data.get('dates'):
                    for date_data in data['dates']:
                        games = date_data.get('games', [])
                        for game in games:
                            if game.get('gamePk') == game_pk:
                                print(f"✅ Found game {game_pk} in schedule API")
                                print(f"   Date: {date}")
                                print(f"   Sport ID: {sport_id}")
                                
                                # Examine the game structure
                                print(f"\n   Game structure:")
                                print(f"   - gamePk: {game.get('gamePk')}")
                                print(f"   - status: {game.get('status')}")
                                
                                # Examine teams structure
                                teams = game.get('teams', {})
                                print(f"   - teams structure: {list(teams.keys())}")
                                
                                if 'away' in teams:
                                    away = teams['away']
                                    print(f"   - away team: {away.get('team', {}).get('name')}")
                                    print(f"   - away score: {away.get('score')}")
                                    print(f"   - away structure: {list(away.keys())}")
                                
                                if 'home' in teams:
                                    home = teams['home']
                                    print(f"   - home team: {home.get('team', {}).get('name')}")
                                    print(f"   - home score: {home.get('score')}")
                                    print(f"   - home structure: {list(home.keys())}")
                                
                                # Examine linescore
                                linescore = game.get('linescore', {})
                                if linescore:
                                    print(f"   - linescore structure: {list(linescore.keys())}")
                                    print(f"   - currentInning: {linescore.get('currentInning')}")
                                    print(f"   - inningState: {linescore.get('inningState')}")
                                    print(f"   - balls: {linescore.get('balls')}")
                                    print(f"   - strikes: {linescore.get('strikes')}")
                                    print(f"   - outs: {linescore.get('outs')}")
                                
                                return game
                
            except Exception as e:
                continue
    
    print(f"❌ Could not find game {game_pk} in schedule API")
    return None

def debug_live_feed_structure(game_pk):
    """Debug the live feed API structure."""
    print(f"\n2. Testing live feed API for game {game_pk}")
    print("-" * 40)
    
    url = f"http://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Live feed API response received")
        print(f"   Response keys: {list(data.keys())}")
        
        live_data = data.get('liveData', {})
        print(f"   liveData keys: {list(live_data.keys())}")
        
        linescore = live_data.get('linescore', {})
        if linescore:
            print(f"   linescore keys: {list(linescore.keys())}")
            print(f"   - currentInning: {linescore.get('currentInning')}")
            print(f"   - inningState: {linescore.get('inningState')}")
            print(f"   - balls: {linescore.get('balls')}")
            print(f"   - strikes: {linescore.get('strikes')}")
            print(f"   - outs: {linescore.get('outs')}")
            
            # Check teams in linescore
            teams = linescore.get('teams', {})
            if teams:
                print(f"   - teams in linescore: {list(teams.keys())}")
                if 'away' in teams:
                    away = teams['away']
                    print(f"   - away runs: {away.get('runs')}")
                    print(f"   - away structure: {list(away.keys())}")
                if 'home' in teams:
                    home = teams['home']
                    print(f"   - home runs: {home.get('runs')}")
                    print(f"   - home structure: {list(home.keys())}")
        
        # Check gameData
        game_data = live_data.get('gameData', {})
        if game_data:
            print(f"   gameData keys: {list(game_data.keys())}")
            
            # Check teams in gameData
            teams = game_data.get('teams', {})
            if teams:
                print(f"   - teams in gameData: {list(teams.keys())}")
                if 'away' in teams:
                    away = teams['away']
                    print(f"   - away name: {away.get('name')}")
                    print(f"   - away structure: {list(away.keys())}")
                if 'home' in teams:
                    home = teams['home']
                    print(f"   - home name: {home.get('name')}")
                    print(f"   - home structure: {list(home.keys())}")
        
        return data
        
    except Exception as e:
        print(f"❌ Error fetching live feed: {e}")
        return None

def main():
    """Run the debug tests."""
    from datetime import timedelta
    
    # Debug the specific live game
    game = debug_live_game_structure()
    
    if game:
        game_pk = game.get('gamePk')
        debug_live_feed_structure(game_pk)
    
    print(f"\n" + "=" * 60)
    print("DEBUG SUMMARY")
    print("=" * 60)
    print("This debug script examines:")
    print("✅ The exact structure of the schedule API response")
    print("✅ The exact structure of the live feed API response")
    print("✅ Where scores are stored in the API responses")
    print("✅ How the MiLB manager should extract score data")

if __name__ == "__main__":
    main() 