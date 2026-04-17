"""
The Odds API Integration - Live Odds Data
Free tier: 500 requests/month
Provides odds from multiple sportsbooks for comparison
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path
import hashlib

# The Odds API Configuration
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Sport mapping from our format to Odds API format
SPORT_KEYS = {
    "NBA": "basketball_nba",
    "NCAAMB": "basketball_ncaab",
    "MLB": "baseball_mlb",
    "NFL": "americanfootball_nfl",
    "NCAAF": "americanfootball_ncaaf",
    "NHL": "icehockey_nhl",
    "MLS": "soccer_usa_mls",
    "EPL": "soccer_epl",
    "La Liga": "soccer_spain_la_liga",
    "Bundesliga": "soccer_germany_bundesliga",
    "Serie A": "soccer_italy_serie_a",
    "Ligue 1": "soccer_france_ligue_one",
    "UCL": "soccer_uefa_champions_league",
}

# Reverse mapping
ODDS_TO_OUR_SPORT = {v: k for k, v in SPORT_KEYS.items()}


@dataclass
class BookOdds:
    """Odds from a specific sportsbook."""
    book_key: str
    book_title: str
    last_update: str
    home_odds: int
    away_odds: int
    draw_odds: Optional[int] = None
    spread: Optional[float] = None
    total: Optional[float] = None


@dataclass
class ConsensusLine:
    """Consensus odds across multiple books."""
    sport: str
    event_id: str
    home_team: str
    away_team: str
    commence_time: str
    
    # Consensus odds (median)
    home_consensus: int
    away_consensus: int
    
    # Best available odds
    home_best: int
    away_best: int
    best_book_home: str
    best_book_away: str
    
    # Market info
    book_count: int
    line_movement: str  # "stable", "steam", "reverse"
    sharp_indicator: float  # 0-100, higher = more sharp money


class OddsAPIManager:
    """
    Manager for The Odds API integration.
    Handles caching, rate limiting, and data enrichment.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ODDS_API_KEY')
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json'
        })
        
        # Cache settings
        self.cache_dir = Path(__file__).parent.parent.parent / "data" / "cache" / "odds_api"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = 900  # 15 minutes
        
        # Rate limit tracking
        self.requests_today = 0
        self.request_limit = 500  # Free tier
        
        # Load request count from file
        self._load_request_count()
    
    def _load_request_count(self):
        """Load today's request count from file."""
        today = datetime.now().strftime('%Y-%m-%d')
        count_file = self.cache_dir / f"requests_{today}.json"
        
        if count_file.exists():
            try:
                with open(count_file, 'r') as f:
                    data = json.load(f)
                    self.requests_today = data.get('count', 0)
            except:
                self.requests_today = 0
    
    def _save_request_count(self):
        """Save request count to file."""
        today = datetime.now().strftime('%Y-%m-%d')
        count_file = self.cache_dir / f"requests_{today}.json"
        
        with open(count_file, 'w') as f:
            json.dump({'count': self.requests_today, 'date': today}, f)
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate cache key."""
        key_str = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached response if valid."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                
            # Check TTL
            cached_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
            if (datetime.now() - cached_time).seconds > self.cache_ttl:
                return None
            
            return cached.get('data')
        except:
            return None
    
    def _set_cached(self, cache_key: str, data: Any):
        """Cache response."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }, f)
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def clear_cache(self):
        """Clear all cached data to force fresh fetches."""
        try:
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                print("🧹 Cleared Odds API cache")
                return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Any]:
        """Make API request with caching and rate limiting."""
        if not self.api_key:
            print(f"❌ No Odds API key configured. Set ODDS_API_KEY environment variable.")
            return None
        
        if self.requests_today >= self.request_limit:
            print(f"⚠️ Odds API rate limit reached ({self.request_limit}/day)")
            return None
        
        # Check cache
        cache_key = self._get_cache_key(endpoint, params or {})
        cached = self._get_cached(cache_key)
        if cached is not None:
            print(f"📦 Using cached data for {endpoint}")
            return cached
        
        print(f"🌐 Making Odds API request: {endpoint}")
        
        # Make request
        url = f"{ODDS_API_BASE}/{endpoint}"
        request_params = params or {}
        request_params['apiKey'] = self.api_key
        
        try:
            response = self.session.get(url, params=request_params, timeout=15)
            
            # Update rate limit info
            remaining = response.headers.get('x-requests-remaining')
            if remaining:
                print(f"Odds API calls remaining today: {remaining}")
            
            response.raise_for_status()
            data = response.json()
            
            # Track request
            self.requests_today += 1
            self._save_request_count()
            
            # Cache response
            self._set_cached(cache_key, data)
            
            return data
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                print("Invalid Odds API key")
            elif response.status_code == 429:
                print("Odds API rate limit exceeded")
            else:
                print(f"Odds API error: {e}")
            return None
        except Exception as e:
            print(f"Odds API request failed: {e}")
            return None
    
    def get_sports(self) -> List[Dict]:
        """Get list of available sports."""
        return self._make_request("sports") or []
    
    def get_odds(self, 
                 sport: str, 
                 regions: str = "us",
                 markets: str = "h2h",
                 odds_format: str = "american",
                 date_format: str = "iso") -> Optional[List[Dict]]:
        """
        Get odds for a sport.
        
        Args:
            sport: Our sport key (NBA, MLB, etc.)
            regions: 'us', 'uk', 'eu', 'au' or comma-separated
            markets: 'h2h' (moneyline), 'spreads', 'totals', 'outrights'
            odds_format: 'american' or 'decimal'
            date_format: 'iso' or 'unix'
        """
        sport_key = SPORT_KEYS.get(sport)
        if not sport_key:
            print(f"Unknown sport: {sport}")
            return None
        
        endpoint = f"sports/{sport_key}/odds"
        params = {
            'regions': regions,
            'markets': markets,
            'oddsFormat': odds_format,
            'dateFormat': date_format
        }
        
        return self._make_request(endpoint, params)
    
    def get_all_odds(self, 
                    sports: List[str] = None,
                    regions: str = "us",
                    markets: str = "h2h") -> Dict[str, List[Dict]]:
        """
        Get odds for multiple sports efficiently.
        Prioritizes high-EV sports first.
        """
        if sports is None:
            sports = ["NBA", "NFL", "MLB", "NHL"]
        
        results = {}
        
        for sport in sports:
            print(f"Fetching odds for {sport}...")
            odds = self.get_odds(sport, regions, markets)
            if odds:
                results[sport] = odds
                print(f"  Found {len(odds)} events")
            
            # Stop if approaching rate limit
            if self.requests_today >= self.request_limit - 10:
                print("Approaching rate limit, stopping")
                break
        
        return results
    
    def parse_event_odds(self, event_data: Dict) -> Dict[str, Any]:
        """
        Parse raw event data into structured format.
        """
        sport_key = event_data.get('sport_key', '')
        sport = ODDS_TO_OUR_SPORT.get(sport_key, sport_key)
        
        home_team = event_data.get('home_team', '')
        away_team = event_data.get('away_team', '')
        commence_time = event_data.get('commence_time', '')
        event_id = event_data.get('id', '')
        
        # Parse bookmaker odds
        bookmakers = event_data.get('bookmakers', [])
        
        odds_by_book = {}
        for book in bookmakers:
            book_key = book.get('key', '')
            book_title = book.get('title', '')
            
            # Get moneyline (h2h) markets
            h2h_market = None
            for market in book.get('markets', []):
                if market.get('key') == 'h2h':
                    h2h_market = market
                    break
            
            if h2h_market:
                outcomes = h2h_market.get('outcomes', [])
                home_odds = None
                away_odds = None
                
                for outcome in outcomes:
                    if outcome.get('name') == home_team:
                        home_odds = int(outcome.get('price', 0))
                    elif outcome.get('name') == away_team:
                        away_odds = int(outcome.get('price', 0))
                
                if home_odds and away_odds:
                    odds_by_book[book_key] = {
                        'book': book_title,
                        'home': home_odds,
                        'away': away_odds,
                        'last_update': book.get('last_update', '')
                    }
        
        # Calculate consensus (median) odds
        home_odds_list = [v['home'] for v in odds_by_book.values()]
        away_odds_list = [v['away'] for v in odds_by_book.values()]
        
        consensus = {
            'home': int(sorted(home_odds_list)[len(home_odds_list)//2]) if home_odds_list else 0,
            'away': int(sorted(away_odds_list)[len(away_odds_list)//2]) if away_odds_list else 0
        }
        
        # Find best odds
        best_home = max(home_odds_list) if home_odds_list else 0
        best_away = max(away_odds_list) if away_odds_list else 0
        
        best_home_book = next((k for k, v in odds_by_book.items() if v['home'] == best_home), '')
        best_away_book = next((k for k, v in odds_by_book.items() if v['away'] == best_away), '')
        
        return {
            'sport': sport,
            'event_id': event_id,
            'home_team': home_team,
            'away_team': away_team,
            'commence_time': commence_time,
            'bookmakers': bookmakers,
            'odds_by_book': odds_by_book,
            'consensus': consensus,
            'best_home': best_home,
            'best_away': best_away,
            'best_home_book': best_home_book,
            'best_away_book': best_away_book,
            'book_count': len(bookmakers)
        }
    
    def convert_to_candidates(self, odds_data: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Convert Odds API data to our candidate format.
        """
        candidates = []
        
        for sport, events in odds_data.items():
            for event in events:
                parsed = self.parse_event_odds(event)
                
                if not parsed['consensus']['home'] or not parsed['consensus']['away']:
                    continue
                
                # Create candidate for home team
                candidates.append({
                    'bet_id': f"{parsed['event_id']}-ml-home",
                    'sport': sport,
                    'event': f"{parsed['home_team']} vs {parsed['away_team']}",
                    'event_id': parsed['event_id'],
                    'market_type': 'moneyline',
                    'bet_type': 'moneyline',
                    'selection': parsed['home_team'],
                    'selection_team': parsed['home_team'],
                    'odds': parsed['consensus']['home'],
                    'best_odds': parsed['best_home'],
                    'best_book': parsed['best_home_book'],
                    'home_team': parsed['home_team'],
                    'away_team': parsed['away_team'],
                    'commence_time': parsed['commence_time'],
                    'model_probability': 0.5,  # Will be updated by model
                    'data_quality': 85,  # Higher quality with real odds
                    'sample_size': 30,
                    'book_count': parsed['book_count'],
                    'odds_source': 'odds_api'
                })
                
                # Create candidate for away team
                candidates.append({
                    'bet_id': f"{parsed['event_id']}-ml-away",
                    'sport': sport,
                    'event': f"{parsed['home_team']} vs {parsed['away_team']}",
                    'event_id': parsed['event_id'],
                    'market_type': 'moneyline',
                    'bet_type': 'moneyline',
                    'selection': parsed['away_team'],
                    'selection_team': parsed['away_team'],
                    'odds': parsed['consensus']['away'],
                    'best_odds': parsed['best_away'],
                    'best_book': parsed['best_away_book'],
                    'home_team': parsed['home_team'],
                    'away_team': parsed['away_team'],
                    'commence_time': parsed['commence_time'],
                    'model_probability': 0.5,
                    'data_quality': 85,
                    'sample_size': 30,
                    'book_count': parsed['book_count'],
                    'odds_source': 'odds_api'
                })
        
        return candidates
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        return {
            'requests_today': self.requests_today,
            'request_limit': self.request_limit,
            'remaining_today': max(0, self.request_limit - self.requests_today),
            'api_key_configured': self.api_key is not None,
            'cache_ttl_seconds': self.cache_ttl
        }


# Global instance
odds_manager = OddsAPIManager()


def get_live_odds_for_sports(sports: List[str] = None) -> List[Dict]:
    """
    Convenience function to get live odds and convert to candidates.
    """
    if sports is None:
        sports = ["NBA", "NFL", "MLB", "NHL"]
    
    # Fetch odds
    odds_data = odds_manager.get_all_odds(sports)
    
    # Convert to candidates
    candidates = odds_manager.convert_to_candidates(odds_data)
    
    print(f"Converted {len(candidates)} candidates from Odds API")
    
    return candidates


def test_odds_api():
    """Test function to verify Odds API integration."""
    print("Testing Odds API Integration")
    print("=" * 60)
    
    # Check if API key is configured
    stats = odds_manager.get_usage_stats()
    print(f"API Key configured: {stats['api_key_configured']}")
    print(f"Requests today: {stats['requests_today']}/{stats['request_limit']}")
    
    if not stats['api_key_configured']:
        print("\nTo use The Odds API:")
        print("1. Sign up at https://the-odds-api.com/")
        print("2. Get free API key (500 requests/month)")
        print("3. Set environment variable: ODDS_API_KEY=your_key")
        print("4. Or modify backend/data/odds_api_integration.py")
        return
    
    # Test fetching odds
    print("\nFetching NBA odds...")
    nba_odds = odds_manager.get_odds("NBA")
    
    if nba_odds:
        print(f"Found {len(nba_odds)} NBA events")
        
        # Show first event details
        if nba_odds:
            first = nba_odds[0]
            parsed = odds_manager.parse_event_odds(first)
            print(f"\nExample: {parsed['home_team']} vs {parsed['away_team']}")
            print(f"  Home odds: {parsed['consensus']['home']} (best: {parsed['best_home']} at {parsed['best_home_book']})")
            print(f"  Away odds: {parsed['consensus']['away']} (best: {parsed['best_away']} at {parsed['best_away_book']})")
            print(f"  Books offering lines: {parsed['book_count']}")
    else:
        print("No odds data returned")
    
    print("\nUsage stats:")
    stats = odds_manager.get_usage_stats()
    print(f"  Remaining today: {stats['remaining_today']}")


if __name__ == "__main__":
    test_odds_api()
