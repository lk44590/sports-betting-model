"""
Main entry point for the sports betting model.
Starts the API server and provides CLI commands.
"""

#!/usr/bin/env python3
import argparse
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))


def start_api_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Start the FastAPI server."""
    import uvicorn
    from api.main import app
    
    print(f"🚀 Starting Sports Betting Model API on http://{host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"📖 Alternative Docs: http://{host}:{port}/redoc")
    print("\nPress Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


def generate_daily_picks():
    """Generate today's picks."""
    from api.main import betting_model, fetcher
    from core.betting_model import create_candidate_from_dict
    from datetime import datetime
    
    print("🏆 Generating today's +EV picks...")
    print("=" * 60)
    
    # Active sports
    sports = ["NBA", "NHL", "MLB"]
    today_str = datetime.now().strftime('%Y%m%d')
    
    all_candidates = []
    for sport in sports:
        print(f"\n📊 Fetching {sport} games...")
        candidates = fetcher.create_candidates_from_espn(sport, today_str)
        print(f"   Found {len(candidates)} candidates")
        all_candidates.extend(candidates)
    
    # Evaluate
    print(f"\n🧠 Evaluating {len(all_candidates)} candidates...")
    evaluated = []
    for candidate_data in all_candidates:
        bet_candidate = create_candidate_from_dict(candidate_data)
        evaluated_candidate = betting_model.evaluate_candidate(bet_candidate)
        evaluated.append(evaluated_candidate)
    
    # Filter to qualified
    picks = betting_model.filter_and_rank_picks(evaluated)
    
    # Display results
    print(f"\n✅ {len(picks)} QUALIFIED PICKS:")
    print("=" * 60)
    
    total_stake = 0
    for i, pick in enumerate(picks, 1):
        total_stake += pick.stake
        print(f"\n{i}. {pick.sport}: {pick.event}")
        print(f"   Bet: {pick.bet_type} - {pick.selection}")
        print(f"   Odds: {pick.odds:+d} | True Prob: {pick.true_probability*100:.1f}%")
        print(f"   EV: +{pick.ev_pct:.1f}% | Edge Score: {pick.edge_score:.0f}")
        print(f"   💰 Recommended Stake: ${pick.stake:.2f} ({pick.stake_pct:.2f}%)")
        if pick.notes:
            print(f"   📝 {pick.notes}")
    
    print(f"\n{'=' * 60}")
    print(f"Total Exposure: ${total_stake:.2f}")
    print(f"Expected Value: +{sum(p.ev_pct for p in picks):.1f}% total edge")
    print(f"\n💾 Picks available at API: http://localhost:8000/api/picks/today")
    
    return picks


def show_performance():
    """Show current performance summary."""
    from data.db import db
    
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    summary = db.get_performance_summary()
    
    print(f"\nTotal Bets: {summary['total_bets']}")
    print(f"Settled: {summary['settled_bets']} | Open: {summary['open_bets']}")
    print(f"\nWins: {summary['wins']} | Losses: {summary['losses']} | Pushes: {summary['pushes']}")
    print(f"Win Rate: {summary['hit_rate_pct']:.1f}%")
    print(f"\nTotal Staked: ${summary['staked']:.2f}")
    print(f"Total Profit: ${summary['profit']:.2f}")
    print(f"ROI: {summary['roi_pct']:.2f}%")
    print(f"Avg EV: {summary['avg_ev_pct']:.2f}%")
    
    # By sport
    by_sport = db.get_performance_by_sport()
    if by_sport:
        print(f"\n📈 BY SPORT:")
        for sport_data in by_sport:
            print(f"  {sport_data['sport']}: {sport_data['roi_pct']:.1f}% ROI ({sport_data['bets']} bets)")


def init_database():
    """Initialize the database."""
    from data.db import db
    print("✅ Database initialized at:", db.db_path)


def main():
    parser = argparse.ArgumentParser(
        description="Sports Betting Model - World-Class +EV Detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py server              # Start API server
  python run.py server --port 8080  # Start on custom port
  python run.py picks               # Generate today's picks
  python run.py performance         # Show performance stats
  python run.py init                # Initialize database
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start API server')
    server_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    server_parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    server_parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    # Picks command
    picks_parser = subparsers.add_parser('picks', help='Generate daily picks')
    
    # Performance command
    perf_parser = subparsers.add_parser('performance', help='Show performance stats')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    
    args = parser.parse_args()
    
    if args.command == 'server':
        start_api_server(args.host, args.port, args.reload)
    elif args.command == 'picks':
        generate_daily_picks()
    elif args.command == 'performance':
        show_performance()
    elif args.command == 'init':
        init_database()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
