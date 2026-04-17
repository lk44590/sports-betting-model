"""
Backtesting Framework
Validate model performance on historical data
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

@dataclass
class BacktestResult:
    """Results of a backtest simulation."""
    total_bets: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    total_staked: float
    total_return: float
    profit: float
    roi: float
    max_drawdown: float
    sharpe_ratio: float
    
    # By bet type
    ml_results: Dict[str, Any]
    spread_results: Dict[str, Any]
    total_results: Dict[str, Any]
    
    # By sport
    sport_results: Dict[str, Dict[str, Any]]


class Backtester:
    """
    Backtest betting model on historical data.
    Simulates betting with proper bankroll management.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "backtest.db"
        self.db_path = str(db_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize backtest database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Historical bets (simulated or actual)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historical_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bet_id TEXT UNIQUE NOT NULL,
                date TEXT NOT NULL,
                sport TEXT NOT NULL,
                bet_type TEXT NOT NULL,  -- 'ml', 'spread', 'total'
                selection TEXT NOT NULL,
                odds INTEGER NOT NULL,
                stake REAL NOT NULL,
                result TEXT,  -- 'win', 'loss', 'push', 'pending'
                profit REAL DEFAULT 0,
                model_prob REAL,  -- Model's predicted probability
                actual_prob REAL,  -- For validation (if known)
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Daily bankroll snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bankroll_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                starting_bankroll REAL NOT NULL,
                ending_bankroll REAL NOT NULL,
                total_bets INTEGER DEFAULT 0,
                daily_profit REAL DEFAULT 0,
                max_drawdown REAL DEFAULT 0
            )
        """)
        
        conn.commit()
        conn.close()
    
    def record_bet(self, bet_data: Dict[str, Any]):
        """Record a bet in history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO historical_bets 
            (bet_id, date, sport, bet_type, selection, odds, stake, result, profit, model_prob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bet_data['bet_id'],
            bet_data['date'],
            bet_data['sport'],
            bet_data['bet_type'],
            bet_data['selection'],
            bet_data['odds'],
            bet_data['stake'],
            bet_data.get('result', 'pending'),
            bet_data.get('profit', 0),
            bet_data.get('model_prob')
        ))
        
        conn.commit()
        conn.close()
    
    def update_bet_result(self, bet_id: str, result: str, profit: float):
        """Update a bet with its result."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE historical_bets 
            SET result = ?, profit = ?
            WHERE bet_id = ?
        """, (result, profit, bet_id))
        
        conn.commit()
        conn.close()
    
    def run_backtest(self, start_date: str, end_date: str, 
                     initial_bankroll: float = 1000.0,
                     kelly_fraction: float = 0.2) -> BacktestResult:
        """
        Run backtest simulation over date range.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all bets in date range
        cursor.execute("""
            SELECT * FROM historical_bets 
            WHERE date >= ? AND date <= ? AND result != 'pending'
            ORDER BY date
        """, (start_date, end_date))
        
        bets = cursor.fetchall()
        conn.close()
        
        if not bets:
            print("No bets found for backtest period")
            return None
        
        # Simulate bankroll
        bankroll = initial_bankroll
        max_bankroll = initial_bankroll
        max_drawdown = 0.0
        daily_returns = []
        
        total_bets = 0
        wins = 0
        losses = 0
        pushes = 0
        total_staked = 0.0
        total_profit = 0.0
        
        # By bet type
        ml_bets = {'total': 0, 'wins': 0, 'profit': 0}
        spread_bets = {'total': 0, 'wins': 0, 'profit': 0}
        total_bets_by_type = {'total': 0, 'wins': 0, 'profit': 0}
        
        # By sport
        sport_stats = {}
        
        current_date = None
        daily_profit = 0
        
        for bet in bets:
            bet_date = bet[2]
            sport = bet[3]
            bet_type = bet[4]
            odds = bet[6]
            stake = bet[7]
            result = bet[8]
            profit = bet[9] if bet[9] else 0
            
            # New day - track daily return
            if bet_date != current_date:
                if current_date:
                    daily_returns.append(daily_profit / bankroll if bankroll > 0 else 0)
                current_date = bet_date
                daily_profit = 0
            
            total_bets += 1
            total_staked += stake
            daily_profit += profit
            total_profit += profit
            bankroll += profit
            
            # Track max drawdown
            if bankroll > max_bankroll:
                max_bankroll = bankroll
            drawdown = (max_bankroll - bankroll) / max_bankroll
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            
            # Track results
            if result == 'win':
                wins += 1
            elif result == 'loss':
                losses += 1
            elif result == 'push':
                pushes += 1
            
            # By bet type
            if bet_type == 'ml':
                ml_bets['total'] += 1
                if result == 'win':
                    ml_bets['wins'] += 1
                ml_bets['profit'] += profit
            elif bet_type == 'spread':
                spread_bets['total'] += 1
                if result == 'win':
                    spread_bets['wins'] += 1
                spread_bets['profit'] += profit
            elif bet_type == 'total':
                total_bets_by_type['total'] += 1
                if result == 'win':
                    total_bets_by_type['wins'] += 1
                total_bets_by_type['profit'] += profit
            
            # By sport
            if sport not in sport_stats:
                sport_stats[sport] = {'total': 0, 'wins': 0, 'profit': 0}
            sport_stats[sport]['total'] += 1
            if result == 'win':
                sport_stats[sport]['wins'] += 1
            sport_stats[sport]['profit'] += profit
        
        # Calculate metrics
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        roi = (total_profit / total_staked) * 100 if total_staked > 0 else 0
        
        # Sharpe ratio (simplified)
        if daily_returns:
            avg_return = sum(daily_returns) / len(daily_returns)
            variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
            std_dev = variance ** 0.5
            sharpe = (avg_return / std_dev) * (365 ** 0.5) if std_dev > 0 else 0  # Annualized
        else:
            sharpe = 0
        
        # Calculate win rates for breakdowns
        ml_win_rate = ml_bets['wins'] / ml_bets['total'] if ml_bets['total'] > 0 else 0
        spread_win_rate = spread_bets['wins'] / spread_bets['total'] if spread_bets['total'] > 0 else 0
        total_win_rate = total_bets_by_type['wins'] / total_bets_by_type['total'] if total_bets_by_type['total'] > 0 else 0
        
        return BacktestResult(
            total_bets=total_bets,
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=win_rate,
            total_staked=total_staked,
            total_return=total_profit + total_staked,
            profit=total_profit,
            roi=roi,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            ml_results={
                'total': ml_bets['total'],
                'win_rate': ml_win_rate,
                'profit': ml_bets['profit'],
                'roi': (ml_bets['profit'] / total_staked * 100) if total_staked > 0 else 0
            },
            spread_results={
                'total': spread_bets['total'],
                'win_rate': spread_win_rate,
                'profit': spread_bets['profit'],
                'roi': (spread_bets['profit'] / total_staked * 100) if total_staked > 0 else 0
            },
            total_results={
                'total': total_bets_by_type['total'],
                'win_rate': total_win_rate,
                'profit': total_bets_by_type['profit'],
                'roi': (total_bets_by_type['profit'] / total_staked * 100) if total_staked > 0 else 0
            },
            sport_results=sport_stats
        )
    
    def print_backtest_report(self, result: BacktestResult):
        """Print formatted backtest report."""
        print("\n" + "=" * 70)
        print("BACKTEST RESULTS")
        print("=" * 70)
        print(f"Total Bets:        {result.total_bets}")
        print(f"Wins:              {result.wins}")
        print(f"Losses:            {result.losses}")
        print(f"Pushes:            {result.pushes}")
        print(f"Win Rate:          {result.win_rate:.1%}")
        print(f"\nTotal Staked:      ${result.total_staked:,.2f}")
        print(f"Total Profit:      ${result.profit:,.2f}")
        print(f"ROI:               {result.roi:.2f}%")
        print(f"Max Drawdown:      {result.max_drawdown:.1%}")
        print(f"Sharpe Ratio:      {result.sharpe_ratio:.2f}")
        
        print("\n--- By Bet Type ---")
        print(f"Moneyline:         {result.ml_results['total']} bets, "
              f"{result.ml_results['win_rate']:.1%} win rate, "
              f"${result.ml_results['profit']:,.2f} profit")
        print(f"Spread:            {result.spread_results['total']} bets, "
              f"{result.spread_results['win_rate']:.1%} win rate, "
              f"${result.spread_results['profit']:,.2f} profit")
        print(f"Totals:            {result.total_results['total']} bets, "
              f"{result.total_results['win_rate']:.1%} win rate, "
              f"${result.total_results['profit']:,.2f} profit")
        
        print("\n--- By Sport ---")
        for sport, stats in result.sport_results.items():
            win_rate = stats['wins'] / stats['total'] if stats['total'] > 0 else 0
            print(f"{sport:15s} {stats['total']:3d} bets, "
                  f"{win_rate:.1%} win rate, "
                  f"${stats['profit']:,.2f} profit")
        
        print("=" * 70)
        
        # ROI assessment
        if result.roi > 5:
            print("✅ EXCELLENT: ROI above 5% - world class performance")
        elif result.roi > 2:
            print("✅ GOOD: ROI above 2% - profitable long-term")
        elif result.roi > 0:
            print("⚠️ MARGINAL: ROI positive but below 2% - high variance risk")
        else:
            print("❌ POOR: Negative ROI - model needs improvement")
        
        print("=" * 70 + "\n")


# Global instance
backtester = Backtester()
