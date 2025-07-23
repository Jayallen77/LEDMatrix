#!/usr/bin/env python3
"""
Script to check ESPN API responses for broadcast information
"""

import requests
import json
from datetime import datetime, timedelta
import sys

def check_espn_api():
    """Check ESPN API responses for broadcast information"""
    
    # Test different sports and leagues
    test_urls = [
        # MLB
        "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
        # NFL  
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        # NBA
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
        # College Football
        "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    ]
    
    today = datetime.now().strftime("%Y%m%d")
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Checking: {url}")
        print(f"{'='*60}")
        
        try:
            # Add date parameter
            params = {'dates': today}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            events = data.get('events', [])
            print(f"Found {len(events)} events")
            
            # Check first few events for broadcast info
            for i, event in enumerate(events[:3]):  # Check first 3 events
                print(f"\n--- Event {i+1} ---")
                print(f"Event ID: {event.get('id')}")
                print(f"Name: {event.get('name', 'N/A')}")
                print(f"Status: {event.get('status', {}).get('type', {}).get('name', 'N/A')}")
                
                # Check competitions for broadcast info
                competitions = event.get('competitions', [])
                if competitions:
                    competition = competitions[0]
                    broadcasts = competition.get('broadcasts', [])
                    print(f"Broadcasts found: {len(broadcasts)}")
                    
                    for j, broadcast in enumerate(broadcasts):
                        print(f"  Broadcast {j+1}:")
                        print(f"    Raw broadcast data: {broadcast}")
                        
                        # Check media info
                        media = broadcast.get('media', {})
                        print(f"    Media data: {media}")
                        
                        # Check for shortName
                        short_name = media.get('shortName')
                        if short_name:
                            print(f"    ✓ shortName: '{short_name}'")
                        else:
                            print(f"    ✗ No shortName found")
                        
                        # Check for other possible broadcast fields
                        for key in ['name', 'type', 'callLetters', 'id']:
                            value = media.get(key)
                            if value:
                                print(f"    {key}: '{value}'")
                
                else:
                    print("No competitions found")
                    
        except Exception as e:
            print(f"Error fetching {url}: {e}")

def check_specific_game():
    """Check a specific game that should have broadcast info"""
    print(f"\n{'='*60}")
    print("Checking for games with known broadcast info")
    print(f"{'='*60}")
    
    # Check NFL games (more likely to have broadcast info)
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    today = datetime.now().strftime("%Y%m%d")
    
    try:
        params = {'dates': today}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        events = data.get('events', [])
        print(f"Found {len(events)} NFL events")
        
        # Look for events with broadcast info
        events_with_broadcasts = []
        for event in events:
            competitions = event.get('competitions', [])
            if competitions:
                broadcasts = competitions[0].get('broadcasts', [])
                if broadcasts:
                    events_with_broadcasts.append(event)
        
        print(f"Events with broadcast info: {len(events_with_broadcasts)}")
        
        for i, event in enumerate(events_with_broadcasts[:2]):  # Show first 2
            print(f"\n--- Event with Broadcast {i+1} ---")
            print(f"Event ID: {event.get('id')}")
            print(f"Name: {event.get('name', 'N/A')}")
            
            competitions = event.get('competitions', [])
            if competitions:
                broadcasts = competitions[0].get('broadcasts', [])
                for j, broadcast in enumerate(broadcasts):
                    print(f"  Broadcast {j+1}:")
                    media = broadcast.get('media', {})
                    print(f"    Media: {media}")
                    
                    # Show all possible broadcast-related fields
                    for key, value in media.items():
                        print(f"    {key}: {value}")
                        
    except Exception as e:
        print(f"Error checking specific games: {e}")

if __name__ == "__main__":
    print("ESPN API Broadcast Information Check")
    print("This script will check what broadcast information is available in ESPN API responses")
    
    check_espn_api()
    check_specific_game()
    
    print(f"\n{'='*60}")
    print("Check complete. Look for 'shortName' fields in the broadcast data.")
    print("This is what the odds ticker uses to map to broadcast logos.") 