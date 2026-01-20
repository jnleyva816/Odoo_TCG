/**
 * Portfolio Dashboard Page - "Wall Street" style analytics
 *
 * Features:
 * - Portfolio value with 24h/7d/30d changes
 * - Value over time chart
 * - Top Movers widget (gainers/losers)
 */

import { useEffect, useState } from 'react'
import { useFeatures } from '../contexts/FeaturesContext'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { TrendingUp, TrendingDown, RefreshCw, Calendar, AlertCircle } from 'lucide-react'
import { apiClient } from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { PageTransition } from '../components/ui/PageTransition'
import { motion } from 'framer-motion'

// Helper to fetch with auth
const fetchWithAuth = async (url: string) => {
  const res = await apiClient.authFetch(url)
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`)
  }
  return res.json()
}

interface PortfolioSummary {
  total_cards: number
  total_unique_cards: number
  total_value: string
  total_cost_basis: string
  unrealized_profit: string
  change_24h: string
  change_24h_percent: number
  change_7d: string
  change_7d_percent: number
  change_30d: string
  change_30d_percent: number
  calculated_at: string
}

interface TopMover {
  product_id: number
  name: string
  sku: string
  set_name: string
  image_url: string | null
  current_price: string
  price_change_24h: string
  percent_change_24h: number
  quantity_owned: number
  direction: 'up' | 'down'
}

interface PortfolioStats {
  summary: PortfolioSummary
  top_gainers: TopMover[]
  top_losers: TopMover[]
}

interface ValueHistoryPoint {
  date: string
  value: number
}

interface TopValuedCard {
  product_id: number
  name: string
  sku: string
  set_name: string
  price: number
  quantity: number
  total_value: number
}

export default function PortfolioDashboardPage() {
  const { features } = useFeatures()
  const [stats, setStats] = useState<PortfolioStats | null>(null)
  const [history, setHistory] = useState<ValueHistoryPoint[]>([])
  const [topCards, setTopCards] = useState<TopValuedCard[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [historyDays, setHistoryDays] = useState(30)

  const fetchData = async () => {
    try {
      setError(null)

      // Fetch stats and top cards first (fast)
      const [statsResponse, topCardsResponse] = await Promise.all([
        fetchWithAuth('/api/portfolio/stats'),
        fetchWithAuth('/api/portfolio/top-cards?limit=10'),
      ])

      setStats(statsResponse)
      setTopCards(topCardsResponse)

      // Fetch history separately (can be slow/fail without breaking page)
      try {
        const historyResponse = await fetchWithAuth(`/api/portfolio/history?days=${historyDays}`)
        setHistory(historyResponse)
      } catch {
        // History not available - that's okay
        setHistory([])
      }
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to load portfolio'
      setError(errorMessage)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    if (features.portfolio_dashboard) {
      fetchData()
    }
  }, [features.portfolio_dashboard, historyDays])

  const handleRefresh = async () => {
    setRefreshing(true)
    await fetchData()
  }

  if (!features.portfolio_dashboard) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-white mb-2">Portfolio Dashboard</h1>
          <p className="text-neutral-400">
            This feature is not enabled. Enable it in settings to track your
            collection value over time.
          </p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-4 border-red-500 border-t-transparent"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-red-500 mb-2">Error</h1>
          <p className="text-neutral-400 mb-4">{error}</p>
          <Button
            onClick={handleRefresh}
            variant="primary"
          >
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  const summary = stats?.summary
  const totalValue = parseFloat(summary?.total_value || '0')
  const change24h = parseFloat(summary?.change_24h || '0')
  const isPositive24h = change24h >= 0

  // Format currency
  const formatCurrency = (value: number | string) => {
    const num = typeof value === 'string' ? parseFloat(value) : value
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(num)
  }

  // Calculate min/max for chart
  const values = history.map((h) => h.value)
  const minValue = Math.min(...values) * 0.95
  const maxValue = Math.max(...values) * 1.05

  return (
    <PageTransition className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-white tracking-tight">
            Portfolio Dashboard
          </h1>
          <p className="text-neutral-400 mt-1">
            Track your collection value like a stock portfolio
          </p>
        </div>
        <Button
          onClick={handleRefresh}
          disabled={refreshing}
          isLoading={refreshing}
          variant="secondary"
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Refresh
        </Button>
      </div>

      {/* Portfolio Value Hero Card */}
      <Card variant="elevated" className="bg-gradient-to-br from-neutral-900 to-neutral-950 border-neutral-800">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div>
            <p className="text-neutral-400 text-sm uppercase tracking-widest font-medium">
              Total Portfolio Value
            </p>
            <p className="text-5xl font-display font-black text-white mt-2 tracking-tight">
              {formatCurrency(totalValue)}
            </p>
            <div className="flex items-center gap-2 mt-3">
              {isPositive24h ? (
                <TrendingUp className="w-5 h-5 text-accent-500" />
              ) : (
                <TrendingDown className="w-5 h-5 text-red-500" />
              )}
              <span
                className={`text-lg font-semibold ${isPositive24h ? 'text-accent-500' : 'text-red-500'
                  }`}
              >
                {isPositive24h ? '+' : ''}
                {formatCurrency(change24h)} ({summary?.change_24h_percent?.toFixed(2) || '0.00'}%)
              </span>
              <span className="text-neutral-500 text-sm">24h</span>
            </div>
          </div>

          {/* Time period changes */}
          <div className="grid grid-cols-3 gap-6">
            <div className="text-center">
              <p className="text-neutral-500 text-xs uppercase tracking-wide font-medium">
                24 Hours
              </p>
              <p
                className={`text-xl font-bold mt-1 ${(summary?.change_24h_percent || 0) >= 0
                  ? 'text-accent-500'
                  : 'text-red-500'
                  }`}
              >
                {(summary?.change_24h_percent || 0) >= 0 ? '+' : ''}
                {summary?.change_24h_percent?.toFixed(2) || '0.00'}%
              </p>
            </div>
            <div className="text-center">
              <p className="text-neutral-500 text-xs uppercase tracking-wide font-medium">
                7 Days
              </p>
              <p
                className={`text-xl font-bold mt-1 ${(summary?.change_7d_percent || 0) >= 0
                  ? 'text-accent-500'
                  : 'text-red-500'
                  }`}
              >
                {(summary?.change_7d_percent || 0) >= 0 ? '+' : ''}
                {summary?.change_7d_percent?.toFixed(2) || '0.00'}%
              </p>
            </div>
            <div className="text-center">
              <p className="text-neutral-500 text-xs uppercase tracking-wide font-medium">
                30 Days
              </p>
              <p
                className={`text-xl font-bold mt-1 ${(summary?.change_30d_percent || 0) >= 0
                  ? 'text-accent-500'
                  : 'text-red-500'
                  }`}
              >
                {(summary?.change_30d_percent || 0) >= 0 ? '+' : ''}
                {summary?.change_30d_percent?.toFixed(2) || '0.00'}%
              </p>
            </div>
          </div>
        </div>
      </Card>

      {/* Top Valued Cards - Horizontal Scroll */}
      {topCards.length > 0 && (
        <Card variant="glass" className="backdrop-blur-xl bg-white/5">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary-500" />
            Top Valued Cards
          </h2>
          <div className="overflow-x-auto pb-2 -mx-2 px-2 scrollbar-hide">
            <div className="flex gap-4" style={{ minWidth: 'max-content' }}>
              {topCards.map((card, idx) => (
                <motion.div
                  key={card.product_id}
                  whileHover={{ y: -4, scale: 1.02 }}
                  className="flex-shrink-0 w-48 bg-surface-900/50 rounded-xl p-4 border border-surface-800 hover:border-primary-500/50 transition-colors shadow-sm"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-primary-500">#{idx + 1}</span>
                    <span className="text-xs text-neutral-500 truncate">{card.set_name}</span>
                  </div>
                  <p className="text-white font-medium text-sm truncate mb-1" title={card.name}>
                    {card.name}
                  </p>
                  <p className="text-neutral-500 text-xs mb-3">{card.sku}</p>
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-neutral-500">Price</span>
                      <span className="text-white font-medium">{formatCurrency(card.price)}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-neutral-500">Qty</span>
                      <span className="text-white font-medium">×{card.quantity}</span>
                    </div>
                    <div className="flex justify-between text-sm pt-2 border-t border-neutral-800">
                      <span className="text-neutral-400 font-medium">Total</span>
                      <span className="text-accent-500 font-bold">{formatCurrency(card.total_value)}</span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Value History Chart */}
      <Card variant="default">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Calendar className="w-5 h-5 text-primary-500" />
            Value History
          </h2>
          <div className="flex gap-2">
            {[7, 30, 90].map((days) => (
              <button
                key={days}
                onClick={() => setHistoryDays(days)}
                className={`px-3 py-1 text-sm rounded-lg transition-all ${historyDays === days
                  ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/20'
                  : 'bg-surface-100 dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-200 dark:hover:bg-surface-700'
                  }`}
              >
                {days}D
              </button>
            ))}
          </div>
        </div>

        {history.length > 0 ? (
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history}>
                <defs>
                  <linearGradient id="valueGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  stroke="#525252"
                  fontSize={12}
                  tickFormatter={(val) => {
                    const date = new Date(val)
                    return `${date.getMonth() + 1}/${date.getDate()}`
                  }}
                />
                <YAxis
                  stroke="#525252"
                  fontSize={12}
                  domain={[minValue, maxValue]}
                  tickFormatter={(val) => `$${val.toLocaleString()}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#18181b',
                    border: '1px solid #27272a',
                    borderRadius: '12px',
                    color: '#fff',
                    boxShadow: '0 10px 30px -10px rgba(0,0,0,0.5)'
                  }}
                  formatter={(value: number | undefined) => [value != null ? formatCurrency(value) : '', 'Value']}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#f43f5e"
                  strokeWidth={2}
                  fill="url(#valueGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-[300px] flex items-center justify-center">
            <p className="text-neutral-500">
              No price history data yet. Run a price sync to start tracking.
            </p>
          </div>
        )}
      </Card>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Cards', value: summary?.total_cards?.toLocaleString() || 0 },
          { label: 'Unique Cards', value: summary?.total_unique_cards?.toLocaleString() || 0 },
          { label: 'Avg. Card Value', value: summary?.total_unique_cards ? formatCurrency(totalValue / summary.total_unique_cards) : '$0.00' },
          { label: 'Inventory Depth', value: summary?.total_cards && summary?.total_unique_cards ? (summary.total_cards / summary.total_unique_cards).toFixed(1) + 'x' : '0x' }
        ].map((stat, i) => (
          <Card key={i} variant="default" className="p-4" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}>
            <p className="text-neutral-500 text-xs uppercase tracking-wide font-medium">
              {stat.label}
            </p>
            <p className="text-2xl font-display font-bold text-white mt-1">
              {stat.value}
            </p>
          </Card>
        ))}
      </div>

      {/* Top Movers */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Top Gainers */}
        <Card>
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-accent-500" />
            Top Gainers (24h)
          </h2>
          {stats?.top_gainers?.length ? (
            <div className="space-y-3">
              {stats.top_gainers.slice(0, 5).map((card, idx) => (
                <motion.div
                  key={card.product_id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-center justify-between p-3 bg-surface-100 dark:bg-surface-800 rounded-lg border border-transparent hover:border-accent-500/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-neutral-500 font-mono text-sm w-5">
                      #{idx + 1}
                    </span>
                    <div>
                      <p className="text-surface-900 dark:text-white font-medium text-sm truncate max-w-[180px]">
                        {card.name}
                      </p>
                      <p className="text-neutral-500 text-xs">{card.set_name}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-accent-500 font-semibold">
                      +{formatCurrency(card.price_change_24h)}
                    </p>
                    <p className="text-accent-500 text-xs">
                      +{card.percent_change_24h.toFixed(1)}%
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <p className="text-neutral-500 text-center py-8">
              No price movements yet
            </p>
          )}
        </Card>

        {/* Top Losers */}
        <Card>
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-red-500" />
            Top Losers (24h)
          </h2>
          {stats?.top_losers?.length ? (
            <div className="space-y-3">
              {stats.top_losers.slice(0, 5).map((card, idx) => (
                <motion.div
                  key={card.product_id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="flex items-center justify-between p-3 bg-surface-100 dark:bg-surface-800 rounded-lg border border-transparent hover:border-red-500/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-neutral-500 font-mono text-sm w-5">
                      #{idx + 1}
                    </span>
                    <div>
                      <p className="text-surface-900 dark:text-white font-medium text-sm truncate max-w-[180px]">
                        {card.name}
                      </p>
                      <p className="text-neutral-500 text-xs">{card.set_name}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-red-500 font-semibold">
                      {formatCurrency(card.price_change_24h)}
                    </p>
                    <p className="text-red-500 text-xs">
                      {card.percent_change_24h.toFixed(1)}%
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <p className="text-neutral-500 text-center py-8">
              No price movements yet
            </p>
          )}
        </Card>
      </div>

      {/* Last Updated */}
      {summary?.calculated_at && (
        <p className="text-center text-neutral-500 text-sm">
          Last updated: {new Date(summary.calculated_at).toLocaleString()}
        </p>
      )}
    </PageTransition>
  )
}
