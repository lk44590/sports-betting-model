"""Kelly Criterion stake sizing with advanced risk management."""

from typing import Tuple, List, Dict, Any
from dataclasses import dataclass
import math

from .ev_calculator import american_to_profit_multiple, calculate_ev


@dataclass
class KellyResult:
    """Result of Kelly calculation."""
    full_kelly_pct: float
    fractional_kelly_pct: float
    recommended_stake: float
    recommended_pct: float
    confidence_score: float
    max_stake_reached: bool
    notes: str


class KellyCriterion:
    """
    Kelly Criterion implementation with fractional Kelly and risk management.
    """
    
    def __init__(self, 
                 bankroll: float = 1000.0,
                 kelly_fraction: float = 0.20,
                 max_stake_pct: float = 0.035,
                 max_daily_risk_pct: float = 0.15,
                 min_stake: float = 5.0):
        """
        Args:
            bankroll: Current bankroll
            kelly_fraction: Fraction of full Kelly to use (0.25 = quarter Kelly)
            max_stake_pct: Maximum stake as % of bankroll per bet
            max_daily_risk_pct: Maximum total daily exposure
            min_stake: Minimum dollar stake
        """
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.max_stake_pct = max_stake_pct
        self.max_daily_risk_pct = max_daily_risk_pct
        self.min_stake = min_stake
        
        # Track daily exposure
        self.daily_stake_total = 0.0
    
    def calculate_stake(self,
                       true_probability: float,
                       odds: int,
                       quality: float = 75.0,
                       sample_size: int = 30,
                       edge_score: float = 70.0) -> KellyResult:
        """
        Calculate optimal stake using Kelly Criterion.
        
        Args:
            true_probability: Model win probability (0-1)
            odds: American odds
            quality: Data quality score (0-100)
            sample_size: Sample size for confidence
            edge_score: Composite edge score
        
        Returns:
            KellyResult with recommended stake
        """
        profit_mult = american_to_profit_multiple(odds)
        
        # Full Kelly formula: (bp - q) / b
        # where b = odds, p = probability, q = 1-p
        p = true_probability
        q = 1 - p
        b = profit_mult
        
        full_kelly = ((b * p) - q) / b if b > 0 else 0
        full_kelly = max(0, full_kelly)  # Kelly can't be negative
        
        # Calculate confidence adjustment based on quality and sample
        sample_confidence = min(1.0, sample_size / 40.0)
        quality_factor = quality / 100.0
        
        # Reduce Kelly when less confident
        confidence_multiplier = 0.4 + (0.6 * sample_confidence * quality_factor)
        
        # Edge score bonus (slight increase for very strong edges)
        edge_bonus = 1.0 + (max(0, edge_score - 80) / 200)  # Up to 10% boost
        
        # Apply fractional Kelly and confidence adjustment
        adjusted_kelly_fraction = self.kelly_fraction * confidence_multiplier * edge_bonus
        fractional_kelly = full_kelly * adjusted_kelly_fraction
        
        # Calculate dollar stake
        stake = self.bankroll * fractional_kelly
        
        # Apply caps
        max_stake = self.bankroll * self.max_stake_pct
        capped_stake = min(stake, max_stake)
        max_reached = capped_stake < stake
        
        # Check daily risk limit
        remaining_daily_risk = (self.bankroll * self.max_daily_risk_pct) - self.daily_stake_total
        if capped_stake > remaining_daily_risk:
            capped_stake = remaining_daily_risk
            max_reached = True
        
        # Minimum stake check
        if capped_stake < self.min_stake:
            notes = f"Stake ${capped_stake:.2f} below minimum ${self.min_stake}"
            return KellyResult(
                full_kelly_pct=full_kelly * 100,
                fractional_kelly_pct=fractional_kelly * 100,
                recommended_stake=0,
                recommended_pct=0,
                confidence_score=confidence_multiplier * 100,
                max_stake_reached=max_reached,
                notes=notes
            )
        
        notes = f"Kelly: {fractional_kelly*100:.2f}% | Conf: {confidence_multiplier*100:.0f}%"
        if max_reached:
            notes += " | Capped by limit"
        
        return KellyResult(
            full_kelly_pct=full_kelly * 100,
            fractional_kelly_pct=fractional_kelly * 100,
            recommended_stake=round(capped_stake, 2),
            recommended_pct=round((capped_stake / self.bankroll) * 100, 2),
            confidence_score=round(confidence_multiplier * 100, 1),
            max_stake_reached=max_reached,
            notes=notes
        )
    
    def update_bankroll(self, new_bankroll: float) -> None:
        """Update bankroll (e.g., after daily settlement)."""
        self.bankroll = new_bankroll
    
    def reset_daily_exposure(self) -> None:
        """Reset daily exposure tracking."""
        self.daily_stake_total = 0.0
    
    def add_exposure(self, stake: float) -> None:
        """Add stake to daily exposure."""
        self.daily_stake_total += stake
    
    def get_remaining_daily_risk(self) -> float:
        """Get remaining daily risk allowance."""
        return (self.bankroll * self.max_daily_risk_pct) - self.daily_stake_total


def simultaneous_kelly_adjustment(picks: List[Dict[str, Any]], 
                                  bankroll: float,
                                  max_daily_risk_pct: float = 0.15) -> List[Dict[str, Any]]:
    """
    Adjust stakes when placing multiple correlated bets simultaneously.
    Uses proportional scaling to stay within risk limits.
    """
    if not picks or len(picks) == 1:
        return picks
    
    total_stake = sum(p.get('stake', 0) for p in picks)
    max_total = bankroll * max_daily_risk_pct
    
    if total_stake <= max_total:
        return picks
    
    # Scale down proportionally
    scale_factor = max_total / total_stake
    
    for pick in picks:
        pick['original_stake'] = pick['stake']
        pick['stake'] = round(pick['stake'] * scale_factor, 2)
        pick['stake_pct'] = round((pick['stake'] / bankroll) * 100, 2)
        pick['notes'] = pick.get('notes', '') + f" | Kelly scaled {scale_factor*100:.0f}%"
    
    return picks


class DrawdownManager:
    """
    Manages betting stakes during drawdowns to protect bankroll.
    """
    
    def __init__(self,
                 peak_bankroll: float = 1000.0,
                 drawdown_trigger_pct: float = 10.0,
                 drawdown_levels: list = None):
        """
        Args:
            peak_bankroll: All-time high bankroll
            drawdown_trigger_pct: When to start reducing stakes
            drawdown_levels: List of (drawdown_pct, multiplier) tuples
        """
        self.peak_bankroll = peak_bankroll
        self.drawdown_trigger_pct = drawdown_trigger_pct
        
        # Default levels: increasing reductions at deeper drawdowns
        self.drawdown_levels = drawdown_levels or [
            (10.0, 0.8),   # -10%: 80% of normal stake
            (15.0, 0.6),   # -15%: 60% of normal stake
            (20.0, 0.4),   # -20%: 40% of normal stake
            (25.0, 0.25),  # -25%: 25% of normal stake (quarter Kelly)
            (30.0, 0.0),   # -30%: Stop betting
        ]
    
    def get_drawdown_multiplier(self, current_bankroll: float) -> float:
        """Get stake multiplier based on current drawdown."""
        drawdown_pct = ((self.peak_bankroll - current_bankroll) / self.peak_bankroll) * 100
        
        if drawdown_pct <= self.drawdown_trigger_pct:
            return 1.0
        
        # Find applicable multiplier
        for level_dd, multiplier in sorted(self.drawdown_levels, reverse=True):
            if drawdown_pct >= level_dd:
                return multiplier
        
        return 1.0
    
    def update_peak(self, current_bankroll: float) -> None:
        """Update peak bankroll if we have a new high."""
        if current_bankroll > self.peak_bankroll:
            self.peak_bankroll = current_bankroll
    
    def get_drawdown_status(self, current_bankroll: float) -> Dict[str, Any]:
        """Get current drawdown status for reporting."""
        drawdown_pct = max(0, ((self.peak_bankroll - current_bankroll) / self.peak_bankroll) * 100)
        multiplier = self.get_drawdown_multiplier(current_bankroll)
        
        status = "normal"
        if drawdown_pct >= self.drawdown_trigger_pct:
            status = "drawdown"
        if multiplier == 0:
            status = "stopped"
        
        return {
            "peak_bankroll": self.peak_bankroll,
            "current_bankroll": current_bankroll,
            "drawdown_pct": round(drawdown_pct, 2),
            "stake_multiplier": multiplier,
            "status": status
        }


class BankrollManager:
    """
    Comprehensive bankroll management with drawdown protection and growth targets.
    """
    
    def __init__(self,
                 initial_bankroll: float = 1000.0,
                 kelly_fraction: float = 0.20,
                 max_stake_pct: float = 0.035,
                 target_monthly_growth: float = 15.0):
        self.initial_bankroll = initial_bankroll
        self.current_bankroll = initial_bankroll
        self.peak_bankroll = initial_bankroll
        self.kelly_fraction = kelly_fraction
        self.max_stake_pct = max_stake_pct
        self.target_monthly_growth = target_monthly_growth
        
        self.kelly = KellyCriterion(
            bankroll=initial_bankroll,
            kelly_fraction=kelly_fraction,
            max_stake_pct=max_stake_pct
        )
        self.drawdown_mgr = DrawdownManager(peak_bankroll=initial_bankroll)
    
    def calculate_position(self, true_prob: float, odds: int, 
                          quality: float, sample_size: int) -> Dict[str, Any]:
        """Calculate complete position sizing recommendation."""
        # Get base Kelly stake
        kelly_result = self.kelly.calculate_stake(
            true_prob, odds, quality, sample_size
        )
        
        # Apply drawdown multiplier
        multiplier = self.drawdown_mgr.get_drawdown_multiplier(self.current_bankroll)
        
        adjusted_stake = kelly_result.recommended_stake * multiplier
        adjusted_pct = kelly_result.recommended_pct * multiplier
        
        drawdown_status = self.drawdown_mgr.get_drawdown_status(self.current_bankroll)
        
        return {
            "stake": round(adjusted_stake, 2),
            "stake_pct": round(adjusted_pct, 2),
            "full_kelly_pct": round(kelly_result.full_kelly_pct, 2),
            "fractional_kelly_pct": round(kelly_result.fractional_kelly_pct, 2),
            "confidence_score": kelly_result.confidence_score,
            "drawdown_multiplier": multiplier,
            "drawdown_status": drawdown_status,
            "notes": kelly_result.notes
        }
    
    def update_after_result(self, profit: float) -> None:
        """Update bankroll after a bet settles."""
        self.current_bankroll += profit
        self.kelly.update_bankroll(self.current_bankroll)
        self.drawdown_mgr.update_peak(self.current_bankroll)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current bankroll performance metrics."""
        total_return = self.current_bankroll - self.initial_bankroll
        roi_pct = (total_return / self.initial_bankroll) * 100
        drawdown_pct = ((self.peak_bankroll - self.current_bankroll) / self.peak_bankroll) * 100
        
        return {
            "initial_bankroll": self.initial_bankroll,
            "current_bankroll": round(self.current_bankroll, 2),
            "peak_bankroll": round(self.peak_bankroll, 2),
            "total_return": round(total_return, 2),
            "roi_pct": round(roi_pct, 2),
            "current_drawdown_pct": round(max(0, drawdown_pct), 2),
            "target_monthly_growth_pct": self.target_monthly_growth
        }
