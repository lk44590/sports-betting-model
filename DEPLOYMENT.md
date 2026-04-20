# 🚀 Deployment Guide - Sports Betting Model

## Quick Start (5 Minutes)

### 1. Get The Odds API Key (FREE)
```
1. Go to https://the-odds-api.com/
2. Click "Get API Key"
3. Sign up (free tier = 500 requests/month)
4. Copy your API key (32-character string)
```

### 2. Deploy to Railway
```
1. Go to https://railway.app/
2. Select your project
3. Go to Deployments tab
4. Click "Redeploy" (or it auto-deploys on git push)
```

### 3. Set Environment Variable
```
1. In Railway, go to your project → Variables tab
2. Click "New Variable"
3. Name: ODDS_API_KEY
4. Value: your_32_character_api_key_here
5. Click "Add"
6. Redeploy the service
```

### 4. Verify It Works
```
Visit: https://sports-betting-model-production-98fe.up.railway.app/api/picks/today

Expected: JSON with today's picks (or "No upcoming games")
```

---

## 📊 What Happens After Deploy

### Automatic Features (No Setup Required)
- ✅ Paper trading tracks all picks automatically
- ✅ EV calculations run on every pick
- ✅ Kelly stake sizing calculated
- ✅ Performance metrics tracked

### First Time Setup
1. Visit the dashboard
2. Set your bankroll in Settings
3. Generate first picks
4. Monitor paper trading for 1-2 weeks
5. Start real betting when confident

---

## 🔧 Troubleshooting

### "No API key found" in logs
```
Fix: Set ODDS_API_KEY in Railway Variables (see step 3 above)
Without API key: Model uses demo/stale data only
```

### Dashboard shows 500 error
```
Check: Railway logs for specific error
Common: Database initialization (should be fixed)
Fix: Redeploy the service
```

### No picks showing
```
Check: /api/picks/today endpoint directly
If empty: No games scheduled or API key issue
If error: Check Railway logs
```

---

## 📈 Next Steps After Deploy

### Week 1: Paper Trading
- Generate picks daily
- Watch paper trading performance
- Track calibration metrics

### Week 2: Analysis
- Check Brier score (should be <0.20)
- Review EV bucket performance
- Adjust bankroll/settings if needed

### Week 3: Go Live
- Start with 25% of normal stakes
- Monitor daily results
- Scale up gradually

---

## 🎯 Success Metrics

You're profitable when:
- ✅ Win rate > 52% on -110 odds
- ✅ Monthly ROI > 5%
- ✅ Brier score < 0.20 (well-calibrated)
- ✅ Positive CLV on 60%+ of bets

---

## 🆘 Support

Issues? Check:
1. Railway logs (Deployment → View Logs)
2. Browser console for frontend errors
3. API endpoints directly (/api/picks/today)

---

**Ready to deploy? Start with Step 1: Get your API key!**
