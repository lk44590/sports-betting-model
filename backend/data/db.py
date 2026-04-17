"""SQLite database operations for bet tracking and performance analytics."""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent.parent / "data" / "betting.db"


@dataclass
class Bet:
    id: Optional[int]
    bet_id: str
    date: str
    sport: str
    event: str
    event_id: str
    market_type: str
    bet_type: str
    selection: str
    odds: int
    true_probability: float
    ev_pct: float
    edge_score: float
    stake: float
    stake_pct: float
    result: Optional[str] = None
    profit: Optional[float] = None
    settled_date: Optional[str] = None
    created_at: Optional[str] = None
    notes: Optional[str] = None


class BettingDatabase:
    """SQLite database for tracking all bets and performance."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def init_db(self) -> None:
        """Initialize database tables."""
        with self.get_connection() as conn:
            # Main bets table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bet_id TEXT UNIQUE NOT NULL,
                    date TEXT NOT NULL,
                    sport TEXT NOT NULL,
                    event TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    bet_type TEXT NOT NULL,
                    selection TEXT NOT NULL,
                    odds INTEGER NOT NULL,
                    true_probability REAL NOT NULL,
                    ev_pct REAL NOT NULL,
                    edge_score REAL NOT NULL,
                    stake REAL NOT NULL,
                    stake_pct REAL NOT NULL,
                    result TEXT CHECK(result IN ('win', 'loss', 'push', NULL)),
                    profit REAL,
                    settled_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            """)
            
            # Performance summary by sport
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_by_sport (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sport TEXT UNIQUE NOT NULL,
                    total_bets INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    pushes INTEGER DEFAULT 0,
                    total_staked REAL DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    roi_pct REAL DEFAULT 0,
                    hit_rate_pct REAL DEFAULT 0,
                    avg_ev_pct REAL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Performance summary by market type
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_by_market (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_type TEXT UNIQUE NOT NULL,
                    total_bets INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    pushes INTEGER DEFAULT 0,
                    total_staked REAL DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    roi_pct REAL DEFAULT 0,
                    hit_rate_pct REAL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Daily bankroll tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bankroll_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    starting_bankroll REAL NOT NULL,
                    ending_bankroll REAL NOT NULL,
                    daily_pnl REAL NOT NULL,
                    daily_roi_pct REAL NOT NULL,
                    bets_count INTEGER DEFAULT 0,
                    peak_bankroll REAL NOT NULL,
                    drawdown_pct REAL DEFAULT 0,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Model predictions for tracking accuracy
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bet_id TEXT UNIQUE NOT NULL,
                    sport TEXT NOT NULL,
                    market_type TEXT NOT NULL,
                    predicted_probability REAL NOT NULL,
                    actual_result INTEGER,  -- 1 for win, 0 for loss
                    prediction_error REAL,
                    model_version TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # API usage tracking for rate limiting
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    call_date TEXT NOT NULL,
                    calls_count INTEGER DEFAULT 1,
                    UNIQUE(api_name, endpoint, call_date)
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bets_date ON bets(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bets_sport ON bets(sport)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bets_result ON bets(result)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bets_event_id ON bets(event_id)")
    
    def insert_bet(self, bet: Bet) -> int:
        """Insert a new bet and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO bets (
                    bet_id, date, sport, event, event_id, market_type, bet_type,
                    selection, odds, true_probability, ev_pct, edge_score,
                    stake, stake_pct, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bet.bet_id, bet.date, bet.sport, bet.event, bet.event_id,
                bet.market_type, bet.bet_type, bet.selection, bet.odds,
                bet.true_probability, bet.ev_pct, bet.edge_score,
                bet.stake, bet.stake_pct, bet.notes
            ))
            return cursor.lastrowid
    
    def settle_bet(self, bet_id: str, result: str, profit: float) -> bool:
        """Update bet with result and profit."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE bets 
                SET result = ?, profit = ?, settled_date = ?
                WHERE bet_id = ?
            """, (result, profit, datetime.now().isoformat(), bet_id))
            return cursor.rowcount > 0
    
    def get_open_bets(self) -> List[Bet]:
        """Get all unsettled bets."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM bets WHERE result IS NULL ORDER BY date DESC
            """)
            rows = cursor.fetchall()
            return [self._row_to_bet(row) for row in rows]
    
    def get_bets_by_date(self, bet_date: str) -> List[Bet]:
        """Get all bets for a specific date."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM bets WHERE date = ? ORDER BY created_at DESC
            """, (bet_date,))
            rows = cursor.fetchall()
            return [self._row_to_bet(row) for row in rows]
    
    def get_settled_bets(self, days: int = 30) -> List[Bet]:
        """Get settled bets from last N days."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM bets 
                WHERE result IS NOT NULL 
                AND date >= date('now', '-{} days')
                ORDER BY settled_date DESC
            """.format(days))
            rows = cursor.fetchall()
            return [self._row_to_bet(row) for row in rows]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_bets,
                    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN result = 'push' THEN 1 ELSE 0 END) as pushes,
                    SUM(stake) as total_staked,
                    SUM(profit) as total_profit,
                    AVG(ev_pct) as avg_ev
                FROM bets WHERE result IS NOT NULL
            """)
            row = cursor.fetchone()
            
            total_bets = row[0] or 0
            wins = row[1] or 0
            losses = row[2] or 0
            pushes = row[3] or 0
            staked = row[4] or 0
            profit = row[5] or 0
            avg_ev = row[6] or 0
            
            decisions = wins + losses
            
            return {
                "total_bets": total_bets,
                "settled_bets": wins + losses + pushes,
                "open_bets": self._get_open_bets_count(conn),
                "wins": wins,
                "losses": losses,
                "pushes": pushes,
                "staked": round(staked, 2),
                "profit": round(profit, 2),
                "roi_pct": round((profit / staked * 100), 2) if staked else 0,
                "hit_rate_pct": round((wins / decisions * 100), 2) if decisions else 0,
                "avg_ev_pct": round(avg_ev, 2),
                "win_loss_ratio": round(wins / losses, 2) if losses else 0
            }
    
    def get_performance_by_sport(self) -> List[Dict[str, Any]]:
        """Get performance breakdown by sport."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    sport,
                    COUNT(*) as total_bets,
                    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                    SUM(stake) as total_staked,
                    SUM(profit) as total_profit
                FROM bets 
                WHERE result IS NOT NULL
                GROUP BY sport
                ORDER BY total_bets DESC
            """)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                sport, total, wins, losses, staked, profit = row
                decisions = wins + losses
                results.append({
                    "sport": sport,
                    "bets": total,
                    "wins": wins,
                    "losses": losses,
                    "staked": round(staked, 2),
                    "profit": round(profit, 2),
                    "roi_pct": round((profit / staked * 100), 2) if staked else 0,
                    "hit_rate_pct": round((wins / decisions * 100), 2) if decisions else 0
                })
            return results
    
    def update_bankroll(self, bankroll_date: str, starting: float, ending: float, 
                       peak: float, bets_count: int = 0) -> None:
        """Update daily bankroll record."""
        daily_pnl = ending - starting
        daily_roi = (daily_pnl / starting * 100) if starting else 0
        drawdown = ((peak - ending) / peak * 100) if peak > ending else 0
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO bankroll_history 
                (date, starting_bankroll, ending_bankroll, daily_pnl, 
                 daily_roi_pct, bets_count, peak_bankroll, drawdown_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (bankroll_date, starting, ending, daily_pnl, daily_roi, 
                  bets_count, peak, drawdown))
    
    def get_bankroll_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get bankroll history for charting."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM bankroll_history 
                WHERE date >= date('now', '-{} days')
                ORDER BY date ASC
            """.format(days))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def track_api_call(self, api_name: str, endpoint: str) -> None:
        """Track API usage for rate limiting."""
        today = date.today().isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO api_usage (api_name, endpoint, call_date, calls_count)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(api_name, endpoint, call_date) 
                DO UPDATE SET calls_count = calls_count + 1
            """, (api_name, endpoint, today))
    
    def get_api_usage_today(self, api_name: str) -> int:
        """Get today's API call count."""
        today = date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT SUM(calls_count) FROM api_usage 
                WHERE api_name = ? AND call_date = ?
            """, (api_name, today))
            result = cursor.fetchone()[0]
            return result or 0
    
    def _get_open_bets_count(self, conn) -> int:
        """Helper to get count of open bets."""
        cursor = conn.execute("SELECT COUNT(*) FROM bets WHERE result IS NULL")
        return cursor.fetchone()[0] or 0
    
    def _row_to_bet(self, row: sqlite3.Row) -> Bet:
        """Convert database row to Bet dataclass."""
        return Bet(
            id=row['id'],
            bet_id=row['bet_id'],
            date=row['date'],
            sport=row['sport'],
            event=row['event'],
            event_id=row['event_id'],
            market_type=row['market_type'],
            bet_type=row['bet_type'],
            selection=row['selection'],
            odds=row['odds'],
            true_probability=row['true_probability'],
            ev_pct=row['ev_pct'],
            edge_score=row['edge_score'],
            stake=row['stake'],
            stake_pct=row['stake_pct'],
            result=row['result'],
            profit=row['profit'],
            settled_date=row['settled_date'],
            created_at=row['created_at'],
            notes=row['notes']
        )


# Global database instance
db = BettingDatabase()
