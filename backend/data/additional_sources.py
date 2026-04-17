"""
Additional data sources for more comprehensive sports coverage.
Expands beyond ESPN to include more sports and data types.
"""

import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import json

# Additional data sources (free tiers)
DATA_SOURCES = {
    "sportsdataio": {
        "base_url": "https://api.sportsdata.io/v3",
        "sports": ["nfl", "nba", "mlb", "nhl"],
        "requires_key": True
    },
    "api_football": {
        "base_url": "https://v3.football.api-sports.io",
        "sports": ["soccer"],
        "requires_key": True
    },
    "rugby_api": {
        "base_url": "https://v1.rugby.api-sports.io",
        "sports": ["rugby"],
        "requires_key": True
    }
}

# Sport-specific ESPN extensions
SPORT_EXTENSIONS = {
    "tennis": {
        "atp_rankings": "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/rankings",
        "wta_rankings": "https://site.api.espn.com/apis/site/v2/sports/tennis/wta/rankings",
        "events": "https://site.api.espn.com/apis/site/v2/sports/tennis/all/scoreboard"
    },
    "mma": {
        "ufc_rankings": "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/rankings",
        "events": "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
    },
    "golf": {
        "pga_rankings": "https://site.api.espn.com/apis/site/v2/sports/golf/pga/rankings",
        "events": "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"
    },
    "wnba": {
        "scoreboard": "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
        "standings": "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/standings"
    }
}


class ExtendedDataFetcher:
    """
    Extended data fetcher with additional sports coverage.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_tennis_events(self) -> Optional[Dict]:
        """Fetch tennis events from ESPN."""
        try:
            url = SPORT_EXTENSIONS["tennis"]["events"]
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching tennis events: {e}")
            return None
    
    def get_mma_events(self) -> Optional[Dict]:
        """Fetch MMA/UFC events from ESPN."""
        try:
            url = SPORT_EXTENSIONS["mma"]["events"]
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching MMA events: {e}")
            return None
    
    def get_golf_events(self) -> Optional[Dict]:
        """Fetch golf events from ESPN."""
        try:
            url = SPORT_EXTENSIONS["golf"]["events"]
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching golf events: {e}")
            return None
    
    def get_wnba_games(self, date: str = None) -> Optional[Dict]:
        """Fetch WNBA games."""
        try:
            url = SPORT_EXTENSIONS["wnba"]["scoreboard"]
            params = {}
            if date:
                params['dates'] = date
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching WNBA games: {e}")
            return None
    
    def get_player_stats(self, sport: str, player_id: str) -> Optional[Dict]:
        """Get detailed player statistics."""
        sport_paths = {
            "nba": "basketball/nba",
            "mlb": "baseball/mlb",
            "nfl": "football/nfl",
            "nhl": "hockey/nhl"
        }
        
        if sport.lower() not in sport_paths:
            return None
        
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_paths[sport.lower()]}/athletes/{player_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching player stats: {e}")
            return None
    
    def get_team_injuries(self, sport: str, team_id: str) -> Optional[List[Dict]]:
        """Get team injury report."""
        try:
            # ESPN injuries endpoint
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/teams/{team_id}/injuries"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('injuries', [])
        except Exception as e:
            print(f"Error fetching injuries: {e}")
            return None
    
    def get_weather_for_game(self, venue_id: str, game_time: str) -> Optional[Dict]:
        """
        Get weather forecast for outdoor games.
        Uses OpenWeatherMap API (requires free API key).
        """
        # This would integrate with weather API
        # For now, return placeholder
        return {
            "temperature": 72,
            "condition": "Clear",
            "wind_speed": 5,
            "precipitation_chance": 0
        }


class DataEnricher:
    """
    Enrich betting candidates with additional data.
    """
    
    def __init__(self):
        self.extended = ExtendedDataFetcher()
    
    def enrich_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add additional data to a betting candidate.
        """
        sport = candidate.get('sport', '').lower()
        
        # Add injury data if available
        if sport in ['nba', 'nfl', 'nhl', 'mlb']:
            injuries = self._get_injury_impact(sport, candidate)
            if injuries:
                candidate['injury_notes'] = injuries
                # Adjust quality score based on injuries
                candidate['data_quality'] = min(100, candidate.get('data_quality', 75) + 5)
        
        # Add weather for outdoor sports
        if sport in ['nfl', 'mlb', 'golf']:
            weather = self._get_weather_impact(sport, candidate)
            if weather:
                candidate['weather'] = weather
        
        # Add player rest days for NBA
        if sport == 'nba':
            rest_impact = self._calculate_rest_advantage(candidate)
            if rest_impact:
                candidate['rest_advantage'] = rest_impact
        
        return candidate
    
    def _get_injury_impact(self, sport: str, candidate: Dict) -> Optional[str]:
        """Assess injury impact on the game."""
        # This would integrate with real injury data
        # Return placeholder for now
        return None
    
    def _get_weather_impact(self, sport: str, candidate: Dict) -> Optional[str]:
        """Assess weather impact on the game."""
        # Weather factors:
        # - Wind for baseball totals
        # - Temperature for football
        # - Rain for outdoor sports
        return None
    
    def _calculate_rest_advantage(self, candidate: Dict) -> Optional[Dict]:
        """
        Calculate rest day advantage for NBA.
        Teams with more rest perform better.
        """
        # This would calculate days since last game
        return None
    
    def get_line_movement(self, candidate: Dict) -> Optional[Dict]:
        """
        Track line movement for a candidate.
        Significant movement can indicate sharp money.
        """
        return {
            "open_odds": candidate.get('odds'),
            "current_odds": candidate.get('odds'),
            "line_movement": 0,
            "movement_pct": 0
        }


class AlternativeMarkets:
    """
    Identify alternative betting markets.
    """
    
    @staticmethod
    def get_derivative_markets(candidate: Dict) -> List[Dict]:
        """
        Identify derivative markets for a game.
        e.g., if moneyline is good, check team totals, player props
        """
        derivatives = []
        
        sport = candidate.get('sport', '').upper()
        
        if sport == 'NBA':
            # For NBA games, also consider:
            # - Team totals
            # - First half lines
            # - Player props (points, rebounds, assists)
            derivatives.append({
                "market_type": "team_total",
                "reasoning": "Correlated with moneyline"
            })
        
        elif sport == 'MLB':
            # For MLB games:
            # - Pitcher strikeout props
            # - First 5 innings
            # - Run line alternative
            derivatives.append({
                "market_type": "f5_ml",
                "reasoning": "Pitcher-focused"
            })
        
        elif sport == 'NFL':
            # For NFL games:
            # - Team totals
            # - First quarter
            # - Player props
            derivatives.append({
                "market_type": "team_total",
                "reasoning": "Game script correlated"
            })
        
        return derivatives
    
    @staticmethod
    def get_correlated_bets(candidates: List[Dict]) -> List[List[Dict]]:
        """
        Identify groups of correlated bets.
        e.g., moneyline + over for high-scoring games
        """
        correlations = []
        
        # Group by event
        by_event = {}
        for c in candidates:
            event = c.get('event_id', c.get('event'))
            if event not in by_event:
                by_event[event] = []
            by_event[event].append(c)
        
        # Find correlations within events
        for event, bets in by_event.items():
            if len(bets) >= 2:
                correlations.append(bets)
        
        return correlations


# Global instance
extended_fetcher = ExtendedDataFetcher()
data_enricher = DataEnricher()
