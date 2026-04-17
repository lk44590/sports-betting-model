"""
Data fetcher for ESPN API and other free data sources.
Smart caching to minimize API calls.
"""

import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import hashlib

# ESPN API endpoints (free, no API key required)
ESPN_ENDPOINTS = {
    "MLB": "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    "NCAABASE": "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard",
    "NBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "WNBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
    "NCAAMB": "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard",
    "NCAAWB": "https://site.api.espn.com/apis/site/v2/sports/basketball/womens-college-basketball/scoreboard",
    "NFL": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    "NCAAF": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
    "NHL": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "MLS": "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
    "EPL": "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
    "La Liga": "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard",
    "Bundesliga": "https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard",
    "Serie A": "https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard",
    "UCL": "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard",
}

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    data: Any
    timestamp: float
    ttl_seconds: int
    
    def is_valid(self) -> bool:
        return (time.time() - self.timestamp) < self.ttl_seconds


class SmartCache:
    """
    Smart caching system with different TTLs for different data types.
    """
    
    TTL_CONFIG = {
        "scores": 60,           # 1 minute for live scores
        "odds": 900,            # 15 minutes for betting odds
        "schedule": 3600,       # 1 hour for schedules
        "teams": 86400,         # 24 hours for team info
        "stats": 3600,          # 1 hour for statistics
        "default": 300          # 5 minutes default
    }
    
    def __init__(self):
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._disk_cache_dir = CACHE_DIR
    
    def _get_cache_key(self, endpoint: str, params: Dict = None) -> str:
        """Generate cache key from endpoint and params."""
        key_str = endpoint + json.dumps(params or {}, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_ttl(self, data_type: str) -> int:
        """Get TTL for data type."""
        return self.TTL_CONFIG.get(data_type, self.TTL_CONFIG["default"])
    
    def get(self, endpoint: str, params: Dict = None, data_type: str = "default") -> Optional[Any]:
        """Get cached data if available and valid."""
        cache_key = self._get_cache_key(endpoint, params)
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if entry.is_valid():
                return entry.data
            del self._memory_cache[cache_key]
        
        # Check disk cache
        cache_file = self._disk_cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)
                    timestamp = cached.get('_timestamp', 0)
                    ttl = self._get_ttl(data_type)
                    
                    if (time.time() - timestamp) < ttl:
                        # Restore to memory cache
                        self._memory_cache[cache_key] = CacheEntry(
                            data=cached['data'],
                            timestamp=timestamp,
                            ttl_seconds=ttl
                        )
                        return cached['data']
            except Exception:
                pass
        
        return None
    
    def set(self, endpoint: str, data: Any, params: Dict = None, data_type: str = "default") -> None:
        """Cache data in memory and disk."""
        cache_key = self._get_cache_key(endpoint, params)
        ttl = self._get_ttl(data_type)
        timestamp = time.time()
        
        # Store in memory
        self._memory_cache[cache_key] = CacheEntry(
            data=data,
            timestamp=timestamp,
            ttl_seconds=ttl
        )
        
        # Store on disk
        cache_file = self._disk_cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'data': data,
                    '_timestamp': timestamp,
                    '_ttl': ttl
                }, f)
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def invalidate(self, pattern: str = None) -> None:
        """Invalidate cache entries matching pattern."""
        if pattern:
            keys_to_remove = [k for k in self._memory_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._memory_cache[key]
        else:
            self._memory_cache.clear()


class ESPNDataFetcher:
    """
    Fetch sports data from ESPN API with smart caching.
    """
    
    def __init__(self):
        self.cache = SmartCache()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.request_count = 0
        self.cache_hits = 0
    
    def _make_request(self, url: str, params: Dict = None, 
                     data_type: str = "default") -> Optional[Dict]:
        """Make API request with caching."""
        # Check cache first
        cached = self.cache.get(url, params, data_type)
        if cached is not None:
            self.cache_hits += 1
            return cached
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Cache the response
            self.cache.set(url, data, params, data_type)
            self.request_count += 1
            
            return data
        except requests.RequestException as e:
            print(f"API request failed: {url} - {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {url} - {e}")
            return None
    
    def get_schedule(self, sport: str, game_date: str = None) -> Optional[Dict]:
        """
        Get schedule/scoreboard for a sport.
        
        Args:
            sport: Sport key (NBA, MLB, NFL, etc.)
            game_date: Date in YYYYMMDD format (optional)
        """
        if sport not in ESPN_ENDPOINTS:
            print(f"Unknown sport: {sport}")
            return None
        
        url = ESPN_ENDPOINTS[sport]
        params = {}
        
        if game_date:
            params['dates'] = game_date
        
        return self._make_request(url, params, data_type="schedule")
    
    def get_live_scores(self, sport: str) -> Optional[Dict]:
        """Get live scores for a sport (shorter cache)."""
        return self.get_schedule(sport)  # Same endpoint, different cache TTL
    
    def get_event_details(self, event_id: str) -> Optional[Dict]:
        """Get detailed information for a specific event."""
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
        params = {'event': event_id}
        return self._make_request(url, params, data_type="scores")
    
    def get_team_stats(self, sport: str, team_id: str) -> Optional[Dict]:
        """Get team statistics."""
        # ESPN team stats endpoint varies by sport
        sport_paths = {
            "NBA": "basketball/nba",
            "MLB": "baseball/mlb",
            "NFL": "football/nfl",
            "NHL": "hockey/nhl",
        }
        
        if sport not in sport_paths:
            return None
        
        url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_paths[sport]}/teams/{team_id}"
        return self._make_request(url, data_type="teams")
    
    def get_all_sports_schedules(self, game_date: str = None) -> Dict[str, Optional[Dict]]:
        """Get schedules for all supported sports."""
        results = {}
        for sport in ESPN_ENDPOINTS.keys():
            results[sport] = self.get_schedule(sport, game_date)
        return results
    
    def get_stats(self) -> Dict[str, int]:
        """Get fetcher statistics."""
        return {
            "requests": self.request_count,
            "cache_hits": self.cache_hits,
            "hit_rate": round(self.cache_hits / (self.request_count + self.cache_hits) * 100, 1) if (self.request_count + self.cache_hits) > 0 else 0
        }


class OddsDataFetcher:
    """
    Fetch odds data from The Odds API (free tier).
    500 requests/month limit - use wisely!
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.cache = SmartCache()
        self.session = requests.Session()
        self.base_url = "https://api.the-odds-api.com/v4"
        self.request_count = 0
        
        # Odds API to our sport mapping
        self.SPORT_MAP = {
            "basketball_nba": "NBA",
            "basketball_ncaab": "NCAAMB",
            "baseball_mlb": "MLB",
            "americanfootball_nfl": "NFL",
            "icehockey_nhl": "NHL",
            "soccer_usa_mls": "MLS",
        }
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make Odds API request with caching."""
        if not self.api_key:
            return None
        
        cache_key = f"odds_{endpoint}_{hashlib.md5(json.dumps(params or {}).encode()).hexdigest()}"
        
        # Check cache (15 min for odds)
        cached = self.cache.get(endpoint, params, data_type="odds")
        if cached:
            return cached
        
        url = f"{self.base_url}/{endpoint}"
        params = params or {}
        params['apiKey'] = self.api_key
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            # Check rate limit
            remaining = response.headers.get('x-requests-remaining')
            if remaining:
                print(f"Odds API calls remaining: {remaining}")
            
            response.raise_for_status()
            data = response.json()
            
            self.cache.set(endpoint, data, params, data_type="odds")
            self.request_count += 1
            
            return data
        except requests.RequestException as e:
            print(f"Odds API request failed: {e}")
            return None
    
    def get_live_odds(self, sport: str, regions: str = "us", 
                     markets: str = "h2h,spreads,totals") -> Optional[List[Dict]]:
        """
        Get live odds for a sport.
        
        Args:
            sport: Odds API sport key (e.g., 'basketball_nba')
            regions: 'us', 'uk', 'eu', 'au' or comma-separated combo
            markets: 'h2h' (moneyline), 'spreads', 'totals', or comma-separated
        """
        endpoint = f"sports/{sport}/odds"
        params = {
            'regions': regions,
            'markets': markets,
            'oddsFormat': 'american',
            'dateFormat': 'iso'
        }
        return self._make_request(endpoint, params)
    
    def get_all_live_odds(self, regions: str = "us") -> Dict[str, List[Dict]]:
        """Get live odds for all supported sports."""
        results = {}
        for odds_sport, our_sport in self.SPORT_MAP.items():
            odds = self.get_live_odds(odds_sport, regions)
            if odds:
                results[our_sport] = odds
        return results
    
    def get_usage(self) -> Dict[str, Any]:
        """Get API usage stats."""
        return {
            "requests_this_month": self.request_count,
            "limit": 500,
            "remaining": max(0, 500 - self.request_count),
            "has_api_key": self.api_key is not None
        }


class DataAggregator:
    """
    Aggregate data from multiple sources to create bet candidates.
    """
    
    def __init__(self, odds_api_key: Optional[str] = None):
        self.espn = ESPNDataFetcher()
        self.odds = OddsDataFetcher(odds_api_key)
    
    def create_candidates_from_espn(self, sport: str, 
                                    game_date: str = None) -> List[Dict[str, Any]]:
        """
        Create bet candidates from ESPN schedule data.
        
        Note: ESPN provides limited odds data. Best used with Odds API
        or for tracking games without live odds.
        """
        schedule = self.espn.get_schedule(sport, game_date)
        if not schedule:
            return []
        
        candidates = []
        
        for event in schedule.get('events', []):
            event_id = event.get('id', '')
            event_name = event.get('name', '')
            
            # Get teams
            competitions = event.get('competitions', [])
            if not competitions:
                continue
            
            comp = competitions[0]
            home_team = comp.get('competitors', [{}])[0].get('team', {}).get('displayName', '')
            away_team = comp.get('competitors', [{}])[1].get('team', {}).get('displayName', '')
            
            # Get odds if available
            odds_data = comp.get('odds', {})
            # Handle case where odds is a list
            if isinstance(odds_data, list) and odds_data:
                odds_data = odds_data[0]
            if odds_data and isinstance(odds_data, dict):
                # Extract moneyline odds
                home_odds = odds_data.get('homeTeamOdds', {}).get('moneyLine', 0) if isinstance(odds_data.get('homeTeamOdds'), dict) else 0
                away_odds = odds_data.get('awayTeamOdds', {}).get('moneyLine', 0) if isinstance(odds_data.get('awayTeamOdds'), dict) else 0
                
                if home_odds and away_odds:
                    # Create candidates for both sides
                    candidates.append({
                        'bet_id': f"{event_id}-ml-home",
                        'sport': sport,
                        'event': event_name,
                        'event_id': event_id,
                        'market_type': 'moneyline',
                        'bet_type': 'moneyline',
                        'selection': home_team,
                        'selection_team': home_team,
                        'odds': int(home_odds) if home_odds else -110,
                        'home_team': home_team,
                        'away_team': away_team,
                        'model_probability': 0.5,  # Will be updated by model
                        'data_quality': 70,
                        'sample_size': 20
                    })
                    
                    candidates.append({
                        'bet_id': f"{event_id}-ml-away",
                        'sport': sport,
                        'event': event_name,
                        'event_id': event_id,
                        'market_type': 'moneyline',
                        'bet_type': 'moneyline',
                        'selection': away_team,
                        'selection_team': away_team,
                        'odds': int(away_odds) if away_odds else -110,
                        'home_team': home_team,
                        'away_team': away_team,
                        'model_probability': 0.5,
                        'data_quality': 70,
                        'sample_size': 20
                    })
        
        return candidates
    
    def get_fetcher_stats(self) -> Dict[str, Any]:
        """Get stats from all fetchers."""
        return {
            "espn": self.espn.get_stats(),
            "odds_api": self.odds.get_usage()
        }


# Global fetcher instance
fetcher = DataAggregator()
