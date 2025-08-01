#!/usr/bin/env python3
"""
Test script to check MiLB API directly
"""

import requests
import json
from datetime import datetime, timedelta, timezone

def test_milb_api():
    """Test the MiLB API directly to see what games are available."""
    print("Testing MiLB API directly...")
    
    # MiLB league sport IDs (same as in the manager)
    sport_ids = [10, 11, 12, 13, 14, 15]  # Mexican, AAA, AA, A+, A, Rookie
    
    # Get dates for the next 7 days
    now = datetime.now(timezone.utc)
    dates = []
    for i in range(-1, 8):  # Yesterday + 7 days (same as manager)
        date = now + timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    
    print(f"Checking dates: {dates}")
    print(f"Checking sport IDs: {sport_ids}")
    
    all_games = {}
    
    for date in dates:
        for sport_id in sport_ids:
            try:
                url = f"http://statsapi.mlb.com/api/v1/schedule?sportId={sport_id}&date={date}"
                print(f"\nFetching MiLB games for sport ID {sport_id}, date: {date}")
                print(f"URL: {url}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                if not data.get('dates'):
                    print(f"  No dates data for sport ID {sport_id}")
                    continue
                
                if not data['dates'][0].get('games'):
                    print(f"  No games found for sport ID {sport_id}")
                    continue
                
                games = data['dates'][0]['games']
                print(f"  Found {len(games)} games for sport ID {sport_id}")
                
                for game in games:
                    game_pk = game['gamePk']
                    
                    home_team_name = game['teams']['home']['team']['name']
                    away_team_name = game['teams']['away']['team']['name']
                    
                    home_abbr = game['teams']['home']['team'].get('abbreviation', home_team_name[:3].upper())
                    away_abbr = game['teams']['away']['team'].get('abbreviation', away_team_name[:3].upper())
                    
                    status_obj = game['status']
                    status_state = status_obj.get('abstractGameState', 'Preview')
                    detailed_state = status_obj.get('detailedState', '').lower()
                    
                    # Map status to consistent format
                    status_map = {
                        'in progress': 'status_in_progress',
                        'final': 'status_final',
                        'scheduled': 'status_scheduled',
                        'preview': 'status_scheduled'
                    }
                    mapped_status = status_map.get(detailed_state, 'status_other')
                    
                    game_time = datetime.fromisoformat(game['gameDate'].replace('Z', '+00:00'))
                    
                    print(f"    Game {game_pk}:")
                    print(f"      Teams: {away_abbr} @ {home_abbr}")
                    print(f"      Status: {detailed_state} -> {mapped_status}")
                    print(f"      State: {status_state}")
                    print(f"      Time: {game_time}")
                    print(f"      Scores: {game['teams']['away'].get('score', 0)} - {game['teams']['home'].get('score', 0)}")
                    
                    # Check if it's a favorite team (TAM from config)
                    favorite_teams = ['TAM']
                    is_favorite = (home_abbr in favorite_teams or away_abbr in favorite_teams)
                    if is_favorite:
                        print(f"      ⭐ FAVORITE TEAM GAME")
                    
                    # Store game data
                    game_data = {
                        'id': game_pk,
                        'away_team': away_abbr,
                        'home_team': home_abbr,
                        'away_score': game['teams']['away'].get('score', 0),
                        'home_score': game['teams']['home'].get('score', 0),
                        'status': mapped_status,
                        'status_state': status_state,
                        'start_time': game['gameDate'],
                        'is_favorite': is_favorite
                    }
                    
                    all_games[game_pk] = game_data
                
            except Exception as e:
                print(f"Error fetching MiLB games for sport ID {sport_id}, date {date}: {e}")
    
    # Summary
    print(f"\n{'='*50}")
    print(f"SUMMARY:")
    print(f"Total games found: {len(all_games)}")
    
    favorite_games = [g for g in all_games.values() if g['is_favorite']]
    print(f"Favorite team games: {len(favorite_games)}")
    
    live_games = [g for g in all_games.values() if g['status'] == 'status_in_progress']
    print(f"Live games: {len(live_games)}")
    
    upcoming_games = [g for g in all_games.values() if g['status'] == 'status_scheduled']
    print(f"Upcoming games: {len(upcoming_games)}")
    
    final_games = [g for g in all_games.values() if g['status'] == 'status_final']
    print(f"Final games: {len(final_games)}")
    
    if favorite_games:
        print(f"\nFavorite team games:")
        for game in favorite_games:
            print(f"  {game['away_team']} @ {game['home_team']} - {game['status']} ({game['status_state']})")
    
    if live_games:
        print(f"\nLive games:")
        for game in live_games:
            print(f"  {game['away_team']} @ {game['home_team']} - {game['away_score']}-{game['home_score']}")

if __name__ == "__main__":
    test_milb_api() 