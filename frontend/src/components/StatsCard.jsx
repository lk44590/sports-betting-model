import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

function StatsCard({ title, value, subtitle, trend, trendValue }) {
  const getTrendIcon = () => {
    if (trend === 'up') return <TrendingUp className="w-5 h-5 text-success-600" />
    if (trend === 'down') return <TrendingDown className="w-5 h-5 text-danger-600" />
    return <Minus className="w-5 h-5 text-gray-400" />
  }

  const getTrendColor = () => {
    if (trend === 'up') return 'text-success-600'
    if (trend === 'down') return 'text-danger-600'
    return 'text-gray-600'
  }

  const getBorderColor = () => {
    if (trend === 'up') return 'border-success-500'
    if (trend === 'down') return 'border-danger-500'
    return 'border-gray-300'
  }

  return (
    <div className={`stat-card ${getBorderColor()}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-1">
          {getTrendIcon()}
          {trendValue && (
            <span className={`text-sm font-medium ${getTrendColor()}`}>
              {trendValue}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default StatsCard
