"""
Model Calibration Tracking
Monitors prediction accuracy and calibration quality
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict

from .ev_calculator import calculate_brier_score, calculate_confidence_interval


@dataclass
class CalibrationRecord:
    """Single prediction outcome record for calibration tracking."""
    bet_id: str
    date: str
    sport: str
    predicted_probability: float
    actual_outcome: int  # 1 = win, 0 = loss
    odds: int
    ev_pct: float
    edge_score: float
    sample_size: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


class CalibrationTracker:
    """
    Tracks model calibration and prediction accuracy over time.
    Provides metrics to assess if probabilities are well-calibrated.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path(__file__).parent.parent.parent / "data" / "calibration"
        
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.records_file = self.storage_path / "calibration_records.json"
        self.metrics_file = self.storage_path / "calibration_metrics.json"
        
        self.records: List[CalibrationRecord] = []
        self._load_records()
    
    def _load_records(self):
        """Load historical calibration records."""
        if self.records_file.exists():
            try:
                with open(self.records_file, 'r') as f:
                    data = json.load(f)
                    self.records = [CalibrationRecord(**r) for r in data]
            except Exception as e:
                print(f"Error loading calibration records: {e}")
                self.records = []
    
    def _save_records(self):
        """Save calibration records to disk."""
        try:
            with open(self.records_file, 'w') as f:
                json.dump([r.to_dict() for r in self.records], f, indent=2)
        except Exception as e:
            print(f"Error saving calibration records: {e}")
    
    def add_record(self, 
                   bet_id: str,
                   sport: str,
                   predicted_probability: float,
                   actual_outcome: int,
                   odds: int,
                   ev_pct: float,
                   edge_score: float,
                   sample_size: int):
        """
        Add a new calibration record.
        
        Args:
            bet_id: Unique bet identifier
            sport: Sport/category
            predicted_probability: Model's predicted win probability (0-1)
            actual_outcome: 1 for win, 0 for loss
            odds: American odds of the bet
            ev_pct: Expected value percentage
            edge_score: Composite edge score
            sample_size: Sample size for confidence
        """
        record = CalibrationRecord(
            bet_id=bet_id,
            date=datetime.now().strftime('%Y-%m-%d'),
            sport=sport,
            predicted_probability=predicted_probability,
            actual_outcome=actual_outcome,
            odds=odds,
            ev_pct=ev_pct,
            edge_score=edge_score,
            sample_size=sample_size
        )
        
        self.records.append(record)
        self._save_records()
        
        print(f"📊 Added calibration record: {bet_id} (predicted: {predicted_probability:.1%}, outcome: {actual_outcome})")
    
    def get_brier_score(self, days: int = 30, sport: Optional[str] = None) -> float:
        """
        Calculate Brier score for recent predictions.
        Lower is better (0 = perfect, 0.25 = random).
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        filtered = [
            r for r in self.records 
            if r.date >= cutoff_date and (sport is None or r.sport == sport)
        ]
        
        if len(filtered) < 5:
            return 0.0  # Not enough data
        
        predicted = [r.predicted_probability for r in filtered]
        outcomes = [r.actual_outcome for r in filtered]
        
        return calculate_brier_score(predicted, outcomes)
    
    def get_calibration_by_bins(self, days: int = 30, bins: int = 5) -> List[Dict]:
        """
        Get calibration analysis by probability bins.
        Shows if model is over/under-confident in different ranges.
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent = [r for r in self.records if r.date >= cutoff_date]
        
        if len(recent) < 10:
            return []
        
        # Create bins (e.g., 0-20%, 20-40%, 40-60%, 60-80%, 80-100%)
        bin_size = 1.0 / bins
        results = []
        
        for i in range(bins):
            bin_min = i * bin_size
            bin_max = (i + 1) * bin_size
            
            # Get records in this bin
            bin_records = [
                r for r in recent 
                if bin_min <= r.predicted_probability < bin_max
            ]
            
            if len(bin_records) < 3:
                continue
            
            # Calculate average predicted probability
            avg_predicted = sum(r.predicted_probability for r in bin_records) / len(bin_records)
            
            # Calculate actual win rate
            actual_win_rate = sum(r.actual_outcome for r in bin_records) / len(bin_records)
            
            # Calibration error (predicted vs actual)
            calibration_error = avg_predicted - actual_win_rate
            
            results.append({
                'bin_range': f"{bin_min:.0%}-{bin_max:.0%}",
                'predicted_probability': round(avg_predicted, 3),
                'actual_win_rate': round(actual_win_rate, 3),
                'calibration_error': round(calibration_error, 3),
                'sample_size': len(bin_records),
                'assessment': 'overconfident' if calibration_error > 0.05 else 'underconfident' if calibration_error < -0.05 else 'well-calibrated'
            })
        
        return results
    
    def get_roi_by_ev_threshold(self, days: int = 30) -> List[Dict]:
        """
        Analyze ROI by EV threshold buckets.
        Shows if higher EV bets actually perform better.
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent = [r for r in self.records if r.date >= cutoff_date]
        
        if len(recent) < 10:
            return []
        
        # Create EV buckets
        buckets = [
            (0, 3, "0-3% EV"),
            (3, 7, "3-7% EV"),
            (7, 12, "7-12% EV"),
            (12, 20, "12-20% EV"),
            (20, 100, "20%+ EV")
        ]
        
        results = []
        for min_ev, max_ev, label in buckets:
            bucket_records = [
                r for r in recent if min_ev <= r.ev_pct < max_ev
            ]
            
            if len(bucket_records) < 3:
                continue
            
            wins = sum(r.actual_outcome for r in bucket_records)
            win_rate = wins / len(bucket_records)
            
            # Calculate approximate ROI
            # Simplified: assume average odds of -110 for calculation
            roi = (win_rate * 0.91) - (1 - win_rate) if win_rate > 0 else -1.0
            roi_pct = roi * 100
            
            results.append({
                'ev_bucket': label,
                'bets': len(bucket_records),
                'wins': wins,
                'win_rate': round(win_rate * 100, 1),
                'estimated_roi': round(roi_pct, 2),
                'avg_predicted_prob': round(
                    sum(r.predicted_probability for r in bucket_records) / len(bucket_records), 3
                )
            })
        
        return results
    
    def get_performance_summary(self, days: int = 30) -> Dict:
        """Get comprehensive calibration and performance summary."""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        recent = [r for r in self.records if r.date >= cutoff_date]
        
        if len(recent) < 5:
            return {
                'status': 'insufficient_data',
                'message': f'Need at least 5 bets for calibration analysis. Currently have {len(recent)}.',
                'total_bets': len(recent)
            }
        
        # Overall metrics
        total_bets = len(recent)
        wins = sum(r.actual_outcome for r in recent)
        win_rate = wins / total_bets
        
        # Brier score
        brier = self.get_brier_score(days)
        
        # Calibration assessment
        calibration_bins = self.get_calibration_by_bins(days)
        
        # EV bucket performance
        ev_performance = self.get_roi_by_ev_threshold(days)
        
        # Assessment
        if brier < 0.15:
            calibration_quality = "excellent"
        elif brier < 0.20:
            calibration_quality = "good"
        elif brier < 0.25:
            calibration_quality = "fair"
        else:
            calibration_quality = "poor"
        
        return {
            'status': 'ok',
            'period_days': days,
            'total_bets': total_bets,
            'wins': wins,
            'losses': total_bets - wins,
            'win_rate': round(win_rate * 100, 1),
            'brier_score': round(brier, 4),
            'calibration_quality': calibration_quality,
            'calibration_by_bins': calibration_bins,
            'ev_bucket_performance': ev_performance,
            'recommendations': self._generate_recommendations(brier, calibration_bins, ev_performance)
        }
    
    def _generate_recommendations(self, brier: float, calibration_bins: List[Dict], ev_performance: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on calibration analysis."""
        recommendations = []
        
        # Brier score assessment
        if brier > 0.25:
            recommendations.append("Model calibration is poor - probabilities need significant adjustment")
        elif brier > 0.20:
            recommendations.append("Model calibration is fair but could be improved")
        
        # Check for systematic over/under-confidence
        overconfident_bins = [b for b in calibration_bins if b.get('assessment') == 'overconfident']
        underconfident_bins = [b for b in calibration_bins if b.get('assessment') == 'underconfident']
        
        if overconfident_bins:
            ranges = [b['bin_range'] for b in overconfident_bins]
            recommendations.append(f"Model is overconfident in ranges: {', '.join(ranges)} - consider reducing probabilities")
        
        if underconfident_bins:
            ranges = [b['bin_range'] for b in underconfident_bins]
            recommendations.append(f"Model is underconfident in ranges: {', '.join(ranges)} - can be more aggressive")
        
        # EV performance check
        if ev_performance:
            high_ev = [e for e in ev_performance if '12-' in e['ev_bucket'] or '20+' in e['ev_bucket']]
            low_ev = [e for e in ev_performance if '0-3%' in e['ev_bucket'] or '3-7%' in e['ev_bucket']]
            
            if high_ev and all(e['win_rate'] < 50 for e in high_ev):
                recommendations.append("High EV bets are underperforming - model may be overestimating edge")
            
            if low_ev and all(e['win_rate'] > 55 for e in low_ev):
                recommendations.append("Low EV bets are overperforming - consider lowering EV thresholds")
        
        if not recommendations:
            recommendations.append("Model is well-calibrated - continue current approach")
        
        return recommendations
    
    def export_data(self, format: str = 'json') -> str:
        """Export calibration data for external analysis."""
        if format == 'json':
            data = {
                'export_date': datetime.now().isoformat(),
                'total_records': len(self.records),
                'records': [r.to_dict() for r in self.records]
            }
            return json.dumps(data, indent=2)
        
        # CSV format
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['bet_id', 'date', 'sport', 'predicted_probability', 'actual_outcome', 'odds', 'ev_pct', 'edge_score'])
        
        for r in self.records:
            writer.writerow([r.bet_id, r.date, r.sport, r.predicted_probability, r.actual_outcome, r.odds, r.ev_pct, r.edge_score])
        
        return output.getvalue()


# Global instance
calibration_tracker = CalibrationTracker()
