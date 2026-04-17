# World-Class Sports Betting Model

A sophisticated +EV (positive expected value) betting model with Kelly Criterion stake sizing, real-time data feeds, and a modern web dashboard.

## Features

### Core Betting Engine
- **Strict +EV Detection**: 7% minimum EV threshold with Bayesian probability calibration
- **Kelly Criterion**: 20% fractional Kelly with simultaneous bet adjustment
- **Bankroll Management**: Drawdown protection and dynamic stake sizing
- **Sport-Specific Caps**: Realistic probability limits by sport

### Data Sources (Free APIs)
- **ESPN API**: Live schedules, scores, and team stats (unlimited, no key needed)
- **The Odds API**: Live odds comparison (500 requests/month free tier)

### Web Dashboard
- **Today's Picks**: +EV opportunities with recommended stakes
- **Performance Tracking**: ROI, win rate, profit/loss analytics
- **Bankroll Charts**: Visual tracking of growth and drawdowns
- **Sport Breakdown**: Performance by sport and market type

## Quick Start

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### 2. Start the Backend API

```bash
# Option 1: Using the run script
python run.py server

# Option 2: Direct with uvicorn
uvicorn backend.api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

### 3. Start the Frontend

```bash
cd frontend
npm run dev
```

The dashboard will be available at `http://localhost:3000`

## Usage

### Generate Daily Picks (CLI)

```bash
python run.py picks
```

This fetches today's games from ESPN and evaluates them for +EV opportunities.

### View Performance (CLI)

```bash
python run.py performance
```

Shows current ROI, win rate, and profit/loss summary.

### Using the Web Dashboard

1. **Today's Picks**: View all +EV opportunities with Kelly-recommended stakes
2. **Place Bets**: Click "Place Bet" to track bets in the system
3. **Analytics**: View charts and performance breakdowns
4. **Settings**: Update bankroll and view model thresholds

### API Endpoints

#### Picks
- `GET /api/picks/today` - Get today's +EV picks
- `POST /api/model/evaluate` - Evaluate a single bet
- `POST /api/model/evaluate-batch` - Evaluate multiple bets

#### Bets
- `POST /api/bets/place` - Record a placed bet
- `POST /api/bets/settle` - Settle a bet with result
- `GET /api/bets/open` - Get unsettled bets
- `GET /api/bets/history` - Get bet history

#### Performance
- `GET /api/performance/summary` - Overall performance stats
- `GET /api/performance/by-sport` - Breakdown by sport
- `GET /api/bankroll/status` - Current bankroll status
- `GET /api/bankroll/history` - Bankroll over time

## Model Configuration

### Default Thresholds
- **Minimum EV**: 7%
- **Minimum Edge Score**: 70
- **Kelly Fraction**: 20% (conservative)
- **Max Stake**: 3.5% of bankroll per bet
- **Max Daily Risk**: 15% total exposure

### Sport-Specific Probability Caps
- MLB/NCAABASE: 30-70% moneyline, 25-75% totals
- NBA/WNBA/NCAAMB: 32-68% moneyline, 28-72% spreads
- NFL/NCAAF: 35-65% moneyline, 30-70% spreads
- NHL: 30-70% moneyline, 28-72% puck line

## Project Structure

```
sports-betting-model/
├── backend/
│   ├── api/
│   │   ├── main.py              # FastAPI application
│   │   └── routes/
│   ├── core/
│   │   ├── betting_model.py     # Core +EV model
│   │   ├── ev_calculator.py     # EV and probability math
│   │   └── kelly.py             # Kelly Criterion
│   ├── data/
│   │   ├── db.py                # SQLite database
│   │   └── fetcher.py           # ESPN/Odds API
│   ├── ml/
│   │   └── (neural nets, NLP coming in Phase 2)
│   └── tracking/
│       └── performance.py       # Analytics
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── pages/              # Dashboard, Analytics, Settings
│   │   ├── api.js              # API client
│   │   └── App.jsx             # Main app
│   └── package.json
├── data/                       # SQLite DB and cache
├── run.py                      # CLI entry point
└── requirements.txt
```

## Database

The model uses SQLite for tracking:
- `bets` - All placed bets with results
- `performance_by_sport` - Aggregated stats by sport
- `performance_by_market` - Aggregated stats by market type
- `bankroll_history` - Daily bankroll snapshots
- `api_usage` - API call tracking for rate limits

Database location: `data/betting.db`

## Kelly Criterion Explained

The model uses the Kelly Criterion for optimal bet sizing:

```
Full Kelly = (bp - q) / b
Fractional Kelly = Full Kelly × 0.20
```

Where:
- `b` = profit multiple (decimal odds - 1)
- `p` = true probability of winning
- `q` = 1 - p (probability of losing)

We use 20% fractional Kelly for safety, with additional adjustments for:
- Sample size confidence
- Data quality
- Current drawdown status

## Expected Value (EV)

Bets are qualified when:
```
EV% = (True Probability × Profit Multiple) - (1 - True Probability) × 100 > 7%
```

The model also applies uncertainty buffers for:
- Data quality penalties
- Sample size penalties
- Early season adjustments

## API Rate Limits

### ESPN API
- Unlimited requests
- 60-second cache for scores
- 1-hour cache for schedules

### The Odds API (Free Tier)
- 500 requests/month
- 15-minute cache for odds
- Prioritized for high-EV opportunities

## Future Enhancements (Phase 2)

- [ ] Neural network ensemble (TensorFlow)
- [ ] NLP sentiment analysis for injuries/news
- [ ] Automated daily runs with email notifications
- [ ] Player prop modeling
- [ ] Live betting (in-game) opportunities
- [ ] Parlay +EV detection
- [ ] Arbitrage detection across sportsbooks

## Disclaimer

This model is for educational and entertainment purposes. Sports betting involves risk. Never bet more than you can afford to lose. The model's past performance does not guarantee future results.

## License

MIT License - Feel free to use and modify as needed.

## Support

For issues or questions:
1. Check API status: `http://localhost:8000/api/data/stats`
2. Verify database: `python run.py init`
3. Review logs in console output
