"""Expected Value (EV) and probability calculations for sports betting."""

import math
from typing import Tuple, Optional


def american_to_probability(odds: int) -> float:
    """Convert American odds to implied probability (0-1)."""
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds."""
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1


def american_to_profit_multiple(odds: int) -> float:
    """Convert American odds to profit multiple (decimal - 1)."""
    if odds > 0:
        return odds / 100
    else:
        return 100 / abs(odds)


def probability_to_american(probability: float) -> int:
    """Convert probability (0-1) to American odds."""
    if probability >= 0.5:
        return -int((probability / (1 - probability)) * 100)
    else:
        return int(((1 - probability) / probability) * 100)


def calculate_fair_probability(odds1: int, odds2: int) -> Tuple[float, float]:
    """Calculate fair (no-vig) probabilities from two-way market."""
    prob1 = american_to_probability(odds1)
    prob2 = american_to_probability(odds2)
    
    # Remove vig
    total_prob = prob1 + prob2
    fair_prob1 = prob1 / total_prob
    fair_prob2 = prob2 / total_prob
    
    return fair_prob1, fair_prob2


def calculate_ev(true_probability: float, odds: int) -> float:
    """
    Calculate expected value as percentage.
    
    Args:
        true_probability: Model's estimated win probability (0-1)
        odds: American odds (+150, -110, etc.)
    
    Returns:
        EV percentage (e.g., 0.15 = +15% EV)
    """
    implied_prob = american_to_probability(odds)
    profit_mult = american_to_profit_multiple(odds)
    
    # EV = (P(win) * Profit) - (P(loss) * 1)
    ev = (true_probability * profit_mult) - ((1 - true_probability) * 1)
    return ev


def calculate_ev_percentage(true_probability: float, odds: int) -> float:
    """Calculate EV as percentage (e.g., 7.5 for +7.5% EV)."""
    return calculate_ev(true_probability, odds) * 100


def calculate_edge(true_probability: float, odds: int) -> float:
    """Calculate edge over market (true_prob - implied_prob)."""
    implied_prob = american_to_probability(odds)
    return true_probability - implied_prob


def calculate_expected_profit(stake: float, ev_pct: float) -> float:
    """Calculate expected profit for a given stake and EV."""
    return stake * (ev_pct / 100)


def calculate_clv(bet_odds: int, closing_odds: int) -> float:
    """
    Calculate Closing Line Value (CLV) percentage.
    Positive CLV means you beat the closing line.
    """
    bet_prob = american_to_probability(bet_odds)
    close_prob = american_to_probability(closing_odds)
    return (close_prob - bet_prob) * 100


def get_max_odds_for_ev_threshold(true_probability: float, 
                                   min_ev_pct: float = 2.0) -> int:
    """
    Find the maximum odds where EV is still above threshold.
    Used to determine when line movement makes a bet unprofitable.
    """
    # Start from fair odds and work outward
    fair_odds = probability_to_american(true_probability)
    
    if fair_odds < 0:
        # Negative odds: check tighter lines (more negative)
        for test_odds in range(fair_odds, -500, -1):
            ev = calculate_ev_percentage(true_probability, test_odds)
            if ev < min_ev_pct:
                return test_odds + 1
        return -500
    else:
        # Positive odds: check longer odds (higher positive)
        for test_odds in range(fair_odds, 500):
            ev = calculate_ev_percentage(true_probability, test_odds)
            if ev < min_ev_pct:
                return test_odds - 1
        return 500


def calculate_parlay_ev(individual_probs: list[float], 
                         combined_odds: int) -> float:
    """
    Calculate EV for a parlay.
    
    Args:
        individual_probs: List of win probabilities for each leg
        combined_odds: American odds for the parlay
    
    Returns:
        EV percentage
    """
    combined_prob = math.prod(individual_probs)
    return calculate_ev_percentage(combined_prob, combined_odds)


def calculate_confidence_interval(probability: float, 
                                   sample_size: int, 
                                   confidence: float = 0.95) -> Tuple[float, float]:
    """
    Calculate Wilson score confidence interval for a probability.
    Used to quantify uncertainty in probability estimates.
    """
    if sample_size == 0:
        return (0, 1)
    
    z = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%
    
    # Wilson score interval
    p = probability
    n = sample_size
    
    denominator = 1 + z**2 / n
    centre_adjusted_probability = p + z**2 / (2 * n)
    adjusted_standard_deviation = math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    
    lower_bound = (centre_adjusted_probability - z * adjusted_standard_deviation) / denominator
    upper_bound = (centre_adjusted_probability + z * adjusted_standard_deviation) / denominator
    
    return (max(0, lower_bound), min(1, upper_bound))


def bayesian_update(prior_prob: float, 
                   likelihood: float,
                   prior_strength: int = 10) -> float:
    """
    Bayesian probability update.
    
    Args:
        prior_prob: Initial probability estimate
        likelihood: New evidence probability
        prior_strength: How confident we are in prior (pseudo-observations)
    
    Returns:
        Updated (posterior) probability
    """
    # Beta distribution parameterization
    # Prior: Beta(alpha, beta)
    alpha_prior = prior_prob * prior_strength
    beta_prior = (1 - prior_prob) * prior_strength
    
    # Update with likelihood
    # Simplified: weighted average based on evidence strength
    evidence_strength = 5  # Assume moderate evidence
    alpha_post = alpha_prior + likelihood * evidence_strength
    beta_post = beta_prior + (1 - likelihood) * evidence_strength
    
    # Posterior mean
    posterior_prob = alpha_post / (alpha_post + beta_post)
    
    return posterior_prob


def calculate_composite_score(ev_pct: float,
                              edge: float,
                              true_prob: float,
                              quality: float,
                              sample_size: int,
                              confidence_width: float = 0.0,
                              clv: float = 0.0,
                              sport: str = "default",
                              history_boost: float = 0) -> float:
    """
    Enhanced composite edge score (0-100) for ranking bets.
    Uses optimized weights based on professional betting research.
    
    Args:
        ev_pct: Expected value percentage
        edge: Edge over market (as decimal, e.g., 0.05 = 5%)
        true_prob: True win probability
        quality: Data quality score (0-100)
        sample_size: Sample size for confidence
        confidence_width: Width of confidence interval (uncertainty measure)
        clv: Closing Line Value percentage
        sport: Sport for sport-specific adjustments
        history_boost: Historical performance bonus
    
    Returns:
        Composite score from 0-100
    """
    # === WEIGHTED COMPONENTS (Total: 100 points) ===
    
    # EV contribution (40% - primary factor)
    # Higher EV = better, but diminishing returns above 15%
    ev_score = min(ev_pct / 0.20, 40)  # 20% EV = full 40 points
    
    # Edge contribution (15% - secondary confirmation)
    edge_score = min(abs(edge) * 100 * 1.5, 15)
    
    # Confidence/Uncertainty contribution (20% - new!)
    # Narrow confidence interval = higher confidence
    # confidence_width is typically 0.05-0.20 (5-20%)
    confidence_score = max(0, 20 - (confidence_width * 100))
    
    # Probability sweet spot (10% - risk management)
    # Sweet spot is 45-65% probability (manageable variance)
    prob_distance = abs(true_prob - 0.55)
    prob_score = max(0, 10 - (prob_distance * 15))
    
    # Data quality (10% - trust factor)
    quality_score = (quality / 100) * 10
    
    # Sample size (5% - experience factor)
    sample_score = min(sample_size / 50, 1) * 5
    
    # CLV contribution (bonus up to 5 points)
    # Positive CLV (beat closing line) is strong signal
    clv_bonus = max(0, min(clv / 2, 5))
    
    # Sport-specific adjustments
    sport_multipliers = {
        'NFL': 1.05, 'NBA': 1.05,  # More predictable - slight boost
        'MLB': 0.98, 'NHL': 0.98,  # Higher variance - slight reduction
        'NCAAMB': 0.95, 'NCAAF': 0.95,  # Less efficient but volatile
        'default': 1.0
    }
    sport_multiplier = sport_multipliers.get(sport, 1.0)
    
    # History boost (bonus)
    history_bonus = history_boost
    
    # Calculate total
    subtotal = ev_score + edge_score + confidence_score + prob_score + quality_score + sample_score
    total = (subtotal * sport_multiplier) + clv_bonus + history_bonus
    
    return min(total, 100)


def calculate_variance_adjusted_ev(true_probability: float,
                                    odds: int,
                                    sample_size: int,
                                    quality: float) -> float:
    """
    Calculate EV adjusted for uncertainty in probability estimate.
    Uses conservative probability estimate from confidence interval.
    """
    # Get confidence interval
    lower_bound, upper_bound = calculate_confidence_interval(
        true_probability, sample_size, confidence=0.90
    )
    
    # Quality adjustment - lower quality = more conservative
    quality_factor = quality / 100
    
    # Blend between lower bound and point estimate based on quality
    # Low quality: use lower bound (pessimistic)
    # High quality: use point estimate
    conservative_prob = (lower_bound * (1 - quality_factor)) + (true_probability * quality_factor)
    
    # Calculate EV with conservative probability
    return calculate_ev_percentage(conservative_prob, odds)


def calculate_closing_line_value(bet_odds: int, closing_odds: int) -> float:
    """
    Calculate Closing Line Value (CLV) as percentage.
    Positive CLV means you beat the closing line (good).
    Negative CLV means closing line moved against you (bad).
    """
    # Convert both to implied probabilities
    bet_prob = american_to_probability(bet_odds)
    close_prob = american_to_probability(closing_odds)
    
    # For underdogs (positive odds): lower closing odds is better
    # For favorites (negative odds): higher closing odds is better (less negative)
    if bet_odds > 0:
        # Underdog: bet_prob > close_prob means line moved in our favor
        clv = (bet_prob - close_prob) * 100
    else:
        # Favorite: bet_prob < close_prob means line moved in our favor
        # (e.g., bet at -110, close at -105: we got worse odds = negative CLV)
        clv = (close_prob - bet_prob) * 100
    
    return clv


def is_plus_ev(true_probability: float, odds: int, threshold: float = 0.07) -> bool:
    """Quick check if bet is +EV above threshold."""
    ev_pct = calculate_ev_percentage(true_probability, odds)
    return ev_pct >= threshold * 100


def calculate_brier_score(predicted_probs: list[float], outcomes: list[int]) -> float:
    """
    Calculate Brier score for model calibration assessment.
    Lower score = better calibration (0 = perfect, 0.25 = random, 0.5 = worst).
    
    Args:
        predicted_probs: List of predicted probabilities (0-1)
        outcomes: List of actual outcomes (1 = win, 0 = loss)
    
    Returns:
        Brier score (mean squared error)
    """
    if len(predicted_probs) != len(outcomes):
        raise ValueError("Predicted probabilities and outcomes must have same length")
    
    if len(predicted_probs) == 0:
        return 0.0
    
    squared_errors = [(pred - actual) ** 2 for pred, actual in zip(predicted_probs, outcomes)]
    return sum(squared_errors) / len(squared_errors)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))
