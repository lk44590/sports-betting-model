import { CheckCircle, XCircle, AlertCircle, TrendingUp, DollarSign } from 'lucide-react'

function PickCard({ pick, onPlaceBet }) {
  const getConfidenceColor = (score) => {
    if (score >= 80) return 'bg-success-100 border-success-500 text-success-800'
    if (score >= 70) return 'bg-primary-100 border-primary-500 text-primary-800'
    return 'bg-yellow-100 border-yellow-500 text-yellow-800'
  }

  const getEVColor = (ev) => {
    if (ev >= 10) return 'text-success-600'
    if (ev >= 7) return 'text-primary-600'
    return 'text-yellow-600'
  }

  return (
    <div className={`rounded-lg border-2 p-4 mb-4 ${getConfidenceColor(pick.edge_score)}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase tracking-wide text-gray-500">
              {pick.sport}
            </span>
            {pick.qualified ? (
              <CheckCircle className="w-4 h-4 text-success-600" />
            ) : (
              <AlertCircle className="w-4 h-4 text-yellow-600" />
            )}
          </div>
          <h3 className="font-bold text-gray-900">{pick.event}</h3>
          <p className="text-sm text-gray-700 mt-1">
            {pick.bet_type || 'Moneyline'}: <span className="font-semibold">{pick.selection}</span>
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-gray-900">
            {pick.odds > 0 ? `+${pick.odds}` : pick.odds}
          </div>
          <div className={`text-sm font-semibold ${getEVColor(pick.ev_pct)}`}>
            +{pick.ev_pct}% EV
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-3">
        <div className="text-center p-2 bg-white bg-opacity-50 rounded">
          <p className="text-xs text-gray-600">True Prob</p>
          <p className="font-semibold text-gray-900">{pick.true_probability}%</p>
        </div>
        <div className="text-center p-2 bg-white bg-opacity-50 rounded">
          <p className="text-xs text-gray-600">Edge Score</p>
          <p className="font-semibold text-gray-900">{pick.edge_score}</p>
        </div>
        <div className="text-center p-2 bg-white bg-opacity-50 rounded">
          <p className="text-xs text-gray-600">Comp. Score</p>
          <p className="font-semibold text-gray-900">{pick.composite_score}</p>
        </div>
      </div>

      <div className="flex items-center justify-between bg-white bg-opacity-70 rounded p-3">
        <div className="flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-gray-600" />
          <div>
            <p className="text-xs text-gray-600">Kelly Stake</p>
            <p className="font-bold text-gray-900">${pick.stake} ({pick.stake_pct}%)</p>
          </div>
        </div>
        <button
          onClick={() => onPlaceBet && onPlaceBet(pick)}
          className="btn-primary text-sm"
          disabled={!pick.qualified}
        >
          Place Bet
        </button>
      </div>

      {pick.max_odds !== 0 && (
        <p className="text-xs text-gray-600 mt-2">
          Max acceptable odds: {pick.max_odds > 0 ? `+${pick.max_odds}` : pick.max_odds}
        </p>
      )}

      {pick.notes && (
        <p className="text-xs text-gray-500 mt-2 italic">{pick.notes}</p>
      )}
    </div>
  )
}

export default PickCard
