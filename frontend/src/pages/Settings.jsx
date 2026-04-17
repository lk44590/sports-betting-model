import { useState, useEffect } from 'react'
import { Save, RefreshCw, DollarSign, Settings as SettingsIcon } from 'lucide-react'
import { modelApi } from '../api'

function Settings() {
  const [config, setConfig] = useState(null)
  const [bankroll, setBankroll] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      const res = await modelApi.getConfig()
      setConfig(res.data)
      setBankroll(res.data.bankroll?.current_bankroll?.toString() || '1000')
    } catch (err) {
      console.error('Failed to load config:', err)
    }
  }

  const handleUpdateBankroll = async () => {
    setLoading(true)
    setMessage(null)
    
    try {
      const newBankroll = parseFloat(bankroll)
      if (isNaN(newBankroll) || newBankroll <= 0) {
        setMessage({ type: 'error', text: 'Please enter a valid bankroll amount' })
        return
      }

      await modelApi.updateBankroll(newBankroll)
      setMessage({ type: 'success', text: 'Bankroll updated successfully' })
      fetchConfig()
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to update bankroll' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <h2 className="text-2xl font-bold text-gray-900">Settings</h2>

      {message && (
        <div className={`px-4 py-3 rounded-lg ${
          message.type === 'success' ? 'bg-success-100 text-success-700' : 'bg-danger-100 text-danger-700'
        }`}>
          {message.text}
        </div>
      )}

      {/* Bankroll Settings */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <DollarSign className="w-5 h-5 text-primary-600" />
          <h3 className="text-lg font-semibold">Bankroll Management</h3>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Current Bankroll
            </label>
            <div className="flex gap-2">
              <input
                type="number"
                value={bankroll}
                onChange={(e) => setBankroll(e.target.value)}
                className="flex-1 border rounded-lg px-3 py-2"
                placeholder="1000.00"
                step="0.01"
              />
              <button
                onClick={handleUpdateBankroll}
                disabled={loading}
                className="btn-primary flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Update
              </button>
            </div>
            <p className="text-sm text-gray-500 mt-1">
              This updates your current bankroll for Kelly calculations
            </p>
          </div>

          {config?.bankroll && (
            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
              <div>
                <p className="text-sm text-gray-600">Initial Bankroll</p>
                <p className="font-semibold">${config.bankroll.initial_bankroll}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Peak Bankroll</p>
                <p className="font-semibold text-success-600">${config.bankroll.peak_bankroll}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Return</p>
                <p className={`font-semibold ${config.bankroll.total_return >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                  {config.bankroll.total_return >= 0 ? '+' : ''}${config.bankroll.total_return}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">ROI</p>
                <p className={`font-semibold ${config.bankroll.roi_pct >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                  {config.bankroll.roi_pct}%
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Model Thresholds */}
      {config?.thresholds && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <SettingsIcon className="w-5 h-5 text-primary-600" />
            <h3 className="text-lg font-semibold">Model Thresholds</h3>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">Minimum EV</p>
              <p className="font-semibold text-lg">{config.thresholds.min_ev_pct}%</p>
              <p className="text-xs text-gray-500">Only bets with EV above this threshold</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">Min Edge Score</p>
              <p className="font-semibold text-lg">{config.thresholds.min_edge_score}</p>
              <p className="text-xs text-gray-500">Composite quality threshold</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">Kelly Fraction</p>
              <p className="font-semibold text-lg">20%</p>
              <p className="text-xs text-gray-500">Conservative fractional Kelly</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">Max Stake</p>
              <p className="font-semibold text-lg">3.5%</p>
              <p className="text-xs text-gray-500">Per-bet maximum exposure</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">Min Probability</p>
              <p className="font-semibold text-lg">{config.thresholds.min_true_probability}%</p>
              <p className="text-xs text-gray-500">Minimum win probability</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">Min Quality</p>
              <p className="font-semibold text-lg">{config.thresholds.min_quality}</p>
              <p className="text-xs text-gray-500">Data quality threshold</p>
            </div>
          </div>
        </div>
      )}

      {/* About */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">About</h3>
        <div className="space-y-2 text-sm text-gray-600">
          <p><strong>Version:</strong> 1.0.0</p>
          <p><strong>Model:</strong> World-class +EV betting with Kelly Criterion</p>
          <p><strong>Features:</strong></p>
          <ul className="list-disc list-inside ml-4 space-y-1">
            <li>Bayesian probability calibration</li>
            <li>20% fractional Kelly Criterion</li>
            <li>7% minimum EV threshold</li>
            <li>Sport-specific probability caps</li>
            <li>Drawdown protection</li>
            <li>Simultaneous Kelly for multiple bets</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default Settings
