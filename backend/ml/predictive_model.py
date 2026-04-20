"""
Predictive Betting Model
Uses team statistics to predict game outcomes and find value bets
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from data.team_stats import TeamStats, team_stats_manager

@dataclass
class GamePrediction:
    """Predicted outcome for a game."""
    home_team: str
    away_team: str
    sport: str
    
    # Moneyline predictions
    home_win_probability: float
    away_win_probability: float
    
    # Spread predictions
    predicted_spread: float  # Positive = home favored
    home_spread_prob: float  # Prob home covers
    away_spread_prob: float  # Prob away covers
    
    # Total predictions
    predicted_total: float
    over_prob: float
    under_prob: float
    
    # Confidence
    confidence: float  # 0-100 based on data quality
    sample_size: int


class PredictiveBettingModel:
    """
    Statistical model for predicting game outcomes.
    Uses team stats, recent form, and historical trends.
    """
    
    def __init__(self):
        self.home_field_advantage = {
            'MLB': 0.04,  # 4% home field
            'NBA': 0.06,  # 6% home court
            'NFL': 0.07,  # 7% home field
            'NHL': 0.05,  # 5% home ice
            'NCAAMB': 0.08,  # 8% home court (college)
            'NCAAF': 0.09,  # 9% home field (college)
        }
    
    def predict_game(self, home_team_id: str, away_team_id: str, 
                     sport: str, season: Optional[str] = None) -> Optional[GamePrediction]:
        """
        Predict outcome of a game between two teams.
        """
        if season is None:
            from datetime import datetime
            season = str(datetime.now().year)
        
        # Get team stats
        home_stats = team_stats_manager.get_team_stats(home_team_id, season)
        away_stats = team_stats_manager.get_team_stats(away_team_id, season)
        
        if not home_stats or not away_stats:
            return None
        
        # Calculate base win probabilities using Elo-style rating
        home_rating = self._calculate_team_rating(home_stats)
        away_rating = self._calculate_team_rating(away_stats)
        
        # Apply home field advantage
        hfa = self.home_field_advantage.get(sport, 0.05)
        home_rating *= (1 + hfa)
        
        # Convert ratings to probability
        home_prob = home_rating / (home_rating + away_rating)
        away_prob = 1 - home_prob
        
        # Predict score differential (for spreads)
        home_ppg = home_stats.points_scored
        away_ppg = away_stats.points_scored
        home_def = home_stats.points_allowed
        away_def = away_stats.points_allowed
        
        # Expected scores
        home_expected = (home_ppg + away_def) / 2
        away_expected = (away_ppg + home_def) / 2
        
        predicted_spread = home_expected - away_expected
        predicted_total = home_expected + away_expected
        
        # Spread probabilities (simplified model)
        # Assume std dev of 11 for NBA, 10 for NFL, 4 for MLB
        std_dev = {'NBA': 11, 'NFL': 10, 'MLB': 4, 'NHL': 3, 'NCAAMB': 12, 'NCAAF': 14}.get(sport, 10)
        
        # P(home covers spread) = P(home - away > spread)
        # = P(home - away - spread > 0)
        # = 1 - CDF(0, predicted_spread - market_spread, std_dev)
        # Simplified: use predicted spread vs market spread
        
        home_spread_prob = 0.5  # Placeholder - would need market spread
        away_spread_prob = 0.5
        
        # Total probabilities
        # P(over) = P(total > market_total)
        over_prob = 0.5
        under_prob = 0.5
        
        # Confidence based on sample size and recent form
        sample_size = min(home_stats.wins + home_stats.losses, away_stats.wins + away_stats.losses)
        confidence = min(100, 30 + sample_size * 2)  # Base 30 + 2 per game played
        
        # Boost confidence if teams have recent games
        if home_stats.last_10_wins + home_stats.last_10_losses >= 5:
            confidence += 10
        if away_stats.last_10_wins + away_stats.last_10_losses >= 5:
            confidence += 10
        
        confidence = min(100, confidence)
        
        return GamePrediction(
            home_team=home_stats.team_name,
            away_team=away_stats.team_name,
            sport=sport,
            home_win_probability=round(home_prob, 3),
            away_win_probability=round(away_prob, 3),
            predicted_spread=round(predicted_spread, 1),
            home_spread_prob=round(home_spread_prob, 3),
            away_spread_prob=round(away_spread_prob, 3),
            predicted_total=round(predicted_total, 1),
            over_prob=round(over_prob, 3),
            under_prob=round(under_prob, 3),
            confidence=round(confidence, 1),
            sample_size=sample_size
        )
    
    def _calculate_team_rating(self, stats: TeamStats) -> float:
        """
        Calculate team strength rating based on stats.
        Elo-inspired formula using win rate and point differential.
        """
        games = stats.wins + stats.losses
        if games == 0:
            return 1500  # Default rating
        
        # Win rate component (0-1 scale, centered at 0.5)
        win_rate = stats.wins / games
        
        # Point differential component
        # Normalize by sport-typical scoring
        avg_points_for = {'MLB': 4.5, 'NBA': 115, 'NFL': 23, 'NHL': 3.2, 'NCAAMB': 75, 'NCAAF': 28}.get(stats.sport, 100)
        point_diff_norm = (stats.points_scored - stats.points_allowed) / avg_points_for
        
        # Recent form weighting
        recent_games = stats.last_10_wins + stats.last_10_losses
        recent_win_rate = stats.last_10_wins / recent_games if recent_games > 0 else win_rate
        
        # Combine components
        # 40% season win rate, 30% point diff, 30% recent form
        rating = 1500 + (200 * (
            0.4 * (win_rate - 0.5) * 2 +
            0.3 * point_diff_norm +
            0.3 * (recent_win_rate - 0.5) * 2
        ))
        
        return max(1000, min(2000, rating))  # Keep within reasonable bounds
    
    def find_value_bets(self, games: List[Dict], min_ev: float = 0.05) -> List[Dict]:
        """
        Find value bets by comparing predictions to market odds.
        """
        value_bets = []
        
        for game in games:
            home_team_id = game.get('home_team_id')
            away_team_id = game.get('away_team_id')
            sport = game.get('sport')
            
            prediction = self.predict_game(home_team_id, away_team_id, sport)
            
            if not prediction:
                continue
            
            # Check moneyline value
            if 'home_ml_odds' in game and 'away_ml_odds' in game:
                home_ml = game['home_ml_odds']
                away_ml = game['away_ml_odds']
                
                # Calculate implied probabilities
                home_implied = self._american_to_prob(home_ml)
                away_implied = self._american_to_prob(away_ml)
                
                # Remove vig to get fair probabilities
                total_implied = home_implied + away_implied
                home_fair = home_implied / total_implied
                away_fair = away_implied / total_implied
                
                # Compare to our prediction
                home_edge = prediction.home_win_probability - home_fair
                away_edge = prediction.away_win_probability - away_fair
                
                # EV calculation
                if home_edge > 0:
                    home_ev = (prediction.home_win_probability * self._american_to_decimal(home_ml) - 1)
                    if home_ev >= min_ev:
                        value_bets.append({
                            'bet_type': 'moneyline',
                            'selection': prediction.home_team,
                            'odds': home_ml,
                            'predicted_prob': prediction.home_win_probability,
                            'implied_prob': home_fair,
                            'edge': home_edge,
                            'ev': home_ev,
                            'confidence': prediction.confidence
                        })
                
                if away_edge > 0:
                    away_ev = (prediction.away_win_probability * self._american_to_decimal(away_ml) - 1)
                    if away_ev >= min_ev:
                        value_bets.append({
                            'bet_type': 'moneyline',
                            'selection': prediction.away_team,
                            'odds': away_ml,
                            'predicted_prob': prediction.away_win_probability,
                            'implied_prob': away_fair,
                            'edge': away_edge,
                            'ev': away_ev,
                            'confidence': prediction.confidence
                        })
            
            # Check spread value (if market spread provided)
            if 'home_spread' in game and 'home_spread_odds' in game:
                spread = game['home_spread']
                spread_odds = game['home_spread_odds']
                
                # Simplified: assume 50/50 on spreads, look for -110 or better
                if spread_odds <= -105:
                    # Check if our predicted spread differs from market
                    market_spread = -spread if spread < 0 else spread
                    our_spread = prediction.predicted_spread
                    
                    spread_diff = abs(our_spread - market_spread)
                    
                    if spread_diff >= 2:  # Our model differs by 2+ points
                        value_bets.append({
                            'bet_type': 'spread',
                            'selection': f"{prediction.home_team} {spread}",
                            'odds': spread_odds,
                            'predicted_spread': prediction.predicted_spread,
                            'market_spread': market_spread,
                            'edge': spread_diff / 10,  # Simplified edge calc
                            'ev': 0.02,  # Conservative estimate
                            'confidence': prediction.confidence
                        })
        
        # Sort by EV
        value_bets.sort(key=lambda x: x['ev'], reverse=True)
        
        return value_bets
    
    def _american_to_prob(self, odds: int) -> float:
        """Convert American odds to implied probability."""
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    
    def _american_to_decimal(self, odds: int) -> float:
        """Convert American odds to decimal."""
        if odds > 0:
            return (odds / 100) + 1
        else:
            return (100 / abs(odds)) + 1


# Global instance
predictive_model = PredictiveBettingModel()
