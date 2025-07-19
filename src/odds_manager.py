import requests
import logging
import json
from datetime import datetime, timedelta
from src.cache_manager import CacheManager
from src.config_manager import ConfigManager
from typing import Optional, List, Dict, Any

class OddsManager:
    def __init__(self, cache_manager: CacheManager, config_manager: ConfigManager):
        self.cache_manager = cache_manager
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://sports.core.api.espn.com/v2/sports"

    def get_odds(self, sport: str, league: str, event_id: str, update_interval_seconds=3600):
        cache_key = f"odds_espn_{sport}_{league}_{event_id}"

        cached_data = self.cache_manager.get_cached_data(cache_key, max_age=update_interval_seconds)
        if cached_data:
            self.logger.info(f"Using cached odds from ESPN for {cache_key}")
            return cached_data

        self.logger.info(f"Fetching fresh odds from ESPN for {cache_key}")
        
        try:
            url = f"{self.base_url}/{sport}/leagues/{league}/events/{event_id}/competitions/{event_id}/odds"
            response = requests.get(url)
            response.raise_for_status()
            raw_data = response.json()
            
            odds_data = self._extract_espn_data(raw_data)
            
            if odds_data:
                self.cache_manager.save_cache(cache_key, odds_data)
            
            return odds_data

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching odds from ESPN API for {cache_key}: {e}")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON response from ESPN API for {cache_key}.")
        
        return self.cache_manager.load_cache(cache_key)

    def _extract_espn_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "items" in data and data["items"]:
            item = data["items"][0]
            # Find the desired bookmaker, e.g., 'fanduel'
            provider = next((p for p in item.get('providers', []) if p.get('name', '').lower() == 'fanduel'), item['providers'][0] if item.get('providers') else {})
            
            return {
                "details": provider.get("details"),
                "over_under": provider.get("overUnder"),
                "spread": provider.get("spread"),
                "home_team_odds": {
                    "money_line": provider.get("homeTeamOdds", {}).get("moneyLine"),
                    "spread_odds": provider.get("homeTeamOdds", {}).get("spreadOdds")
                },
                "away_team_odds": {
                    "money_line": provider.get("awayTeamOdds", {}).get("moneyLine"),
                    "spread_odds": provider.get("awayTeamOdds", {}).get("spreadOdds")
                }
            }
        return None 