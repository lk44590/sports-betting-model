# Quick Start Guide

Get the Sports Betting Model running in 5 minutes.

## Step 1: Install Python Dependencies

```bash
# Navigate to project
cd sports-betting-model

# Install Python packages
pip install fastapi uvicorn sqlalchemy pandas numpy scikit-learn scipy requests aiohttp python-dotenv pyyaml
```

For the complete install:
```bash
pip install -r requirements.txt
```

## Step 2: Initialize Database

```bash
python run.py init
```

This creates the SQLite database at `data/betting.db`

## Step 3: Start Backend

```bash
python run.py server
```

Or directly with uvicorn:
```bash
uvicorn backend.api.main:app --reload --port 8000
```

Verify it's running:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

## Step 4: Install & Start Frontend

Open a new terminal:

```bash
cd sports-betting-model/frontend

# Install Node dependencies
npm install

# Start dev server
npm run dev
```

Dashboard: http://localhost:3000

## Step 5: Test the System

### Test 1: Generate Picks (CLI)
```bash
python run.py picks
```

You should see today's games evaluated for +EV opportunities.

### Test 2: View Dashboard
Open http://localhost:3000 and you should see:
- Performance summary cards
- Today's picks (if any games meet the 7% EV threshold)
- Bankroll status
- Open bets panel

### Test 3: API Test
```bash
# Get today's picks
curl http://localhost:8000/api/picks/today

# Get performance summary
curl http://localhost:8000/api/performance/summary
```

## Common Issues

### "Module not found" errors
Make sure you're in the right directory:
```bash
cd sports-betting-model
python run.py server
```

### Port already in use
Change ports:
```bash
# Backend on different port
python run.py server --port 8080

# Frontend - edit vite.config.js and change port
```

### Database locked
SQLite can only handle one writer at a time. Close other connections.

### No picks showing
The model is selective with a 7% EV threshold. Either:
1. Wait for better opportunities
2. Temporarily lower threshold in backend/core/betting_model.py
3. Test with sample data via the evaluate endpoint

## Next Steps

1. **Set your bankroll** in Settings page
2. **Review model thresholds** - understand the 7% EV requirement
3. **Track bets** - use "Place Bet" button on picks
4. **Settle bets** - mark results to track ROI
5. **Review analytics** - check performance charts weekly

## Optional: The Odds API Key

For better odds data (500 free requests/month):
1. Sign up at https://the-odds-api.com/
2. Get free API key
3. Set environment variable:
   ```bash
   export ODDS_API_KEY=your_key_here
   ```
4. Or edit `backend/data/fetcher.py` and add key

Without the key, the model uses ESPN odds (more limited).

## Stopping the Servers

- Backend: Press `Ctrl+C` in terminal
- Frontend: Press `Ctrl+C` in terminal

That's it! You're ready to find +EV betting opportunities.
