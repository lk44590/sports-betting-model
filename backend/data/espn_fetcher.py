"""
ESPN Data Fetcher - Team Statistics and Historical Data
Fetches comprehensive team stats from ESPN API
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from .team_stats import TeamStats, team_stats_manager

# ESPN API Endpoints
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"

SPORT_ENDPOINTS = {
    "MLB": "baseball/mlb",
    "NBA": "basketball/nba",
    "NFL": "football/nfl",
    "NHL": "hockey/nhl",
    "NCAAMB": "basketball/mens-college-basketball",
    "NCAAF": "football/college-football"
}


class ESPNStatsFetcher:
    """Fetch team statistics from ESPN."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_team_list(self, sport: str) -> List[Dict]:
        """Get list of teams for a sport."""
        if sport not in SPORT_ENDPOINTS:
            return []
        
        endpoint = SPORT_ENDPOINTS[sport]
        url = f"{ESPN_BASE}/{endpoint}/teams"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            teams = []
            for team_data in data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', []):
                team = team_data.get('team', {})
                teams.append({
                    'id': str(team.get('id', '')),
                    'name': team.get('displayName', ''),
                    'abbreviation': team.get('abbreviation', ''),
                    'location': team.get('location', '')
                })
            
            return teams
        except Exception as e:
            print(f"Error fetching team list for {sport}: {e}")
            return []
    
    def get_team_stats(self, sport: str, team_id: str, season: Optional[str] = None) -> Optional[Dict]:
        """Get detailed team statistics."""
        if sport not in SPORT_ENDPOINTS:
            return None
        
        if season is None:
            season = str(datetime.now().year)
        
        endpoint = SPORT_ENDPOINTS[sport]
        url = f"{ESPN_BASE}/{endpoint}/teams/{team_id}/schedule"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract record and recent form
            events = data.get('events', [])
            
            wins = 0
            losses = 0
            home_wins = 0
            home_losses = 0
            away_wins = 0
            away_losses = 0
            
            points_scored = []
            points_allowed = []
            
            recent_games = events[-10:] if len(events) >= 10 else events
            
            for event in events:
                competition = event.get('competitions', [{}])[0]
                
                # Determine if team is home or away
                home_team = competition.get('competitors', [{}])[0]
                away_team = competition.get('competitors', [{}])[1] if len(competition.get('competitors', [])) > 1 else {}
                
                is_home = str(home_team.get('team', {}).get('id', '')) == team_id
                
                team_score = home_team.get('score', {}).get('value', 0) if is_home else away_team.get('score', {}).get('value', 0)
                opp_score = away_team.get('score', {}).get('value', 0) if is_home else home_team.get('score', {}).get('value', 0)
                
                if team_score and opp_score:
                    points_scored.append(int(team_score))
                    points_allowed.append(int(opp_score))
                    
                    if int(team_score) > int(opp_score):
                        wins += 1
                        if is_home:
                            home_wins += 1
                        else:
                            away_wins += 1
                    else:
                        losses += 1
                        if is_home:
                            home_losses += 1
                        else:
                            away_losses += 1
            
            # Calculate averages
            avg_points_scored = sum(points_scored) / len(points_scored) if points_scored else 0
            avg_points_allowed = sum(points_allowed) / len(points_allowed) if points_allowed else 0
            
            # Recent form (last 10)
            last_10_wins = 0
            last_10_losses = 0
            for event in recent_games:
                competition = event.get('competitions', [{}])[0]
                home_team = competition.get('competitors', [{}])[0]
                away_team = competition.get('competitors', [{}])[1] if len(competition.get('competitors', [])) > 1 else {}
                
                is_home = str(home_team.get('team', {}).get('id', '')) == team_id
                team_score = home_team.get('score', {}).get('value', 0) if is_home else away_team.get('score', {}).get('value', 0)
                opp_score = away_team.get('score', {}).get('value', 0) if is_home else home_team.get('score', {}).get('value', 0)
                
                if team_score and opp_score:
                    if int(team_score) > int(opp_score):
                        last_10_wins += 1
                    else:
                        last_10_losses += 1
            
            # Current streak
            streak = 0
            for event in reversed(events):
                competition = event.get('competitions', [{}])[0]
                home_team = competition.get('competitors', [{}])[0]
                away_team = competition.get('competitors', [{}])[1] if len(competition.get('competitors', [])) > 1 else {}
                
                is_home = str(home_team.get('team', {}).get('id', '')) == team_id
                team_score = home_team.get('score', {}).get('value', 0) if is_home else away_team.get('score', {}).get('value', 0)
                opp_score = away_team.get('score', {}).get('value', 0) if is_home else home_team.get('score', {}).get('value', 0)
                
                if team_score and opp_score:
                    if int(team_score) > int(opp_score):
                        if streak <= 0:
                            streak = 1
                        else:
                            streak += 1
                    else:
                        if streak >= 0:
                            streak = -1
                        else:
                            streak -= 1
            
            return {
                'wins': wins,
                'losses': losses,
                'home_wins': home_wins,
                'home_losses': home_losses,
                'away_wins': away_wins,
                'away_losses': away_losses,
                'points_scored': avg_points_scored,
                'points_allowed': avg_points_allowed,
                'last_10_wins': last_10_wins,
                'last_10_losses': last_10_losses,
                'current_streak': streak,
                'games_played': wins + losses
            }
            
        except Exception as e:
            print(f"Error fetching team stats for {team_id}: {e}")
            return None
    
    def update_all_team_stats(self, sport: str, season: Optional[str] = None):
        """Update stats for all teams in a sport."""
        if season is None:
            season = str(datetime.now().year)
        
        print(f"Fetching team stats for {sport}...")
        teams = self.get_team_list(sport)
        
        for team in teams:
            team_id = team['id']
            team_name = team['name']
            
            stats_data = self.get_team_stats(sport, team_id, season)
            
            if stats_data:
                team_stats = TeamStats(
                    team_id=team_id,
                    team_name=team_name,
                    sport=sport,
                    season=season,
                    wins=stats_data['wins'],
                    losses=stats_data['losses'],
                    home_wins=stats_data['home_wins'],
                    home_losses=stats_data['home_losses'],
                    away_wins=stats_data['away_wins'],
                    away_losses=stats_data['away_losses'],
                    points_scored=stats_data['points_scored'],
                    points_allowed=stats_data['points_allowed'],
                    last_10_wins=stats_data['last_10_wins'],
                    last_10_losses=stats_data['last_10_losses'],
                    current_streak=stats_data['current_streak'],
                    updated_at=datetime.now().isoformat()
                )
                
                team_stats_manager.update_team_stats(team_stats)
                print(f"  Updated {team_name}: {stats_data['wins']}-{stats_data['losses']}")


# Global instance
espn_fetcher = ESPNStatsFetcher()
