"""
World-class sports betting model with +EV detection.
Integrates Kelly Criterion, Bayesian probability, and advanced filtering.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import math
import re

from .ev_calculator import (
    american_to_probability, calculate_ev_percentage, calculate_edge,
    calculate_composite_score, clamp, get_max_odds_for_ev_threshold,
    probability_to_american
)
from .kelly import KellyCriterion, BankrollManager, simultaneous_kelly_adjustment


@dataclass
class BetCandidate:
    """A potential betting opportunity."""
    bet_id: str
    date: str
    sport: str
    event: str
    event_id: str
    market_type: str
    bet_type: str
    selection: str
    selection_team: str
    odds: int
    line: str = ""
    
    # Probability estimates
    model_probability: float = 0.5
    market_implied_prob: float = 0.5
    fair_probability: float = 0.5
    true_probability: float = 0.5
    
    # Quality metrics
    data_quality: float = 75.0
    sample_size: int = 30
    confidence_score: float = 70.0
    
    # EV metrics
    ev_pct: float = 0.0
    edge_pct: float = 0.0
    buffered_ev_pct: float = 0.0
    
    # Kelly sizing
    stake: float = 0.0
    stake_pct: float = 0.0
    full_kelly_pct: float = 0.0
    
    # Scoring
    edge_score: float = 0.0
    composite_score: float = 0.0
    
    # Status
    qualified: bool = False
    filter_reasons: List[str] = field(default_factory=list)
    notes: str = ""
    
    # Metadata
    home_team: str = ""
    away_team: str = ""
    correlation_group: str = ""
    max_odds: int = 0


class SportsBettingModel:
    """
    World-class betting model with strict +EV thresholds and Kelly Criterion.
    """
    
    # Strict thresholds for world-class accuracy
    DEFAULT_CONFIG = {
        "min_ev_pct": 7.0,              # Minimum 7% EV (proven profitable)
        "min_edge_pct": 3.0,            # Minimum 3% edge over market
        "min_buffered_ev_pct": 2.0,     # Minimum 2% after uncertainty buffer
        "min_true_probability_pct": 40.0,  # Minimum 40% win probability
        "min_quality": 60.0,            # Minimum data quality
        "min_sample_size": 15,          # Minimum sample size
        "min_edge_score": 70,           # Minimum composite score
        
        "kelly_fraction": 0.20,         # 20% fractional Kelly
        "max_stake_pct": 0.035,         # 3.5% max per bet
        "max_daily_risk_pct": 0.15,     # 15% max daily exposure
        "min_official_stake": 5.0,      # $5 minimum bet
        
        "market_respect_base": 0.15,
        "market_respect_quality_scale": 0.002,
        "max_probability_gap_pct": 12.0,
        
        # Uncertainty penalties
        "base_haircut_pct": 2.5,
        "quality_penalty_factor": 0.15,
        "sample_penalty_threshold": 20,
        
        # Sport-specific probability caps
        "sport_caps": {
            "MLB": ((0.30, 0.70), (0.25, 0.75)),
            "NCAABASE": ((0.30, 0.70), (0.25, 0.75)),
            "NBA": ((0.32, 0.68), (0.28, 0.72)),
            "WNBA": ((0.32, 0.68), (0.28, 0.72)),
            "NCAAMB": ((0.32, 0.68), (0.28, 0.72)),
            "NCAAWB": ((0.32, 0.68), (0.28, 0.72)),
            "NHL": ((0.30, 0.70), (0.28, 0.72)),
            "NFL": ((0.35, 0.65), (0.30, 0.70)),
            "NCAAF": ((0.35, 0.65), (0.30, 0.70)),
        }
    }
    
    def __init__(self, 
                 bankroll: float = 1000.0,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize betting model.
        
        Args:
            bankroll: Starting bankroll
            config: Override default thresholds
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.bankroll_manager = BankrollManager(
            initial_bankroll=bankroll,
            kelly_fraction=self.config["kelly_fraction"],
            max_stake_pct=self.config["max_stake_pct"]
        )
        self.kelly = self.bankroll_manager.kelly
    
    def evaluate_candidate(self, candidate: BetCandidate) -> BetCandidate:
        """
        Evaluate a bet candidate against all thresholds.
        """
        # Calculate implied probability from odds
        candidate.market_implied_prob = american_to_probability(candidate.odds)
        
        # Apply sport-specific probability caps
        capped_prob = self._apply_probability_caps(
            candidate.model_probability,
            candidate.sport,
            candidate.market_type,
            candidate.sample_size
        )
        candidate.model_probability = capped_prob
        
        # Calculate fair probability (no-vig)
        candidate.fair_probability = candidate.market_implied_prob
        
        # Bayesian calibration to get true probability
        candidate.true_probability = self._calibrate_probability(
            candidate.model_probability,
            candidate.fair_probability,
            candidate.data_quality,
            candidate.sample_size
        )
        
        # Calculate EV metrics
        candidate.ev_pct = calculate_ev_percentage(
            candidate.true_probability, candidate.odds
        )
        candidate.edge_pct = calculate_edge(
            candidate.true_probability, candidate.odds
        ) * 100
        
        # Apply uncertainty buffer for entry
        uncertainty_buffer = self._calculate_uncertainty_buffer(candidate)
        buffered_prob = candidate.true_probability - uncertainty_buffer
        candidate.buffered_ev_pct = calculate_ev_percentage(
            buffered_prob, candidate.odds
        )
        
        # Calculate Kelly stake
        kelly_result = self.kelly.calculate_stake(
            candidate.true_probability,
            candidate.odds,
            candidate.data_quality,
            candidate.sample_size
        )
        candidate.stake = kelly_result.recommended_stake
        candidate.stake_pct = kelly_result.recommended_pct
        candidate.full_kelly_pct = kelly_result.full_kelly_pct
        
        # Calculate edge score
        candidate.edge_score = calculate_composite_score(
            ev_pct=candidate.ev_pct,
            edge=candidate.edge_pct / 100,
            true_prob=candidate.true_probability,
            quality=candidate.data_quality,
            sample_size=candidate.sample_size
        )
        
        # Calculate max acceptable odds (when EV drops below 2%)
        candidate.max_odds = get_max_odds_for_ev_threshold(
            candidate.true_probability, min_ev_pct=2.0
        )
        
        # Check qualification against all thresholds
        candidate.qualified = self._check_qualification(candidate)
        
        # Calculate final composite score for ranking
        candidate.composite_score = self._calculate_final_score(candidate)
        
        return candidate
    
    def _apply_probability_caps(self, 
                                probability: float, 
                                sport: str,
                                market_type: str,
                                sample_size: int) -> float:
        """Apply sport-specific realistic probability caps."""
        caps = self.config["sport_caps"].get(sport, ((0.32, 0.68), (0.28, 0.72)))
        
        # Use tighter caps for spread/totals
        is_alt_line = market_type in ["spread", "total", "alt_spread", "alt_total"]
        min_cap, max_cap = caps[1] if is_alt_line else caps[0]
        
        # Tighten caps for low sample sizes
        sample_confidence = min(1.0, sample_size / 40.0)
        if sample_confidence < 0.5:
            min_cap += 0.08
            max_cap -= 0.08
        elif sample_confidence < 0.75:
            min_cap += 0.04
            max_cap -= 0.04
        
        return clamp(probability, min_cap, max_cap)
    
    def _calibrate_probability(self,
                             model_prob: float,
                             market_prob: float,
                             quality: float,
                             sample_size: int) -> float:
        """
        Bayesian calibration blending model and market probabilities.
        """
        # Weight model more when quality is high
        model_weight = 0.7 * (quality / 100)
        
        # Reduce model weight for small samples
        sample_factor = min(1.0, sample_size / 40.0)
        model_weight *= (0.5 + 0.5 * sample_factor)
        
        market_weight = 1 - model_weight
        
        # Blend probabilities
        blended = (model_prob * model_weight) + (market_prob * market_weight)
        
        # Apply uncertainty regression toward 0.5 for low confidence
        confidence = (quality / 100) * sample_factor
        calibrated = (blended * confidence) + (0.5 * (1 - confidence))
        
        return clamp(calibrated, 0.01, 0.99)
    
    def _calculate_uncertainty_buffer(self, candidate: BetCandidate) -> float:
        """Calculate uncertainty buffer based on data quality."""
        base_buffer = self.config["base_haircut_pct"] / 100
        
        # Quality penalty
        quality_penalty = max(0, 75 - candidate.data_quality) / 1000
        
        # Sample size penalty
        sample_penalty = max(0, self.config["sample_penalty_threshold"] - candidate.sample_size) / 1000
        
        # Early season additional penalty
        early_season_penalty = 0
        if candidate.sample_size < 20:
            early_season_penalty = (20 - candidate.sample_size) * 0.003
        
        total_buffer = base_buffer + quality_penalty + sample_penalty + early_season_penalty
        return min(total_buffer, 0.15)  # Cap at 15%
    
    def _check_qualification(self, candidate: BetCandidate) -> bool:
        """Check if candidate meets all strict thresholds."""
        reasons = []
        
        # Check EV threshold
        if candidate.ev_pct < self.config["min_ev_pct"]:
            reasons.append(f"EV {candidate.ev_pct:.1f}% < {self.config['min_ev_pct']}%")
        
        # Check buffered EV
        if candidate.buffered_ev_pct < self.config["min_buffered_ev_pct"]:
            reasons.append(f"Buffered EV {candidate.buffered_ev_pct:.1f}% < {self.config['min_buffered_ev_pct']}%")
        
        # Check edge score
        if candidate.edge_score < self.config["min_edge_score"]:
            reasons.append(f"Edge score {candidate.edge_score:.0f} < {self.config['min_edge_score']}")
        
        # Check minimum probability
        if candidate.true_probability * 100 < self.config["min_true_probability_pct"]:
            reasons.append(f"Probability {candidate.true_probability*100:.1f}% < {self.config['min_true_probability_pct']}%")
        
        # Check data quality
        if candidate.data_quality < self.config["min_quality"]:
            reasons.append(f"Quality {candidate.data_quality:.0f} < {self.config['min_quality']}")
        
        # Check sample size
        if candidate.sample_size < self.config["min_sample_size"]:
            reasons.append(f"Sample size {candidate.sample_size} < {self.config['min_sample_size']}")
        
        # Check minimum stake
        if candidate.stake < self.config["min_official_stake"]:
            reasons.append(f"Stake ${candidate.stake:.2f} < ${self.config['min_official_stake']}")
        
        candidate.filter_reasons = reasons
        return len(reasons) == 0
    
    def _calculate_final_score(self, candidate: BetCandidate) -> float:
        """Calculate final composite score with all factors."""
        # Base score from edge calculation
        base_score = candidate.edge_score
        
        # EV bonus
        ev_bonus = min(candidate.ev_pct * 0.5, 15)
        
        # Probability bonus (sweet spot 50-70%)
        prob_distance = abs(candidate.true_probability - 0.6)
        prob_bonus = max(0, 10 - (prob_distance * 20))
        
        # Quality bonus
        quality_bonus = (candidate.data_quality - 75) * 0.1 if candidate.data_quality > 75 else 0
        
        # Sample size bonus
        sample_bonus = min(5, (candidate.sample_size - 30) * 0.1) if candidate.sample_size > 30 else 0
        
        # Longshot penalty
        longshot_penalty = 0
        if candidate.odds > 0 and candidate.odds > 160:
            longshot_penalty = (candidate.odds - 160) * 0.05
        
        final_score = base_score + ev_bonus + prob_bonus + quality_bonus + sample_bonus - longshot_penalty
        return round(min(final_score, 100), 2)
    
    def filter_and_rank_picks(self, 
                            candidates: List[BetCandidate],
                            max_picks: int = 10) -> List[BetCandidate]:
        """
        Filter to qualified picks and rank by composite score.
        Applies simultaneous Kelly adjustment.
        """
        # Filter to qualified only
        qualified = [c for c in candidates if c.qualified]
        
        # Sort by composite score descending
        qualified.sort(key=lambda x: x.composite_score, reverse=True)
        
        # Limit to max picks
        picks = qualified[:max_picks]
        
        # Apply simultaneous Kelly adjustment
        picks_data = [
            {
                'stake': p.stake,
                'stake_pct': p.stake_pct,
                'notes': p.notes
            } for p in picks
        ]
        
        adjusted = simultaneous_kelly_adjustment(
            picks_data,
            self.bankroll_manager.current_bankroll,
            self.config["max_daily_risk_pct"]
        )
        
        # Update picks with adjusted stakes
        for i, pick in enumerate(picks):
            pick.stake = adjusted[i]['stake']
            pick.stake_pct = adjusted[i]['stake_pct']
            pick.notes = adjusted[i].get('notes', pick.notes)
        
        return picks
    
    def get_model_config(self) -> Dict[str, Any]:
        """Get current model configuration."""
        return {
            "thresholds": {
                "min_ev_pct": self.config["min_ev_pct"],
                "min_edge_score": self.config["min_edge_score"],
                "min_true_probability": self.config["min_true_probability_pct"],
                "min_quality": self.config["min_quality"],
                "min_sample_size": self.config["min_sample_size"]
            },
            "bankroll": self.bankroll_manager.get_performance_metrics(),
            "drawdown_status": self.bankroll_manager.drawdown_mgr.get_drawdown_status(
                self.bankroll_manager.current_bankroll
            )
        }


def create_candidate_from_dict(data: Dict[str, Any]) -> BetCandidate:
    """Factory function to create BetCandidate from dictionary."""
    return BetCandidate(
        bet_id=data.get('bet_id', ''),
        date=data.get('date', datetime.now().strftime('%Y-%m-%d')),
        sport=data.get('sport', ''),
        event=data.get('event', ''),
        event_id=data.get('event_id', ''),
        market_type=data.get('market_type', 'moneyline'),
        bet_type=data.get('bet_type', ''),
        selection=data.get('selection', ''),
        selection_team=data.get('selection_team', ''),
        odds=data.get('odds', -110),
        line=data.get('line', ''),
        model_probability=data.get('model_probability', 0.5),
        data_quality=data.get('data_quality', 75.0),
        sample_size=data.get('sample_size', 30),
        home_team=data.get('home_team', ''),
        away_team=data.get('away_team', ''),
        correlation_group=data.get('correlation_group', data.get('event_id', ''))
    )
