import { useState, useEffect } from 'react'
import { RefreshCw, Target, DollarSign, TrendingUp, Activity } from 'lucide-react'
import { picksApi, performanceApi, betsApi } from '../api'
import StatsCard from '../components/StatsCard'
import PickCard from '../components/PickCard'

function Dashboard() {
  const [picks, setPicks] = useState([])
  const [performance, setPerformance] = useState(null)
  const [bankroll, setBankroll] = useState(null)
  const [openBets, setOpenBets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    
    try {
      // Fetch all data in parallel
      const [picksRes, perfRes, bankRes, openRes] = await Promise.all([
        picksApi.getTodaysPicks(),
        performanceApi.getSummary(),
        performanceApi.getBankrollStatus(),
        betsApi.getOpenBets()
      ])

      setPicks(picksRes.data.picks || [])
      setPerformance(perfRes.data)
      setBankroll(bankRes.data)
      setOpenBets(openRes.data.bets || [])
      setLastUpdated(new Date())
    } catch (err) {
      setError('Failed to load data. Make sure the API server is running.')
      console.error('Dashboard fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const handlePlaceBet = async (pick) => {
    try {
      const betData = {
        bet_id: pick.bet_id,
        sport: pick.sport,
        event: pick.event,
        event_id: pick.event_id || pick.bet_id,
        market_type: 'moneyline',
        bet_type: pick.bet_type || 'moneyline',
        selection: pick.selection,
        odds: pick.odds,
        true_probability: pick.true_probability / 100,
        ev_pct: pick.ev_pct,
        edge_score: pick.edge_score,
        stake: pick.stake,
        stake_pct: pick.stake_pct
      }

      await betsApi.placeBet(betData)
      alert(`Bet recorded: ${pick.selection} @ ${pick.odds}`)
      fetchData() // Refresh open bets
    } catch (err) {
      alert('Failed to place bet: ' + (err.response?.data?.detail || err.message))
    }
  }

  if (loading && !performance) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-primary-600" />
        <span className="ml-3 text-gray-600">Loading data...</span>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Today's +EV Picks</h2>
          {lastUpdated && (
            <p className="text-sm text-gray-500">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-danger-50 border border-danger-200 text-danger-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Stats Cards */}
      {performance && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="Total ROI"
            value={`${performance.roi_pct}%`}
            subtitle={`${performance.settled_bets} bets`}
            trend={performance.roi_pct > 0 ? 'up' : performance.roi_pct < 0 ? 'down' : 'neutral'}
          />
          <StatsCard
            title="Win Rate"
            value={`${performance.hit_rate_pct}%`}
            subtitle={`${performance.wins}W - ${performance.losses}L - ${performance.pushes}P`}
            trend={performance.hit_rate_pct > 52 ? 'up' : 'down'}
          />
          <StatsCard
            title="Profit/Loss"
            value={`$${performance.profit}`}
            subtitle={`$${performance.staked} staked`}
            trend={performance.profit > 0 ? 'up' : performance.profit < 0 ? 'down' : 'neutral'}
          />
          <StatsCard
            title="Open Bets"
            value={performance.open_bets}
            subtitle="Pending settlement"
            trend="neutral"
          />
        </div>
      )}

      {/* Bankroll Status */}
      {bankroll && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign className="w-5 h-5 text-primary-600" />
            <h3 className="text-lg font-semibold">Bankroll Status</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-600">Current</p>
              <p className="text-xl font-bold text-gray-900">${bankroll.current_bankroll}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Peak</p>
              <p className="text-xl font-bold text-success-600">${bankroll.peak_bankroll}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Return</p>
              <p className={`text-xl font-bold ${bankroll.total_return >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                {bankroll.total_return >= 0 ? '+' : ''}${bankroll.total_return}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Drawdown</p>
              <p className="text-xl font-bold text-gray-900">{bankroll.current_drawdown_pct}%</p>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Picks Column */}
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-5 h-5 text-primary-600" />
            <h3 className="text-lg font-semibold">
              Qualified Picks ({picks.length})
            </h3>
          </div>

          {picks.length === 0 ? (
            <div className="card text-center py-12">
              <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No qualified picks found for today.</p>
              <p className="text-sm text-gray-500 mt-2">
                The model is selective. Check back later or refresh.
              </p>
            </div>
          ) : (
            <div>
              {picks.map((pick) => (
                <PickCard
                  key={pick.bet_id}
                  pick={pick}
                  onPlaceBet={handlePlaceBet}
                />
              ))}
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Open Bets */}
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-primary-600" />
              <h3 className="text-lg font-semibold">Open Bets ({openBets.length})</h3>
            </div>
            
            {openBets.length === 0 ? (
              <p className="text-sm text-gray-500">No open bets</p>
            ) : (
              <div className="space-y-3">
                {openBets.map((bet) => (
                  <div key={bet.bet_id} className="border rounded p-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{bet.selection}</span>
                      <span className="text-sm font-bold">{bet.odds > 0 ? `+${bet.odds}` : bet.odds}</span>
                    </div>
                    <p className="text-xs text-gray-500">{bet.event}</p>
                    <p className="text-xs text-gray-600">Stake: ${bet.stake}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Model Thresholds */}
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp className="w-5 h-5 text-primary-600" />
              <h3 className="text-lg font-semibold">Model Thresholds</h3>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Min EV:</span>
                <span className="font-medium">7%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Kelly Fraction:</span>
                <span className="font-medium">20%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Max Stake:</span>
                <span className="font-medium">3.5%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Min Edge Score:</span>
                <span className="font-medium">70</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
