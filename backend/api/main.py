"""
FastAPI application for the sports betting model.
Provides endpoints for picks, performance tracking, and analytics.
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, date
import os

# Import our modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.betting_model import SportsBettingModel, BetCandidate, create_candidate_from_dict
from core.kelly import BankrollManager
from data.db import BettingDatabase, Bet, db
from data.fetcher import DataAggregator, fetcher
from data.odds_api_integration import odds_manager, get_live_odds_for_sports
from ml.neural_ensemble import neural_ensemble
from ml.nlp_sentiment import sentiment_analyzer
from tracking.performance import PerformanceTracker


# Pydantic models for API
class BetCandidateInput(BaseModel):
    bet_id: str
    sport: str
    event: str
    event_id: str
    market_type: str = "moneyline"
    bet_type: str
    selection: str
    selection_team: Optional[str] = ""
    odds: int
    line: Optional[str] = ""
    model_probability: float = 0.5
    data_quality: float = 75.0
    sample_size: int = 30
    home_team: Optional[str] = ""
    away_team: Optional[str] = ""
    date: Optional[str] = None


class BetEvaluationOutput(BaseModel):
    bet_id: str
    sport: str
    event: str
    selection: str
    odds: int
    true_probability: float
    ev_pct: float
    edge_pct: float
    edge_score: float
    stake: float
    stake_pct: float
    qualified: bool
    filter_reasons: List[str]
    composite_score: float
    max_odds: int
    notes: str


class PlaceBetInput(BaseModel):
    bet_id: str
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
    date: Optional[str] = None
    notes: Optional[str] = ""


class SettleBetInput(BaseModel):
    bet_id: str
    result: str  # 'win', 'loss', 'push'
    profit: float


class PerformanceSummary(BaseModel):
    total_bets: int
    settled_bets: int
    open_bets: int
    wins: int
    losses: int
    pushes: int
    staked: float
    profit: float
    roi_pct: float
    hit_rate_pct: float
    avg_ev_pct: float
    win_loss_ratio: float


class BankrollStatus(BaseModel):
    initial_bankroll: float
    current_bankroll: float
    peak_bankroll: float
    total_return: float
    roi_pct: float
    current_drawdown_pct: float
    target_monthly_growth_pct: float


# Initialize FastAPI app
app = FastAPI(
    title="Sports Betting Model API",
    description="World-class +EV betting model with Kelly Criterion and advanced analytics",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize model and database
betting_model = SportsBettingModel(bankroll=1000.0)
tracker = PerformanceTracker()


@app.get("/api/model/config")
async def get_model_config():
    """Get current model configuration and thresholds."""
    return betting_model.get_model_config()


@app.post("/api/model/evaluate", response_model=BetEvaluationOutput)
async def evaluate_bet(candidate: BetCandidateInput):
    """
    Evaluate a single bet candidate.
    Returns EV, Kelly stake, and qualification status.
    """
    try:
        # Create BetCandidate from input
        candidate_data = candidate.dict()
        if not candidate_data.get('date'):
            candidate_data['date'] = datetime.now().strftime('%Y-%m-%d')
        
        bet_candidate = create_candidate_from_dict(candidate_data)
        
        # Evaluate
        evaluated = betting_model.evaluate_candidate(bet_candidate)
        
        return BetEvaluationOutput(
            bet_id=evaluated.bet_id,
            sport=evaluated.sport,
            event=evaluated.event,
            selection=evaluated.selection,
            odds=evaluated.odds,
            true_probability=round(evaluated.true_probability, 4),
            ev_pct=round(evaluated.ev_pct, 2),
            edge_pct=round(evaluated.edge_pct, 2),
            edge_score=round(evaluated.edge_score, 1),
            stake=evaluated.stake,
            stake_pct=evaluated.stake_pct,
            qualified=evaluated.qualified,
            filter_reasons=evaluated.filter_reasons,
            composite_score=evaluated.composite_score,
            max_odds=evaluated.max_odds,
            notes=evaluated.notes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/model/evaluate-batch")
async def evaluate_batch(candidates: List[BetCandidateInput]):
    """
    Evaluate multiple bet candidates and return ranked picks.
    """
    try:
        evaluated_candidates = []
        
        for candidate_input in candidates:
            candidate_data = candidate_input.dict()
            if not candidate_data.get('date'):
                candidate_data['date'] = datetime.now().strftime('%Y-%m-%d')
            
            bet_candidate = create_candidate_from_dict(candidate_data)
            evaluated = betting_model.evaluate_candidate(bet_candidate)
            evaluated_candidates.append(evaluated)
        
        # Filter and rank
        picks = betting_model.filter_and_rank_picks(evaluated_candidates)
        
        # Convert to output format
        results = []
        for pick in picks:
            results.append({
                "bet_id": pick.bet_id,
                "sport": pick.sport,
                "event": pick.event,
                "selection": pick.selection,
                "odds": pick.odds,
                "true_probability": round(pick.true_probability, 4),
                "ev_pct": round(pick.ev_pct, 2),
                "stake": pick.stake,
                "stake_pct": pick.stake_pct,
                "edge_score": round(pick.edge_score, 1),
                "composite_score": pick.composite_score,
                "qualified": pick.qualified,
                "notes": pick.notes
            })
        
        return {
            "total_evaluated": len(candidates),
            "qualified_picks": len(picks),
            "picks": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/picks/today")
async def get_todays_picks(
    sports: Optional[str] = Query(None, description="Comma-separated sport list (NBA,MLB,NFL)"),
    min_ev: float = Query(7.0, description="Minimum EV percentage"),
    max_picks: int = Query(10, description="Maximum picks to return")
):
    """
    Get today's +EV picks from available data sources.
    """
    try:
        # Determine which sports to fetch
        if sports:
            sport_list = [s.strip() for s in sports.split(',')]
        else:
            # Default to active sports
            sport_list = ["NBA", "NHL", "MLB"]
        
        all_candidates = []
        
        # Fetch from ESPN for each sport
        today_str = datetime.now().strftime('%Y%m%d')
        for sport in sport_list:
            candidates = fetcher.create_candidates_from_espn(sport, today_str)
            all_candidates.extend(candidates)
        
        # Evaluate all candidates
        evaluated = []
        for candidate_data in all_candidates:
            bet_candidate = create_candidate_from_dict(candidate_data)
            evaluated_candidate = betting_model.evaluate_candidate(bet_candidate)
            
            # Apply additional EV filter
            if evaluated_candidate.ev_pct >= min_ev:
                evaluated.append(evaluated_candidate)
        
        # Rank and filter
        picks = betting_model.filter_and_rank_picks(evaluated, max_picks=max_picks)
        
        return {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "sports_checked": sport_list,
            "total_candidates": len(all_candidates),
            "qualified_picks": len(picks),
            "picks": [
                {
                    "bet_id": p.bet_id,
                    "sport": p.sport,
                    "event": p.event,
                    "bet_type": p.bet_type,
                    "selection": p.selection,
                    "odds": p.odds,
                    "true_probability": round(p.true_probability * 100, 1),
                    "ev_pct": round(p.ev_pct, 2),
                    "stake": p.stake,
                    "stake_pct": p.stake_pct,
                    "edge_score": p.edge_score,
                    "composite_score": p.composite_score,
                    "max_odds": p.max_odds,
                    "notes": p.notes
                }
                for p in picks
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bets/place")
async def place_bet(bet: PlaceBetInput):
    """
    Record a placed bet in the tracking system.
    """
    try:
        bet_record = Bet(
            id=None,
            bet_id=bet.bet_id,
            date=bet.date or datetime.now().strftime('%Y-%m-%d'),
            sport=bet.sport,
            event=bet.event,
            event_id=bet.event_id,
            market_type=bet.market_type,
            bet_type=bet.bet_type,
            selection=bet.selection,
            odds=bet.odds,
            true_probability=bet.true_probability,
            ev_pct=bet.ev_pct,
            edge_score=bet.edge_score,
            stake=bet.stake,
            stake_pct=bet.stake_pct,
            notes=bet.notes
        )
        
        bet_id = db.insert_bet(bet_record)
        
        # Update bankroll exposure
        betting_model.bankroll_manager.kelly.add_exposure(bet.stake)
        
        return {
            "success": True,
            "bet_id": bet.bet_id,
            "db_id": bet_id,
            "message": f"Bet recorded: {bet.selection} @ {bet.odds}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bets/settle")
async def settle_bet(settlement: SettleBetInput):
    """
    Settle a bet with result and profit/loss.
    """
    try:
        success = db.settle_bet(settlement.bet_id, settlement.result, settlement.profit)
        
        if success:
            # Update bankroll
            betting_model.bankroll_manager.update_after_result(settlement.profit)
            
            return {
                "success": True,
                "bet_id": settlement.bet_id,
                "result": settlement.result,
                "profit": settlement.profit,
                "updated_bankroll": betting_model.bankroll_manager.current_bankroll
            }
        else:
            raise HTTPException(status_code=404, detail=f"Bet {settlement.bet_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bets/open")
async def get_open_bets():
    """Get all unsettled bets."""
    try:
        bets = db.get_open_bets()
        return {
            "count": len(bets),
            "bets": [
                {
                    "bet_id": b.bet_id,
                    "date": b.date,
                    "sport": b.sport,
                    "event": b.event,
                    "selection": b.selection,
                    "odds": b.odds,
                    "stake": b.stake,
                    "ev_pct": b.ev_pct
                }
                for b in bets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bets/history")
async def get_bet_history(days: int = Query(30, description="Days of history")):
    """Get settled bet history."""
    try:
        bets = db.get_settled_bets(days)
        return {
            "count": len(bets),
            "days": days,
            "bets": [
                {
                    "bet_id": b.bet_id,
                    "date": b.date,
                    "sport": b.sport,
                    "event": b.event,
                    "selection": b.selection,
                    "odds": b.odds,
                    "stake": b.stake,
                    "result": b.result,
                    "profit": b.profit,
                    "ev_pct": b.ev_pct
                }
                for b in bets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/performance/summary", response_model=PerformanceSummary)
async def get_performance_summary():
    """Get overall performance summary."""
    try:
        summary = db.get_performance_summary()
        return PerformanceSummary(**summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/performance/by-sport")
async def get_performance_by_sport():
    """Get performance breakdown by sport."""
    try:
        by_sport = db.get_performance_by_sport()
        return {"sports": by_sport}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bankroll/status", response_model=BankrollStatus)
async def get_bankroll_status():
    """Get current bankroll status and metrics."""
    try:
        status = betting_model.bankroll_manager.get_performance_metrics()
        return BankrollStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bankroll/history")
async def get_bankroll_history(days: int = Query(30, description="Days of history")):
    """Get bankroll history for charting."""
    try:
        history = db.get_bankroll_history(days)
        return {
            "days": days,
            "data_points": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/stats")
async def get_data_stats():
    """Get data fetcher statistics."""
    try:
        stats = fetcher.get_fetcher_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sports/active")
async def get_active_sports():
    """Get list of currently active sports with games."""
    try:
        from data.fetcher import ESPN_ENDPOINTS
        
        active_sports = []
        today_str = datetime.now().strftime('%Y%m%d')
        
        for sport, endpoint in ESPN_ENDPOINTS.items():
            schedule = fetcher.espn.get_schedule(sport, today_str)
            if schedule and schedule.get('events'):
                event_count = len(schedule.get('events', []))
                active_sports.append({
                    "sport": sport,
                    "events_today": event_count,
                    "has_odds": bool(schedule.get('events', [{}])[0].get('competitions', [{}])[0].get('odds'))
                })
        
        return {
            "date": today_str,
            "active_sports": active_sports
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/model/update-bankroll")
async def update_bankroll(new_bankroll: float):
    """Manually update current bankroll."""
    try:
        betting_model.bankroll_manager.current_bankroll = new_bankroll
        betting_model.kelly.update_bankroll(new_bankroll)
        betting_model.bankroll_manager.drawdown_mgr.update_peak(new_bankroll)
        
        return {
            "success": True,
            "new_bankroll": new_bankroll,
            "status": betting_model.bankroll_manager.get_performance_metrics()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# NEW: Odds API Integration Endpoints

@app.get("/api/odds/status")
async def get_odds_api_status():
    """Get The Odds API status and usage stats."""
    try:
        stats = odds_manager.get_usage_stats()
        return {
            "configured": stats['api_key_configured'],
            "requests_today": stats['requests_today'],
            "request_limit": stats['request_limit'],
            "remaining_today": stats['remaining_today'],
            "cache_ttl_seconds": stats['cache_ttl_seconds']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/odds/live")
async def get_live_odds(
    sports: Optional[str] = Query(None, description="Comma-separated sports (NBA,MLB,NFL)"),
    use_odds_api: bool = Query(True, description="Use The Odds API if available")
):
    """
    Get live odds from The Odds API or ESPN fallback.
    Returns candidates ready for evaluation.
    """
    try:
        candidates = []
        
        # Parse sports list
        if sports:
            sport_list = [s.strip() for s in sports.split(',')]
        else:
            sport_list = ["NBA", "NFL", "MLB", "NHL"]
        
        # Try Odds API first if enabled and configured
        if use_odds_api and odds_manager.get_usage_stats()['api_key_configured']:
            print("Fetching from The Odds API...")
            odds_candidates = get_live_odds_for_sports(sport_list)
            candidates.extend(odds_candidates)
        
        # Fallback to ESPN if no Odds API data
        if not candidates:
            print("Using ESPN fallback...")
            today_str = datetime.now().strftime('%Y%m%d')
            for sport in sport_list:
                espn_candidates = fetcher.create_candidates_from_espn(sport, today_str)
                candidates.extend(espn_candidates)
        
        # Evaluate all candidates
        evaluated = []
        for candidate_data in candidates:
            try:
                bet_candidate = create_candidate_from_dict(candidate_data)
                evaluated_candidate = betting_model.evaluate_candidate(bet_candidate)
                evaluated.append(evaluated_candidate)
            except Exception as e:
                print(f"Error evaluating candidate: {e}")
        
        # Filter and rank
        picks = betting_model.filter_and_rank_picks(evaluated, max_picks=20)
        
        return {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "source": "odds_api" if candidates and candidates[0].get('odds_source') == 'odds_api' else "espn",
            "sports_checked": sport_list,
            "total_candidates": len(candidates),
            "evaluated_count": len(evaluated),
            "qualified_picks": len(picks),
            "picks": [
                {
                    "bet_id": p.bet_id,
                    "sport": p.sport,
                    "event": p.event,
                    "bet_type": p.bet_type,
                    "selection": p.selection,
                    "odds": p.odds,
                    "best_odds": p.best_odds if hasattr(p, 'best_odds') else p.odds,
                    "true_probability": round(p.true_probability * 100, 1),
                    "ev_pct": round(p.ev_pct, 2),
                    "stake": p.stake,
                    "stake_pct": p.stake_pct,
                    "edge_score": p.edge_score,
                    "composite_score": p.composite_score,
                    "max_odds": p.max_odds,
                    "qualified": p.qualified,
                    "notes": p.notes
                }
                for p in picks
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/odds/comparison")
async def get_odds_comparison(
    event_id: str = Query(..., description="Event ID to compare odds")
):
    """
    Get odds comparison across multiple sportsbooks for a specific event.
    Shows best available odds and line shopping opportunities.
    """
    try:
        # This would need the sport to be stored or passed
        # For now, return placeholder structure
        return {
            "event_id": event_id,
            "comparison": {
                "home_team": "Team A",
                "away_team": "Team B",
                "books": []
            },
            "message": "Odds comparison requires event details from database"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/odds/sports")
async def get_odds_api_sports():
    """Get list of sports available from The Odds API."""
    try:
        from data.odds_api_integration import SPORT_KEYS
        
        return {
            "supported_sports": list(SPORT_KEYS.keys()),
            "mapping": SPORT_KEYS,
            "note": "Configure ODDS_API_KEY environment variable to use"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ML & NLP Endpoints

@app.get("/api/ml/neural/status")
async def get_neural_model_status():
    """Get neural network model status and info."""
    try:
        info = neural_ensemble.get_model_info()
        return {
            "model_version": info['model_version'],
            "tensorflow_available": info['tensorflow_available'],
            "model_loaded": info['model_loaded'],
            "scaler_configured": info['scaler_configured'],
            "input_dim": info['input_dim']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ml/neural/predict")
async def neural_predict(candidate: BetCandidateInput):
    """
    Get neural network prediction for a candidate.
    Returns probability and confidence.
    """
    try:
        candidate_data = candidate.dict()
        
        prediction = neural_ensemble.predict(candidate_data)
        
        if prediction:
            return {
                "success": True,
                "probability": round(prediction.probability, 4),
                "confidence": round(prediction.confidence, 4),
                "model_version": prediction.model_version
            }
        else:
            return {
                "success": False,
                "error": "Prediction failed"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/nlp/analyze")
async def analyze_sentiment(text: str, category: str = "general"):
    """
    Analyze sentiment of sports news/text.
    Detects injuries, lineup changes, momentum shifts.
    """
    try:
        result = sentiment_analyzer.analyze_text(text, category)
        
        return {
            "text": result.text,
            "sentiment": result.sentiment,
            "confidence": round(result.confidence, 3),
            "category": result.category,
            "entities": result.entities,
            "impact_score": round(result.impact_score, 3),
            "interpretation": _interpret_impact(result.impact_score)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _interpret_impact(impact: float) -> str:
    """Interpret impact score for humans."""
    if impact > 0.5:
        return "Strong positive signal"
    elif impact > 0.2:
        return "Moderate positive signal"
    elif impact < -0.5:
        return "Strong negative signal"
    elif impact < -0.2:
        return "Moderate negative signal"
    else:
        return "Neutral/unclear signal"


@app.post("/api/nlp/team-summary")
async def get_team_sentiment(team: str, news_items: List[Dict[str, Any]]):
    """Get sentiment summary for a team based on news."""
    try:
        summary = sentiment_analyzer.get_team_sentiment_summary(team, news_items)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/nlp/detect-lineup")
async def detect_lineup_change(text: str):
    """Detect lineup changes from text."""
    try:
        result = sentiment_analyzer.detect_lineup_changes(text)
        
        if result:
            return {
                "detected": True,
                "change_type": result['change_type'],
                "players_affected": result['players_affected'],
                "impact_score": result['impact_score'],
                "significance": "High" if abs(result['impact_score']) > 0.5 else "Medium"
            }
        else:
            return {
                "detected": False,
                "message": "No lineup change detected"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Production: Health check endpoint for monitoring
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway monitoring."""
    try:
        # Check database connection
        summary = db.get_performance_summary()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "total_bets": summary.get('total_bets', 0),
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Production: Serve static frontend files
# This should be added AFTER all API routes
def setup_static_files():
    """Setup static file serving for production."""
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    
    if frontend_dist.exists():
        # Mount static files at root, but API routes take precedence
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")
        print(f"Serving frontend from {frontend_dist}")
    else:
        print(f"Frontend build not found at {frontend_dist}")
        print("Run 'cd frontend && npm run build' to create production build")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
else:
    # Production: setup static files when imported
    setup_static_files()
