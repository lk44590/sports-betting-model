"""
FastAPI application for the sports betting model.
Provides endpoints for picks, performance tracking, and analytics.
"""

# Load environment variables FIRST (before any module imports)
from pathlib import Path
import os
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)  # Override Railway's env vars with .env file

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# Import our modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.betting_model import SportsBettingModel, BetCandidate, create_candidate_from_dict
from core.kelly import BankrollManager
from data.db import BettingDatabase, Bet, db
from data.fetcher import DataAggregator, fetcher
from data.odds_api_integration import odds_manager, get_live_odds_for_sports, OddsAPIManager

# Reinitialize odds_manager with correct API key from .env
api_key = os.getenv('ODDS_API_KEY')
if api_key:
    odds_manager = OddsAPIManager(api_key)
    print(f"✅ Reinitialized OddsAPIManager with API key: {api_key[:4]}...{api_key[-4:]}")
from data.team_stats import team_stats_manager
from data.espn_fetcher import espn_fetcher
from ml.neural_ensemble import neural_ensemble
from ml.nlp_sentiment import sentiment_analyzer
from ml.predictive_model import predictive_model, GamePrediction
from tracking.performance import PerformanceTracker
from tracking.backtester import backtester, BacktestResult
from paper_trading.auto_trader import auto_trader, PaperTradingSettings


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


@app.get("/api/status")
async def get_system_status():
    """
    Get complete system health status.
    Use this to verify deployment is working correctly.
    """
    try:
        odds_stats = odds_manager.get_usage_stats()
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "odds_api": {
                "configured": odds_stats['api_key_configured'],
                "requests_today": odds_stats['requests_today'],
                "request_limit": odds_stats['request_limit'],
                "remaining": odds_stats['remaining_today']
            },
            "model": {
                "bankroll": betting_model.bankroll_manager.current_bankroll,
                "kelly_fraction": betting_model.config['kelly_fraction'],
                "min_ev_pct": betting_model.config['min_ev_pct'],
                "min_edge_score": betting_model.config['min_edge_score']
            },
            "paper_trading": {
                "enabled": auto_trader.get_settings().enabled if auto_trader.session else False,
                "current_bankroll": auto_trader.get_current_bankroll() if auto_trader.session else 10000.0
            },
            "next_steps": [] if odds_stats['api_key_configured'] else [
                "Set ODDS_API_KEY in Railway Variables",
                "Get free key at https://the-odds-api.com/",
                "Redeploy after adding key"
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


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
    min_ev: float = Query(6.0, description="Minimum EV percentage"),
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
        data_source = "none"
        
        # Try to fetch from The Odds API for real live games
        print(f"🔍 Checking Odds API key: {odds_manager.get_usage_stats()['api_key_configured']}")
        try:
            # Get live odds from The Odds API
            odds_candidates = get_live_odds_for_sports(sport_list)
            if odds_candidates:
                all_candidates.extend(odds_candidates)
                data_source = "odds_api"
                print(f"✅ Loaded {len(odds_candidates)} live odds from The Odds API")
            else:
                print("⚠️ Odds API returned no candidates")
        except Exception as e:
            print(f"❌ Odds API failed: {e}")
        
        # Check if no games found
        if not all_candidates:
            print("� No upcoming games found for today")
            data_source = "none"
            
            # Return empty response with clear message
            return {
                "date": datetime.now().strftime('%Y-%m-%d'),
                "sports_checked": sport_list,
                "data_source": data_source,
                "total_candidates": 0,
                "qualified_picks": 0,
                "message": "No upcoming games found for today. Check back later when games are scheduled.",
                "picks": []
            }
        
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
        
        # Auto-create paper bets for tracking
        paper_bets_created = 0
        try:
            for pick in picks:
                pick_dict = {
                    'bet_id': pick.bet_id,
                    'sport': pick.sport,
                    'event': pick.event,
                    'selection': pick.selection,
                    'bet_type': pick.bet_type,
                    'odds': pick.odds,
                    'true_probability': pick.true_probability * 100,
                    'ev_pct': pick.ev_pct
                }
                if auto_trader.create_paper_bet(pick_dict):
                    paper_bets_created += 1
            if paper_bets_created > 0:
                print(f"📝 Auto-created {paper_bets_created} paper bets for tracking")
        except Exception as e:
            print(f"⚠️ Could not create paper bets: {e}")
        
        # Get game times from candidates
        game_times = {}
        for c in all_candidates:
            game_times[c.get('bet_id', '')] = c.get('commence_time', '')
        
        return {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "sports_checked": sport_list,
            "data_source": data_source,
            "total_candidates": len(all_candidates),
            "qualified_picks": len(picks),
            "picks": [
                {
                    "bet_id": p.bet_id,
                    "sport": p.sport,
                    "event": p.event,
                    "game_time": game_times.get(p.bet_id, ''),
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
        # Mask API key for security
        api_key_preview = None
        if stats['api_key_configured'] and os.getenv('ODDS_API_KEY'):
            key = os.getenv('ODDS_API_KEY')
            api_key_preview = f"{key[:4]}...{key[-4:]}"
        
        return {
            "configured": stats['api_key_configured'],
            "api_key_preview": api_key_preview,
            "requests_today": stats['requests_today'],
            "request_limit": stats['request_limit'],
            "remaining_today": stats['remaining_today'],
            "cache_ttl_seconds": stats['cache_ttl_seconds']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/odds/clear-cache")
async def clear_odds_cache():
    """Clear the Odds API cache to force fresh data fetching."""
    try:
        success = odds_manager.clear_cache()
        return {
            "success": success,
            "message": "Cache cleared" if success else "Failed to clear cache"
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


# Team Statistics Endpoints

@app.get("/api/stats/teams")
async def get_team_statistics(
    sport: str = Query(..., description="Sport (NBA, MLB, NFL, NHL)"),
    season: Optional[str] = Query(None, description="Season year (default: current)")
):
    """Get team statistics for a sport."""
    try:
        if season is None:
            season = str(datetime.now().year)
        
        # Try to fetch from ESPN
        espn_fetcher.update_all_team_stats(sport, season)
        
        # Get stats from database
        teams = team_stats_manager.get_all_teams_stats(sport, season)
        
        return {
            "sport": sport,
            "season": season,
            "teams_count": len(teams),
            "teams": [
                {
                    "team_id": t.team_id,
                    "name": t.team_name,
                    "record": f"{t.wins}-{t.losses}",
                    "home_record": f"{t.home_wins}-{t.home_losses}",
                    "away_record": f"{t.away_wins}-{t.away_losses}",
                    "points_scored_avg": round(t.points_scored, 1),
                    "points_allowed_avg": round(t.points_allowed, 1),
                    "last_10": f"{t.last_10_wins}-{t.last_10_losses}",
                    "streak": t.current_streak,
                    "updated": t.updated_at
                }
                for t in teams
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stats/update")
async def update_team_stats(
    sport: str = Query(..., description="Sport to update"),
    season: Optional[str] = Query(None, description="Season year")
):
    """Force update team statistics from ESPN."""
    try:
        if season is None:
            season = str(datetime.now().year)
        
        espn_fetcher.update_all_team_stats(sport, season)
        
        return {
            "success": True,
            "sport": sport,
            "season": season,
            "message": f"Updated team stats for {sport}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Predictive Model Endpoints

@app.get("/api/model/predict")
async def predict_game(
    home_team_id: str = Query(..., description="Home team ID"),
    away_team_id: str = Query(..., description="Away team ID"),
    sport: str = Query(..., description="Sport"),
    season: Optional[str] = Query(None, description="Season year")
):
    """Get prediction for a specific game."""
    try:
        prediction = predictive_model.predict_game(home_team_id, away_team_id, sport, season)
        
        if not prediction:
            raise HTTPException(status_code=404, detail="Could not generate prediction - check team IDs and sport")
        
        return {
            "home_team": prediction.home_team,
            "away_team": prediction.away_team,
            "sport": prediction.sport,
            "predictions": {
                "moneyline": {
                    "home_win_prob": prediction.home_win_probability,
                    "away_win_prob": prediction.away_win_probability
                },
                "spread": {
                    "predicted_spread": prediction.predicted_spread,
                    "home_cover_prob": prediction.home_spread_prob,
                    "away_cover_prob": prediction.away_spread_prob
                },
                "total": {
                    "predicted_total": prediction.predicted_total,
                    "over_prob": prediction.over_prob,
                    "under_prob": prediction.under_prob
                }
            },
            "confidence": prediction.confidence,
            "sample_size": prediction.sample_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/model/advanced-picks")
async def get_advanced_picks(
    sports: Optional[str] = Query(None, description="Comma-separated sports"),
    min_ev: float = Query(0.05, description="Minimum EV threshold (as decimal, e.g., 0.05 = 5%)"),
    include_spreads: bool = Query(True, description="Include spread bets"),
    include_totals: bool = Query(True, description="Include total bets")
):
    """
    Get advanced picks using predictive model + current odds.
    Compares model predictions to market odds to find value.
    """
    try:
        sport_list = [s.strip() for s in sports.split(',')] if sports else ["NBA", "MLB", "NHL"]
        
        # Get current odds
        from data.odds_api_integration import odds_manager
        odds_data = odds_manager.get_all_odds(sport_list)
        
        # Convert to games format
        games = []
        for sport, events in odds_data.items():
            for event in events:
                # Extract teams and odds
                home_team = event.get('home_team', '')
                away_team = event.get('away_team', '')
                
                # Parse bookmakers for best odds
                bookmakers = event.get('bookmakers', [])
                if not bookmakers:
                    continue
                
                # Get moneyline odds
                home_ml = None
                away_ml = None
                
                for book in bookmakers:
                    for market in book.get('markets', []):
                        if market.get('key') == 'h2h':
                            outcomes = market.get('outcomes', [])
                            for outcome in outcomes:
                                if outcome.get('name') == home_team:
                                    home_ml = int(outcome.get('price', 0))
                                elif outcome.get('name') == away_team:
                                    away_ml = int(outcome.get('price', 0))
                
                if home_ml and away_ml:
                    games.append({
                        'sport': sport,
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_team_id': None,  # Would need mapping
                        'away_team_id': None,
                        'home_ml_odds': home_ml,
                        'away_ml_odds': away_ml
                    })
        
        # Find value using predictive model
        # Note: This requires team ID mapping which we don't have yet
        # For now, return a placeholder
        
        return {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "sports": sport_list,
            "games_analyzed": len(games),
            "value_bets_found": 0,
            "message": "Advanced picks require team ID mapping from ESPN. Use /api/stats/teams first.",
            "sample_games": games[:5] if games else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Backtesting Endpoints

@app.post("/api/backtest/run")
async def run_backtest(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    initial_bankroll: float = Query(1000.0, description="Starting bankroll"),
    kelly_fraction: float = Query(0.2, description="Kelly fraction (0.2 = 20%)")
):
    """
    Run backtest simulation over historical data.
    Returns performance metrics and validates model effectiveness.
    """
    try:
        result = backtester.run_backtest(start_date, end_date, initial_bankroll, kelly_fraction)
        
        if not result:
            return {
                "success": False,
                "message": "No bets found for the specified date range. Need historical data."
            }
        
        return {
            "success": True,
            "period": f"{start_date} to {end_date}",
            "summary": {
                "total_bets": result.total_bets,
                "win_rate": round(result.win_rate * 100, 1),
                "profit": round(result.profit, 2),
                "roi": round(result.roi, 2),
                "max_drawdown": round(result.max_drawdown * 100, 1),
                "sharpe_ratio": round(result.sharpe_ratio, 2)
            },
            "by_bet_type": {
                "moneyline": result.ml_results,
                "spread": result.spread_results,
                "totals": result.total_results
            },
            "by_sport": result.sport_results,
            "assessment": "EXCELLENT" if result.roi > 5 else "GOOD" if result.roi > 2 else "MARGINAL" if result.roi > 0 else "POOR"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/report")
async def get_backtest_report():
    """Get detailed backtest report."""
    try:
        # Run backtest for last 6 months
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        
        result = backtester.run_backtest(start_date, end_date)
        
        if result:
            backtester.print_backtest_report(result)
            return {
                "success": True,
                "report_generated": True,
                "period": f"{start_date} to {end_date}",
                "summary": {
                    "total_bets": result.total_bets,
                    "win_rate": f"{result.win_rate:.1%}",
                    "profit": f"${result.profit:,.2f}",
                    "roi": f"{result.roi:.2f}%",
                    "max_drawdown": f"{result.max_drawdown:.1%}"
                }
            }
        else:
            return {
                "success": False,
                "message": "No historical data available for backtest"
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


# Paper Trading Endpoints

@app.post("/api/paper-trading/enable")
async def enable_paper_trading(
    starting_bankroll: float = Query(10000.0, description="Starting virtual bankroll"),
    kelly_fraction: float = Query(0.2, description="Kelly fraction (0.2 = 20%)")
):
    """Enable automatic paper trading with virtual money."""
    try:
        auto_trader.update_settings(
            enabled=True,
            starting_bankroll=starting_bankroll,
            current_bankroll=starting_bankroll,
            kelly_fraction=kelly_fraction
        )
        
        return {
            "success": True,
            "message": "Paper trading enabled",
            "starting_bankroll": starting_bankroll,
            "kelly_fraction": kelly_fraction,
            "status": "When you generate picks, virtual bets will be created automatically"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/paper-trading/disable")
async def disable_paper_trading():
    """Disable automatic paper trading."""
    try:
        auto_trader.update_settings(enabled=False)
        
        return {
            "success": True,
            "message": "Paper trading disabled",
            "status": "Automatic bet creation is now off"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/status")
async def get_paper_trading_status():
    """Get paper trading status and current performance."""
    try:
        settings = auto_trader.get_settings()
        performance = auto_trader.get_performance_summary()
        
        return {
            "enabled": settings.enabled,
            "settings": {
                "starting_bankroll": settings.starting_bankroll,
                "kelly_fraction": settings.kelly_fraction,
                "min_ev": settings.min_ev,
                "max_daily_bets": settings.max_daily_bets
            },
            "performance": performance,
            "note": "Paper trading tracks virtual bets automatically when you generate picks"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/bets")
async def get_paper_bets(
    limit: int = Query(50, description="Number of bets to return"),
    status: Optional[str] = Query(None, description="Filter by status: pending, win, loss, push")
):
    """Get all paper bets history."""
    try:
        # Get all bets first
        bets = auto_trader.get_all_bets(limit)
        
        # Filter by status if requested
        if status:
            bets = [b for b in bets if b.result == status]
        
        return {
            "total_bets": len(bets),
            "bets": [
                {
                    "id": bet.id,
                    "bet_id": bet.bet_id,
                    "date": bet.date,
                    "sport": bet.sport,
                    "event": bet.event,
                    "selection": bet.selection,
                    "bet_type": bet.bet_type,
                    "odds": bet.odds,
                    "stake": bet.stake,
                    "model_probability": bet.model_probability,
                    "ev_pct": bet.ev_pct,
                    "result": bet.result,
                    "profit": bet.profit,
                    "created_at": bet.created_at.isoformat() if bet.created_at else None,
                    "settled_at": bet.settled_at.isoformat() if bet.settled_at else None
                }
                for bet in bets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/performance")
async def get_paper_trading_performance(
    days: int = Query(30, description="Days of history to include")
):
    """Get detailed paper trading performance metrics."""
    try:
        summary = auto_trader.get_performance_summary()
        daily = auto_trader.get_daily_performance(days)
        
        return {
            "summary": summary,
            "daily_performance": daily,
            "assessment": _assess_performance(summary['roi'], summary['win_rate'])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _assess_performance(roi: float, win_rate: float) -> str:
    """Assess paper trading performance."""
    if roi > 5:
        return "EXCELLENT: World-class performance (>5% ROI)"
    elif roi > 2:
        return "GOOD: Profitable long-term (>2% ROI)"
    elif roi > 0:
        return "MARGINAL: Positive but high variance (0-2% ROI)"
    elif roi == 0:
        return "BREAK-EVEN: No profit or loss"
    else:
        return "POOR: Losing money - model needs improvement"


@app.post("/api/paper-trading/reset")
async def reset_paper_trading(
    new_bankroll: float = Query(10000.0, description="New starting bankroll")
):
    """Reset paper trading - clears all bets and resets bankroll."""
    try:
        success = auto_trader.reset_paper_trading(new_bankroll)
        
        if success:
            return {
                "success": True,
                "message": f"Paper trading reset with ${new_bankroll:,.2f} virtual bankroll",
                "new_bankroll": new_bankroll,
                "warning": "All previous bet history has been cleared"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reset paper trading")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/paper-trading/settle")
async def settle_paper_bet(
    bet_id: str = Query(..., description="Bet ID to settle"),
    result: str = Query(..., description="Result: win, loss, or push")
):
    """Manually settle a paper bet (for testing or when auto-settlement fails)."""
    try:
        if result not in ['win', 'loss', 'push']:
            raise HTTPException(status_code=400, detail="Result must be win, loss, or push")
        
        success = auto_trader.settle_bet(bet_id, result)
        
        if success:
            return {
                "success": True,
                "message": f"Bet {bet_id} settled as {result}",
                "bet_id": bet_id,
                "result": result
            }
        else:
            raise HTTPException(status_code=400, detail=f"Could not settle bet {bet_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/paper-trading/pending")
async def get_pending_paper_bets():
    """Get all pending paper bets that haven't been settled yet."""
    try:
        bets = auto_trader.get_pending_bets()
        
        return {
            "pending_count": len(bets),
            "bets": [
                {
                    "bet_id": bet.bet_id,
                    "date": bet.date,
                    "sport": bet.sport,
                    "event": bet.event,
                    "selection": bet.selection,
                    "odds": bet.odds,
                    "stake": bet.stake,
                    "created_at": bet.created_at.isoformat() if bet.created_at else None
                }
                for bet in bets
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    try:
        setup_static_files()
    except Exception as e:
        print(f"Warning: Could not setup static files: {e}")
    
    # Production startup: Log API key status (don't crash if fails)
    try:
        print("=" * 60)
        print("🏆 Sports Betting Model - Production Startup")
        print("=" * 60)
        stats = odds_manager.get_usage_stats()
        print(f"🔑 Odds API Key Configured: {stats['api_key_configured']}")
        if stats['api_key_configured']:
            key = os.getenv('ODDS_API_KEY', '')
            if key:
                print(f"   Key preview: {key[:4]}...{key[-4:]}")
        else:
            print("   ⚠️ WARNING: No API key found!")
            print("   → Set ODDS_API_KEY in Railway Variables:")
            print("     1. Go to railway.app → your project")
            print("     2. Click 'Variables' tab")
            print("     3. Add: ODDS_API_KEY = your_key_here")
            print("     4. Get free key: https://the-odds-api.com/")
            print("   → Without API key, model uses stale/demo data")
        print(f"📊 API Requests Today: {stats['requests_today']}/{stats['request_limit']}")
        print("✅ Startup complete - ready for real-time odds")
        print("=" * 60)
    except Exception as e:
        print(f"Warning: Startup logging failed: {e}")
        print("✅ App started (with warnings)")
