#!/usr/bin/env python3
"""
Test script to check MLB API directly
"""

import requests
import json
from datetime import datetime, timedelta, timezone

def test_mlb_api():
    """Test the MLB API directly to see what games are available."""
    print("Testing MLB API directly...")
    
    # Get dates for the next 7 days
    now = datetime.now(timezone.utc)
    dates = []
    for i in range(8):  # Today + 7 days
        date = now + timedelta(days=i)
        dates.append(date.strftime("%Y%m%d"))
    
    print(f"Checking dates: {dates}")
    
    for date in dates:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates={date}"
            print(f"\nFetching MLB games for date: {date}")
            print(f"URL: {url}")
            
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            events = data.get('events', [])
            
            print(f"Found {len(events)} events for MLB on {date}")
            
            for event in events:
                game_id = event['id']
                status = event['status']['type']['name'].lower()
                game_time = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                
                print(f"  Game {game_id}:")
                print(f"    Status: {status}")
                print(f"    Time: {game_time}")
                
                if status in ['scheduled', 'pre-game']:
                    # Get team information
                    competitors = event['competitions'][0]['competitors']
                    home_team = next(c for c in competitors if c['homeAway'] == 'home')
                    away_team = next(c for c in competitors if c['homeAway'] == 'away')
                    
                    home_abbr = home_team['team']['abbreviation']
                    away_abbr = away_team['team']['abbreviation']
                    
                    print(f"    Teams: {away_abbr} @ {home_abbr}")
                    
                    # Check if it's in the next 7 days
                    if now <= game_time <= now + timedelta(days=7):
                        print(f"    ✅ IN RANGE (next 7 days)")
                    else:
                        print(f"    ❌ OUT OF RANGE")
                else:
                    print(f"    ❌ Status '{status}' - not upcoming")
                
        except Exception as e:
            print(f"Error fetching MLB games for date {date}: {e}")

if __name__ == "__main__":
    test_mlb_api() 