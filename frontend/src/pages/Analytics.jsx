import { useState, useEffect } from 'react'
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import { RefreshCw, TrendingUp, PieChart as PieChartIcon, Activity } from 'lucide-react'
import { performanceApi, betsApi } from '../api'

const COLORS = ['#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#8b5cf6']

function Analytics() {
  const [performance, setPerformance] = useState(null)
  const [bySport, setBySport] = useState([])
  const [history, setHistory] = useState([])
  const [betHistory, setBetHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  const fetchAnalytics = async () => {
    setLoading(true)
    try {
      const [perfRes, sportRes, histRes, betsRes] = await Promise.all([
        performanceApi.getSummary(),
        performanceApi.getBySport(),
        performanceApi.getBankrollHistory(days),
        betsApi.getBetHistory(days)
      ])

      setPerformance(perfRes.data)
      setBySport(sportRes.data.sports || [])
      setHistory(histRes.data.history || [])
      setBetHistory(betsRes.data.bets || [])
    } catch (err) {
      console.error('Analytics fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnalytics()
  }, [days])

  // Prepare chart data
  const sportChartData = bySport.map(s => ({
    name: s.sport,
    roi: s.roi_pct,
    bets: s.bets,
    profit: s.profit
  }))

  const bankrollData = history.map(h => ({
    date: h.date,
    bankroll: h.ending_bankroll,
    pnl: h.daily_pnl
  }))

  const winLossData = performance ? [
    { name: 'Wins', value: performance.wins, color: '#22c55e' },
    { name: 'Losses', value: performance.losses, color: '#ef4444' },
    { name: 'Pushes', value: performance.pushes, color: '#9ca3af' }
  ] : []

  if (loading && !performance) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Performance Analytics</h2>
        <div className="flex items-center gap-4">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border rounded-lg px-3 py-2"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="btn-secondary flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      {performance && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card">
            <p className="text-sm text-gray-600">Total Bets</p>
            <p className="text-2xl font-bold">{performance.total_bets}</p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-600">ROI</p>
            <p className={`text-2xl font-bold ${performance.roi_pct >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
              {performance.roi_pct}%
            </p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-600">Win Rate</p>
            <p className="text-2xl font-bold text-primary-600">{performance.hit_rate_pct}%</p>
          </div>
          <div className="card">
            <p className="text-sm text-gray-600">Avg EV</p>
            <p className="text-2xl font-bold text-primary-600">{performance.avg_ev_pct}%</p>
          </div>
        </div>
      )}

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Bankroll Chart */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-primary-600" />
            <h3 className="text-lg font-semibold">Bankroll Over Time</h3>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={bankrollData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                />
                <YAxis />
                <Tooltip 
                  formatter={(value) => `$${value.toFixed(2)}`}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <Line 
                  type="monotone" 
                  dataKey="bankroll" 
                  stroke="#3b82f6" 
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ROI by Sport */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <PieChartIcon className="w-5 h-5 text-primary-600" />
            <h3 className="text-lg font-semibold">ROI by Sport</h3>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sportChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip formatter={(value) => `${value}%`} />
                <Bar dataKey="roi" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Win/Loss Distribution */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-5 h-5 text-primary-600" />
            <h3 className="text-lg font-semibold">Win/Loss Distribution</h3>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={winLossData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {winLossData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sport Performance Table */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-primary-600" />
            <h3 className="text-lg font-semibold">Performance by Sport</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 text-sm font-medium text-gray-600">Sport</th>
                  <th className="text-right py-2 text-sm font-medium text-gray-600">Bets</th>
                  <th className="text-right py-2 text-sm font-medium text-gray-600">ROI</th>
                  <th className="text-right py-2 text-sm font-medium text-gray-600">Profit</th>
                </tr>
              </thead>
              <tbody>
                {bySport.map((sport) => (
                  <tr key={sport.sport} className="border-b">
                    <td className="py-2 font-medium">{sport.sport}</td>
                    <td className="py-2 text-right">{sport.bets}</td>
                    <td className={`py-2 text-right font-medium ${sport.roi_pct >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                      {sport.roi_pct}%
                    </td>
                    <td className={`py-2 text-right ${sport.profit >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                      ${sport.profit}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Recent Bet History */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">Recent Bet History</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 text-sm font-medium text-gray-600">Date</th>
                <th className="text-left py-2 text-sm font-medium text-gray-600">Sport</th>
                <th className="text-left py-2 text-sm font-medium text-gray-600">Event</th>
                <th className="text-left py-2 text-sm font-medium text-gray-600">Selection</th>
                <th className="text-right py-2 text-sm font-medium text-gray-600">Odds</th>
                <th className="text-right py-2 text-sm font-medium text-gray-600">Stake</th>
                <th className="text-center py-2 text-sm font-medium text-gray-600">Result</th>
                <th className="text-right py-2 text-sm font-medium text-gray-600">P/L</th>
              </tr>
            </thead>
            <tbody>
              {betHistory.slice(0, 10).map((bet) => (
                <tr key={bet.bet_id} className="border-b">
                  <td className="py-2 text-sm">{bet.date}</td>
                  <td className="py-2 text-sm">{bet.sport}</td>
                  <td className="py-2 text-sm">{bet.event}</td>
                  <td className="py-2 text-sm">{bet.selection}</td>
                  <td className="py-2 text-sm text-right">{bet.odds > 0 ? `+${bet.odds}` : bet.odds}</td>
                  <td className="py-2 text-sm text-right">${bet.stake}</td>
                  <td className="py-2 text-center">
                    <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                      bet.result === 'win' ? 'bg-success-100 text-success-800' :
                      bet.result === 'loss' ? 'bg-danger-100 text-danger-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {bet.result?.toUpperCase()}
                    </span>
                  </td>
                  <td className={`py-2 text-right font-medium ${
                    (bet.profit || 0) >= 0 ? 'text-success-600' : 'text-danger-600'
                  }`}>
                    {bet.profit > 0 ? '+' : ''}${bet.profit?.toFixed(2) || '0.00'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default Analytics
