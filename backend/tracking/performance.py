"""
Performance tracking and analytics for the betting model.
Calculates advanced metrics like CLV, streaks, and model calibration.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from collections import defaultdict


@dataclass
class StreakInfo:
    """Win/loss streak information."""
    current_streak: int
    current_type: str  # 'win', 'loss', 'push'
    longest_win_streak: int
    longest_loss_streak: int
    last_10_results: List[str]


@dataclass
class ModelCalibration:
    """Model calibration metrics."""
    bins: List[Dict[str, Any]]  # Calibration by probability bin
    brier_score: float
    calibration_error: float
    log_loss: float


class PerformanceTracker:
    """
    Track and analyze betting performance with advanced metrics.
    """
    
    def __init__(self):
        self.metrics_cache = {}
    
    def calculate_streaks(self, results: List[Dict[str, Any]]) -> StreakInfo:
        """
        Calculate current and historical streaks.
        
        Args:
            results: List of bet results with 'result' field
        """
        if not results:
            return StreakInfo(0, 'none', 0, 0, [])
        
        # Sort by date
        sorted_results = sorted(results, key=lambda x: x.get('date', ''))
        
        # Extract just win/loss/push
        outcomes = [r.get('result', '').lower() for r in sorted_results]
        
        # Calculate current streak
        current_streak = 0
        current_type = 'none'
        
        for outcome in reversed(outcomes):
            if outcome == 'push':
                continue
            if current_type == 'none':
                current_type = outcome
                current_streak = 1
            elif outcome == current_type:
                current_streak += 1
            else:
                break
        
        # Calculate longest streaks
        longest_win = 0
        longest_loss = 0
        current_win = 0
        current_loss = 0
        
        for outcome in outcomes:
            if outcome == 'win':
                current_win += 1
                current_loss = 0
                longest_win = max(longest_win, current_win)
            elif outcome == 'loss':
                current_loss += 1
                current_win = 0
                longest_loss = max(longest_loss, current_loss)
            # push resets nothing
        
        # Last 10 results
        last_10 = outcomes[-10:] if len(outcomes) >= 10 else outcomes
        
        return StreakInfo(
            current_streak=current_streak,
            current_type=current_type,
            longest_win_streak=longest_win,
            longest_loss_streak=longest_loss,
            last_10_results=last_10
        )
    
    def calculate_clv_metrics(self, bets: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate Closing Line Value (CLV) metrics.
        CLV > 0 means you beat the closing line (good sign).
        """
        clv_values = []
        
        for bet in bets:
            bet_odds = bet.get('odds')
            closing_odds = bet.get('closing_odds')
            
            if bet_odds and closing_odds:
                # Convert to implied probabilities
                def odds_to_prob(odds):
                    if odds > 0:
                        return 100 / (odds + 100)
                    else:
                        return abs(odds) / (abs(odds) + 100)
                
                bet_prob = odds_to_prob(bet_odds)
                close_prob = odds_to_prob(closing_odds)
                
                # CLV = closing implied prob - bet implied prob
                clv = (close_prob - bet_prob) * 100
                clv_values.append(clv)
        
        if not clv_values:
            return {"avg_clv": 0, "positive_clv_rate": 0, "samples": 0}
        
        positive_clv = sum(1 for v in clv_values if v > 0)
        
        return {
            "avg_clv": round(sum(clv_values) / len(clv_values), 2),
            "positive_clv_rate": round(positive_clv / len(clv_values) * 100, 1),
            "samples": len(clv_values),
            "min_clv": round(min(clv_values), 2),
            "max_clv": round(max(clv_values), 2)
        }
    
    def calculate_model_calibration(self, 
                                   predictions: List[Dict[str, Any]]) -> ModelCalibration:
        """
        Calculate how well calibrated the model's probabilities are.
        A well-calibrated model has actual win rate ≈ predicted probability.
        """
        if not predictions:
            return ModelCalibration([], 0.5, 0.5, 1.0)
        
        # Create probability bins
        bins = defaultdict(lambda: {'predicted': [], 'actual': [], 'count': 0})
        
        for pred in predictions:
            prob = pred.get('true_probability', 0.5)
            actual = 1 if pred.get('result') == 'win' else 0
            
            # Bin into 10% ranges
            bin_key = int(prob * 10) / 10
            bins[bin_key]['predicted'].append(prob)
            bins[bin_key]['actual'].append(actual)
            bins[bin_key]['count'] += 1
        
        # Calculate calibration for each bin
        bin_results = []
        total_brier = 0
        total_log_loss = 0
        total_predictions = 0
        
        for bin_key in sorted(bins.keys()):
            bin_data = bins[bin_key]
            if bin_data['count'] < 5:  # Skip small bins
                continue
            
            avg_predicted = sum(bin_data['predicted']) / bin_data['count']
            actual_rate = sum(bin_data['actual']) / bin_data['count']
            
            # Brier score component
            for p, a in zip(bin_data['predicted'], bin_data['actual']):
                total_brier += (p - a) ** 2
                # Log loss (clipped to avoid infinity)
                p_clipped = max(0.001, min(0.999, p))
                total_log_loss += -(a * math.log(p_clipped) + (1-a) * math.log(1-p_clipped))
                total_predictions += 1
            
            bin_results.append({
                "bin_range": f"{bin_key*100:.0f}%-{(bin_key+0.1)*100:.0f}%",
                "predicted_rate": round(avg_predicted * 100, 1),
                "actual_rate": round(actual_rate * 100, 1),
                "calibration_error": round(abs(avg_predicted - actual_rate) * 100, 1),
                "samples": bin_data['count']
            })
        
        # Overall metrics
        brier_score = total_brier / total_predictions if total_predictions > 0 else 0.25
        log_loss = total_log_loss / total_predictions if total_predictions > 0 else 0.693
        
        # Average calibration error
        calibration_error = sum(b['calibration_error'] for b in bin_results) / len(bin_results) if bin_results else 0
        
        return ModelCalibration(
            bins=bin_results,
            brier_score=round(brier_score, 4),
            calibration_error=round(calibration_error, 2),
            log_loss=round(log_loss, 4)
        )
    
    def calculate_roi_by_period(self, 
                               bets: List[Dict[str, Any]], 
                               period: str = 'day') -> List[Dict[str, Any]]:
        """
        Calculate ROI grouped by time period.
        
        Args:
            period: 'day', 'week', or 'month'
        """
        if not bets:
            return []
        
        # Group by period
        period_stats = defaultdict(lambda: {'stake': 0, 'profit': 0, 'bets': 0, 'wins': 0})
        
        for bet in bets:
            date = bet.get('date', '')
            if not date:
                continue
            
            if period == 'day':
                key = date
            elif period == 'week':
                # Get week number
                dt = datetime.strptime(date, '%Y-%m-%d')
                key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
            elif period == 'month':
                key = date[:7]  # YYYY-MM
            else:
                key = date
            
            period_stats[key]['stake'] += bet.get('stake', 0)
            period_stats[key]['profit'] += bet.get('profit', 0) or 0
            period_stats[key]['bets'] += 1
            if bet.get('result') == 'win':
                period_stats[key]['wins'] += 1
        
        # Calculate ROIs
        results = []
        for key in sorted(period_stats.keys()):
            stats = period_stats[key]
            roi = (stats['profit'] / stats['stake'] * 100) if stats['stake'] > 0 else 0
            hit_rate = (stats['wins'] / stats['bets'] * 100) if stats['bets'] > 0 else 0
            
            results.append({
                'period': key,
                'bets': stats['bets'],
                'stake': round(stats['stake'], 2),
                'profit': round(stats['profit'], 2),
                'roi_pct': round(roi, 2),
                'hit_rate_pct': round(hit_rate, 1)
            })
        
        return results
    
    def calculate_variance_metrics(self, bets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate variance and risk metrics.
        """
        if not bets:
            return {}
        
        profits = [b.get('profit', 0) for b in bets if b.get('profit') is not None]
        
        if not profits:
            return {}
        
        n = len(profits)
        mean_profit = sum(profits) / n
        
        # Variance and standard deviation
        variance = sum((p - mean_profit) ** 2 for p in profits) / n
        std_dev = math.sqrt(variance)
        
        # Sharpe-like ratio (mean / std)
        sharpe = mean_profit / std_dev if std_dev > 0 else 0
        
        # Max drawdown calculation
        cumulative = 0
        peak = 0
        max_drawdown = 0
        
        for profit in profits:
            cumulative += profit
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)
        
        return {
            "avg_profit": round(mean_profit, 2),
            "profit_std_dev": round(std_dev, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(max_drawdown, 2),
            "total_profit": round(sum(profits), 2),
            "samples": n
        }
    
    def get_comprehensive_report(self, 
                                bets: List[Dict[str, Any]],
                                days: int = 30) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.
        """
        # Filter to last N days
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent_bets = [b for b in bets if b.get('date', '') >= cutoff]
        
        # Basic stats
        wins = sum(1 for b in recent_bets if b.get('result') == 'win')
        losses = sum(1 for b in recent_bets if b.get('result') == 'loss')
        pushes = sum(1 for b in recent_bets if b.get('result') == 'push')
        
        total_stake = sum(b.get('stake', 0) for b in recent_bets)
        total_profit = sum(b.get('profit', 0) or 0 for b in recent_bets)
        
        decisions = wins + losses
        
        # Calculate all metrics
        streaks = self.calculate_streaks(recent_bets)
        clv = self.calculate_clv_metrics(recent_bets)
        calibration = self.calculate_model_calibration(recent_bets)
        daily_roi = self.calculate_roi_by_period(recent_bets, 'day')
        variance = self.calculate_variance_metrics(recent_bets)
        
        return {
            "period_days": days,
            "period_start": cutoff,
            "summary": {
                "total_bets": len(recent_bets),
                "wins": wins,
                "losses": losses,
                "pushes": pushes,
                "win_rate": round(wins / decisions * 100, 1) if decisions > 0 else 0,
                "total_staked": round(total_stake, 2),
                "total_profit": round(total_profit, 2),
                "roi_pct": round(total_profit / total_stake * 100, 2) if total_stake > 0 else 0
            },
            "streaks": {
                "current_streak": streaks.current_streak,
                "current_type": streaks.current_type,
                "longest_win_streak": streaks.longest_win_streak,
                "longest_loss_streak": streaks.longest_loss_streak,
                "last_10": streaks.last_10_results
            },
            "clv_metrics": clv,
            "model_calibration": {
                "brier_score": calibration.brier_score,
                "calibration_error": calibration.calibration_error,
                "log_loss": calibration.log_loss,
                "bins": calibration.bins
            },
            "daily_performance": daily_roi[-10:] if len(daily_roi) > 10 else daily_roi,
            "variance_metrics": variance
        }
