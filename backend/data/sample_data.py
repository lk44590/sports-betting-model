"""
Sample data generator for testing and demonstration.
Creates realistic bet scenarios with proper EV calculations.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import random


def generate_sample_bets(count: int = 50) -> List[Dict[str, Any]]:
    """Generate sample bet history for demonstration."""
    
    sports = ["NBA", "NHL", "MLB", "NFL", "NCAAMB"]
    teams = {
        "NBA": ["Lakers", "Warriors", "Celtics", "Heat", "Bucks", "Nuggets", "Suns", "Knicks"],
        "NHL": ["Avalanche", "Rangers", "Hurricanes", "Stars", "Panthers", "Oilers", "Leafs", "Bruins"],
        "MLB": ["Yankees", "Dodgers", "Astros", "Braves", "Orioles", "Phillies", "Blue Jays", "Rangers"],
        "NFL": ["Chiefs", "Ravens", "49ers", "Lions", "Bills", "Eagles", "Dolphins", "Packers"],
        "NCAAMB": ["UConn", "Purdue", "Houston", "Auburn", "Arizona", "Duke", "UNC", "Kentucky"]
    }
    
    bets = []
    base_date = datetime.now() - timedelta(days=30)
    
    # Generate winning record with positive ROI
    for i in range(count):
        sport = random.choice(sports)
        team1, team2 = random.sample(teams[sport], 2)
        
        # Create realistic scenario
        is_home = random.choice([True, False])
        selection = team1 if is_home else team2
        opponent = team2 if is_home else team1
        
        # Generate realistic odds and EV
        odds = random.choice([-140, -130, -120, -110, -105, +100, +110, +120, +140])
        
        # Higher true prob for favorites, lower for dogs
        if odds < 0:
            true_prob = random.uniform(0.55, 0.68)
        else:
            true_prob = random.uniform(0.42, 0.48)
        
        # Calculate EV
        if odds > 0:
            profit_mult = odds / 100
        else:
            profit_mult = 100 / abs(odds)
        
        ev_pct = (true_prob * profit_mult - (1 - true_prob)) * 100
        
        # Determine result (biased toward wins for demo, but realistic)
        # Win if we have edge and random factor
        win_threshold = true_prob + random.uniform(-0.15, 0.05)
        result = "win" if random.random() < win_threshold else "loss"
        
        # Calculate profit/loss
        stake = round(random.uniform(15, 50), 2)
        if result == "win":
            profit = round(stake * profit_mult, 2)
        elif result == "loss":
            profit = round(-stake, 2)
        else:
            profit = 0
        
        bet_date = (base_date + timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d')
        
        bet = {
            "bet_id": f"sample-{i+1:03d}",
            "date": bet_date,
            "sport": sport,
            "event": f"{team1} vs {team2}",
            "event_id": f"evt-{i+1}",
            "market_type": "moneyline",
            "bet_type": "moneyline",
            "selection": selection,
            "odds": odds,
            "true_probability": round(true_prob, 4),
            "ev_pct": round(ev_pct, 2),
            "edge_score": random.randint(70, 95),
            "stake": stake,
            "stake_pct": round((stake / 1000) * 100, 2),
            "result": result,
            "profit": profit,
            "settled_date": bet_date,
            "notes": "Sample data for demonstration"
        }
        
        bets.append(bet)
    
    return bets


def generate_sample_bankroll_history(days: int = 30) -> List[Dict[str, Any]]:
    """Generate sample bankroll history with upward trend."""
    
    history = []
    start_date = datetime.now() - timedelta(days=days)
    
    bankroll = 1000.00
    peak = 1000.00
    
    for i in range(days):
        date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        
        # Random daily P&L with slight upward bias
        daily_pnl = random.uniform(-30, 45)
        
        # Some days have no bets
        if random.random() < 0.3:
            daily_pnl = 0
            bets_count = 0
        else:
            bets_count = random.randint(1, 3)
        
        starting = bankroll
        bankroll += daily_pnl
        ending = bankroll
        
        if ending > peak:
            peak = ending
        
        drawdown = max(0, (peak - ending) / peak * 100)
        
        history.append({
            "date": date,
            "starting_bankroll": round(starting, 2),
            "ending_bankroll": round(ending, 2),
            "daily_pnl": round(daily_pnl, 2),
            "daily_roi_pct": round((daily_pnl / starting) * 100, 2) if starting > 0 else 0,
            "bets_count": bets_count,
            "peak_bankroll": round(peak, 2),
            "drawdown_pct": round(drawdown, 2)
        })
    
    return history


def seed_sample_data():
    """Seed the database with sample data for demonstration."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from data.db import db, Bet
    
    print("Seeding database with sample data...")
    
    # Check if data already exists
    existing = db.get_performance_summary()
    if existing['settled_bets'] > 0:
        print(f"Database already has {existing['settled_bets']} settled bets. Skipping seed.")
        return
    
    # Generate and insert sample bets
    sample_bets = generate_sample_bets(50)
    
    inserted_count = 0
    for bet_data in sample_bets:
        try:
            bet = Bet(
                id=None,
                bet_id=bet_data['bet_id'],
                date=bet_data['date'],
                sport=bet_data['sport'],
                event=bet_data['event'],
                event_id=bet_data['event_id'],
                market_type=bet_data['market_type'],
                bet_type=bet_data['bet_type'],
                selection=bet_data['selection'],
                odds=int(bet_data['odds']),
                true_probability=float(bet_data['true_probability']),
                ev_pct=float(bet_data['ev_pct']),
                edge_score=float(bet_data['edge_score']),
                stake=float(bet_data['stake']),
                stake_pct=float(bet_data['stake_pct']),
                result=bet_data['result'],
                profit=float(bet_data['profit']),
                settled_date=bet_data['settled_date'],
                notes=bet_data['notes']
            )
            db.insert_bet(bet)
            inserted_count += 1
        except Exception as e:
            print(f"  Error inserting bet {bet_data['bet_id']}: {e}")
    
    print(f"Inserted {inserted_count} sample bets")
    
    # Generate bankroll history
    bankroll_history = generate_sample_bankroll_history(30)
    for day in bankroll_history:
        try:
            db.update_bankroll(
                day['date'],
                day['starting_bankroll'],
                day['ending_bankroll'],
                day['peak_bankroll'],
                day['bets_count']
            )
        except Exception as e:
            print(f"  Error updating bankroll for {day['date']}: {e}")
    
    print(f"Inserted {len(bankroll_history)} days of bankroll history")
    
    # Show summary
    try:
        summary = db.get_performance_summary()
        print(f"\nSample Data Summary:")
        print(f"  Total Bets: {summary['total_bets']}")
        print(f"  Settled Bets: {summary['settled_bets']}")
        print(f"  ROI: {summary['roi_pct']}%")
        print(f"  Win Rate: {summary['hit_rate_pct']}%")
        print(f"  Profit: ${summary['profit']}")
    except Exception as e:
        print(f"  Error getting summary: {e}")


if __name__ == "__main__":
    seed_sample_data()
