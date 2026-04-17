"""
Team Statistics Database
Comprehensive team performance tracking for predictive modeling
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import requests
from dataclasses import dataclass, asdict

@dataclass
class TeamStats:
    """Team statistics snapshot."""
    team_id: str
    team_name: str
    sport: str
    season: str
    
    # Overall record
    wins: int = 0
    losses: int = 0
    ties: int = 0  # For NFL/NHL
    
    # Home/Away splits
    home_wins: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_losses: int = 0
    
    # Scoring (sport-specific)
    points_scored: float = 0.0  # Average per game
    points_allowed: float = 0.0  # Average per game
    
    # Recent form (last 10 games)
    last_10_wins: int = 0
    last_10_losses: int = 0
    last_10_points_scored: float = 0.0
    last_10_points_allowed: float = 0.0
    
    # Advanced metrics
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    pace: float = 0.0  # Possessions per game (NBA) or plays per game (NFL)
    
    # Streaks
    current_streak: int = 0  # Positive = winning, negative = losing
    
    # Last updated
    updated_at: str = ""


class TeamStatsManager:
    """Manage team statistics database."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "team_stats.db"
        self.db_path = str(db_path)
        self._init_database()
        
    def _init_database(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Team stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                team_name TEXT NOT NULL,
                sport TEXT NOT NULL,
                season TEXT NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                ties INTEGER DEFAULT 0,
                home_wins INTEGER DEFAULT 0,
                home_losses INTEGER DEFAULT 0,
                away_wins INTEGER DEFAULT 0,
                away_losses INTEGER DEFAULT 0,
                points_scored REAL DEFAULT 0.0,
                points_allowed REAL DEFAULT 0.0,
                last_10_wins INTEGER DEFAULT 0,
                last_10_losses INTEGER DEFAULT 0,
                last_10_points_scored REAL DEFAULT 0.0,
                last_10_points_allowed REAL DEFAULT 0.0,
                offensive_rating REAL DEFAULT 0.0,
                defensive_rating REAL DEFAULT 0.0,
                pace REAL DEFAULT 0.0,
                current_streak INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(team_id, season)
            )
        """)
        
        # Game history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT UNIQUE NOT NULL,
                sport TEXT NOT NULL,
                season TEXT NOT NULL,
                game_date TEXT NOT NULL,
                home_team_id TEXT NOT NULL,
                away_team_id TEXT NOT NULL,
                home_team_name TEXT NOT NULL,
                away_team_name TEXT NOT NULL,
                home_score INTEGER,
                away_score INTEGER,
                spread REAL,
                total REAL,
                home_spread_result TEXT,  -- 'W', 'L', 'P'
                total_result TEXT,  -- 'O', 'U', 'P'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_stats_sport ON team_stats(sport)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team_stats_season ON team_stats(season)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_history_date ON game_history(game_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_history_teams ON game_history(home_team_id, away_team_id)")
        
        conn.commit()
        conn.close()
    
    def update_team_stats(self, stats: TeamStats):
        """Update or insert team statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO team_stats (
                team_id, team_name, sport, season, wins, losses, ties,
                home_wins, home_losses, away_wins, away_losses,
                points_scored, points_allowed,
                last_10_wins, last_10_losses, last_10_points_scored, last_10_points_allowed,
                offensive_rating, defensive_rating, pace, current_streak, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            stats.team_id, stats.team_name, stats.sport, stats.season,
            stats.wins, stats.losses, stats.ties,
            stats.home_wins, stats.home_losses, stats.away_wins, stats.away_losses,
            stats.points_scored, stats.points_allowed,
            stats.last_10_wins, stats.last_10_losses, stats.last_10_points_scored, stats.last_10_points_allowed,
            stats.offensive_rating, stats.defensive_rating, stats.pace, stats.current_streak,
            stats.updated_at or datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def get_team_stats(self, team_id: str, season: str) -> Optional[TeamStats]:
        """Get team statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM team_stats 
            WHERE team_id = ? AND season = ?
        """, (team_id, season))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return TeamStats(
                team_id=row[1],
                team_name=row[2],
                sport=row[3],
                season=row[4],
                wins=row[5],
                losses=row[6],
                ties=row[7],
                home_wins=row[8],
                home_losses=row[9],
                away_wins=row[10],
                away_losses=row[11],
                points_scored=row[12],
                points_allowed=row[13],
                last_10_wins=row[14],
                last_10_losses=row[15],
                last_10_points_scored=row[16],
                last_10_points_allowed=row[17],
                offensive_rating=row[18],
                defensive_rating=row[19],
                pace=row[20],
                current_streak=row[21],
                updated_at=row[22]
            )
        return None
    
    def get_all_teams_stats(self, sport: str, season: str) -> List[TeamStats]:
        """Get all team stats for a sport/season."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM team_stats 
            WHERE sport = ? AND season = ?
        """, (sport, season))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [TeamStats(
            team_id=row[1],
            team_name=row[2],
            sport=row[3],
            season=row[4],
            wins=row[5],
            losses=row[6],
            ties=row[7],
            home_wins=row[8],
            home_losses=row[9],
            away_wins=row[10],
            away_losses=row[11],
            points_scored=row[12],
            points_allowed=row[13],
            last_10_wins=row[14],
            last_10_losses=row[15],
            last_10_points_scored=row[16],
            last_10_points_allowed=row[17],
            offensive_rating=row[18],
            defensive_rating=row[19],
            pace=row[20],
            current_streak=row[21],
            updated_at=row[22]
        ) for row in rows]
    
    def add_game_result(self, game_data: Dict[str, Any]):
        """Add a game result to history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO game_history (
                game_id, sport, season, game_date,
                home_team_id, away_team_id, home_team_name, away_team_name,
                home_score, away_score, spread, total,
                home_spread_result, total_result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_data['game_id'],
            game_data['sport'],
            game_data['season'],
            game_data['game_date'],
            game_data['home_team_id'],
            game_data['away_team_id'],
            game_data['home_team_name'],
            game_data['away_team_name'],
            game_data.get('home_score'),
            game_data.get('away_score'),
            game_data.get('spread'),
            game_data.get('total'),
            game_data.get('home_spread_result'),
            game_data.get('total_result')
        ))
        
        conn.commit()
        conn.close()
    
    def get_team_recent_games(self, team_id: str, n: int = 10) -> List[Dict]:
        """Get team's last n games."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM game_history 
            WHERE home_team_id = ? OR away_team_id = ?
            ORDER BY game_date DESC
            LIMIT ?
        """, (team_id, team_id, n))
        
        rows = cursor.fetchall()
        conn.close()
        
        games = []
        for row in rows:
            is_home = row[5] == team_id
            games.append({
                'game_id': row[1],
                'date': row[4],
                'opponent': row[7] if is_home else row[6],
                'is_home': is_home,
                'team_score': row[9] if is_home else row[10],
                'opp_score': row[10] if is_home else row[9],
                'spread': row[11],
                'total': row[12],
                'spread_result': row[13],
                'total_result': row[14]
            })
        
        return games


# Global instance
team_stats_manager = TeamStatsManager()
