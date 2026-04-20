"""
Auto Trader
Automatically creates paper bets from model picks and tracks performance
"""

from datetime import datetime, date
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from .models import PaperBet, PaperBankroll, AutoTradingSettings, Session

@dataclass
class PaperTradingSettings:
    enabled: bool = False
    starting_bankroll: float = 10000.0
    kelly_fraction: float = 0.2
    min_ev: float = 7.0
    max_daily_bets: int = 10


class AutoTrader:
    """
    Automatic paper trading system.
    Creates virtual bets, tracks results, maintains performance history.
    """
    
    def __init__(self):
        self.session = Session()
        self._ensure_settings_exist()
    
    def _ensure_settings_exist(self):
        """Ensure default settings exist in database"""
        settings = self.session.query(AutoTradingSettings).first()
        if not settings:
            settings = AutoTradingSettings()
            self.session.add(settings)
            self.session.commit()
            print("✅ Created default paper trading settings")
    
    def get_settings(self) -> PaperTradingSettings:
        """Get current paper trading settings"""
        settings = self.session.query(AutoTradingSettings).first()
        if not settings:
            return PaperTradingSettings()
        
        return PaperTradingSettings(
            enabled=settings.enabled,
            starting_bankroll=settings.starting_bankroll,
            kelly_fraction=settings.kelly_fraction,
            min_ev=settings.min_ev,
            max_daily_bets=settings.max_daily_bets
        )
    
    def update_settings(self, **kwargs) -> bool:
        """Update paper trading settings"""
        try:
            settings = self.session.query(AutoTradingSettings).first()
            if not settings:
                settings = AutoTradingSettings()
                self.session.add(settings)
            
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            settings.updated_at = datetime.utcnow()
            self.session.commit()
            return True
        except Exception as e:
            print(f"Error updating settings: {e}")
            self.session.rollback()
            return False
    
    def enable_auto_trading(self) -> bool:
        """Enable automatic paper trading"""
        return self.update_settings(enabled=True)
    
    def disable_auto_trading(self) -> bool:
        """Disable automatic paper trading"""
        return self.update_settings(enabled=False)
    
    def reset_paper_trading(self, new_bankroll: float = 10000.0) -> bool:
        """Reset paper trading - clear all bets and reset bankroll"""
        try:
            # Clear all bets
            self.session.query(PaperBet).delete()
            self.session.query(PaperBankroll).delete()
            
            # Reset settings
            settings = self.session.query(AutoTradingSettings).first()
            if settings:
                settings.starting_bankroll = new_bankroll
                settings.current_bankroll = new_bankroll
                settings.enabled = True
                settings.updated_at = datetime.utcnow()
            
            self.session.commit()
            print(f"✅ Paper trading reset with ${new_bankroll:,.2f} bankroll")
            return True
        except Exception as e:
            print(f"Error resetting paper trading: {e}")
            self.session.rollback()
            return False
    
    def get_current_bankroll(self) -> float:
        """Get current paper trading bankroll"""
        settings = self.session.query(AutoTradingSettings).first()
        if settings:
            return settings.current_bankroll
        return 10000.0
    
    def create_paper_bet(self, pick_data: Dict[str, Any]) -> Optional[PaperBet]:
        """
        Create a paper bet from a pick.
        Called automatically when picks are generated.
        """
        settings = self.get_settings()
        
        if not settings.enabled:
            return None
        
        # Check if bet already exists
        bet_id = pick_data.get('bet_id')
        existing = self.session.query(PaperBet).filter_by(bet_id=bet_id).first()
        if existing:
            return None  # Already tracked
        
        # Check daily bet limit
        today = date.today().strftime('%Y-%m-%d')
        daily_count = self.session.query(PaperBet).filter(PaperBet.date == today).count()
        if daily_count >= settings.max_daily_bets:
            print(f"⚠️ Daily bet limit reached ({settings.max_daily_bets})")
            return None
        
        # Check minimum EV
        ev_pct = pick_data.get('ev_pct', 0)
        if ev_pct < settings.min_ev:
            return None
        
        # Calculate stake using Kelly Criterion
        odds = pick_data.get('odds', -110)
        true_prob = pick_data.get('true_probability', 50) / 100
        
        # Kelly stake calculation
        if odds > 0:
            decimal_odds = (odds / 100) + 1
        else:
            decimal_odds = (100 / abs(odds)) + 1
        
        edge = true_prob - (1 / decimal_odds)
        if edge <= 0:
            return None  # Negative edge, don't bet
        
        kelly_fraction = (edge) / (decimal_odds - 1)
        kelly_stake = kelly_fraction * settings.starting_bankroll
        
        # Apply fractional Kelly (20%)
        stake = kelly_stake * settings.kelly_fraction
        
        # Cap at 3.5% of bankroll
        max_stake = settings.starting_bankroll * 0.035
        stake = min(stake, max_stake)
        
        # Minimum $10 bet
        stake = max(stake, 10.0)
        
        # Create paper bet
        paper_bet = PaperBet(
            bet_id=bet_id,
            date=today,
            sport=pick_data.get('sport', 'Unknown'),
            event=pick_data.get('event', 'Unknown'),
            selection=pick_data.get('selection', 'Unknown'),
            bet_type=pick_data.get('bet_type', 'moneyline'),
            odds=odds,
            stake=round(stake, 2),
            model_probability=true_prob,
            ev_pct=ev_pct,
            result='pending',
            profit=0.0
        )
        
        self.session.add(paper_bet)
        self.session.commit()
        
        print(f"📝 Paper bet created: {paper_bet.selection} ${stake:.2f} @ {odds}")
        return paper_bet
    
    def settle_bet(self, bet_id: str, result: str, actual_odds: Optional[int] = None) -> bool:
        """
        Settle a paper bet with result.
        result: 'win', 'loss', 'push'
        """
        try:
            bet = self.session.query(PaperBet).filter_by(bet_id=bet_id).first()
            if not bet:
                print(f"❌ Bet not found: {bet_id}")
                return False
            
            if bet.result != 'pending':
                print(f"⚠️ Bet already settled: {bet_id}")
                return False
            
            bet.result = result
            bet.settled_at = datetime.utcnow()
            
            # Calculate profit
            if result == 'win':
                if bet.odds > 0:
                    profit = bet.stake * (bet.odds / 100)
                else:
                    profit = bet.stake * (100 / abs(bet.odds))
            elif result == 'push':
                profit = 0
            else:  # loss
                profit = -bet.stake
            
            bet.profit = round(profit, 2)
            
            # Update bankroll
            settings = self.session.query(AutoTradingSettings).first()
            if settings:
                settings.current_bankroll += profit
            
            self.session.commit()
            
            if result == 'win':
                print(f"✅ Paper bet WON: {bet.selection} +${profit:.2f}")
            elif result == 'loss':
                print(f"❌ Paper bet LOST: {bet.selection} -${bet.stake:.2f}")
            else:
                print(f"🔄 Paper bet PUSH: {bet.selection} $0.00")
            
            return True
        except Exception as e:
            print(f"Error settling bet: {e}")
            self.session.rollback()
            return False
    
    def get_all_bets(self, limit: int = 100) -> List[PaperBet]:
        """Get all paper bets ordered by date desc"""
        return self.session.query(PaperBet).order_by(PaperBet.created_at.desc()).limit(limit).all()
    
    def get_pending_bets(self) -> List[PaperBet]:
        """Get all pending paper bets"""
        return self.session.query(PaperBet).filter_by(result='pending').all()
    
    def get_settled_bets(self, days: int = 30) -> List[PaperBet]:
        """Get settled bets from last N days"""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        return self.session.query(PaperBet).filter(
            PaperBet.result != 'pending',
            PaperBet.settled_at >= cutoff
        ).order_by(PaperBet.settled_at.desc()).all()
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        bets = self.session.query(PaperBet).all()
        
        if not bets:
            return {
                'total_bets': 0,
                'wins': 0,
                'losses': 0,
                'pushes': 0,
                'win_rate': 0.0,
                'total_staked': 0.0,
                'total_profit': 0.0,
                'roi': 0.0,
                'current_bankroll': self.get_current_bankroll(),
                'starting_bankroll': 10000.0
            }
        
        wins = sum(1 for b in bets if b.result == 'win')
        losses = sum(1 for b in bets if b.result == 'loss')
        pushes = sum(1 for b in bets if b.result == 'push')
        pending = sum(1 for b in bets if b.result == 'pending')
        
        total_staked = sum(b.stake for b in bets if b.result != 'pending')
        total_profit = sum(b.profit for b in bets if b.result != 'pending')
        
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        
        settings = self.session.query(AutoTradingSettings).first()
        starting = settings.starting_bankroll if settings else 10000.0
        current = settings.current_bankroll if settings else starting
        
        return {
            'total_bets': len(bets),
            'pending_bets': pending,
            'wins': wins,
            'losses': losses,
            'pushes': pushes,
            'win_rate': round(win_rate * 100, 1),
            'total_staked': round(total_staked, 2),
            'total_profit': round(total_profit, 2),
            'roi': round(roi, 2),
            'current_bankroll': round(current, 2),
            'starting_bankroll': round(starting, 2),
            'bankroll_change_pct': round((current - starting) / starting * 100, 2)
        }
    
    def get_daily_performance(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily performance for last N days"""
        from sqlalchemy import func
        from datetime import timedelta
        
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        daily_stats = self.session.query(
            PaperBet.date,
            func.count(PaperBet.id).label('bets'),
            func.sum(PaperBet.profit).label('profit')
        ).filter(
            PaperBet.result != 'pending',
            PaperBet.date >= cutoff
        ).group_by(PaperBet.date).order_by(PaperBet.date.desc()).all()
        
        return [
            {
                'date': stat.date,
                'bets': stat.bets,
                'profit': round(stat.profit or 0, 2)
            }
            for stat in daily_stats
        ]


# Global instance
auto_trader = AutoTrader()
