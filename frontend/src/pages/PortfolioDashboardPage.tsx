/**
 * Portfolio Dashboard Page - "Wall Street" style analytics
 * 
 * Features:
 * - Portfolio value with 24h/7d/30d changes
 * - Top Movers widget (gainers/losers)
 * - Liquidity breakdown chart
 * - Cost basis tracking
 */

import { useEffect, useState } from 'react';
import { useFeatures } from '../contexts/FeaturesContext';

interface PortfolioSummary {
  total_cards: number;
  total_unique_cards: number;
  total_value: string;
  total_cost_basis: string;
  unrealized_profit: string;
  change_24h: string;
  change_24h_percent: number;
  change_7d: string;
  change_7d_percent: number;
  change_30d: string;
  change_30d_percent: number;
  high_liquidity_value: string;
  medium_liquidity_value: string;
  low_liquidity_value: string;
  illiquid_value: string;
  calculated_at: string;
}

interface TopMover {
  product_id: number;
  name: string;
  sku: string;
  set_name: string;
  image_url: string | null;
  current_price: string;
  price_change_24h: string;
  percent_change_24h: number;
  quantity_owned: number;
  direction: 'up' | 'down';
}

interface PortfolioStats {
  summary: PortfolioSummary;
  top_gainers: TopMover[];
  top_losers: TopMover[];
}

export default function PortfolioDashboardPage() {
  const { features } = useFeatures();
  const [stats, setStats] = useState<PortfolioStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchStats() {
      try {
        const response = await fetch('/api/portfolio/stats', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('tcg_auth_token')}` }
        });
        if (!response.ok) throw new Error('Failed to load portfolio');
        const data = await response.json();
        setStats(data);
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load portfolio';
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    }

    if (features.portfolio_dashboard) {
      fetchStats();
    }
  }, [features.portfolio_dashboard]);

  if (!features.portfolio_dashboard) {
    return (
      <div className="p-8 text-center">
        <h1 className="text-2xl font-bold text-gray-400">Portfolio Dashboard</h1>
        <p className="mt-4 text-gray-500">This feature is not enabled.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-red-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <h1 className="text-2xl font-bold text-red-500">Error</h1>
        <p className="mt-4 text-gray-400">{error}</p>
      </div>
    );
  }

  const summary = stats?.summary;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Portfolio Dashboard</h1>
          <p className="text-gray-400 mt-1">
            Track your collection like a stock portfolio
          </p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Portfolio Value Card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
        <div className="flex items-baseline justify-between">
          <div>
            <p className="text-gray-400 text-sm uppercase tracking-wide">Total Portfolio Value</p>
            <p className="text-4xl font-bold text-white mt-1">
              ${summary?.total_value || '0.00'}
            </p>
          </div>
          <div className="text-right">
            <div className={`text-lg font-semibold ${
              (summary?.change_24h_percent || 0) >= 0 ? 'text-green-500' : 'text-red-500'
            }`}>
              {(summary?.change_24h_percent || 0) >= 0 ? '+' : ''}
              {summary?.change_24h_percent?.toFixed(2) || '0.00'}%
            </div>
            <p className="text-gray-500 text-sm">24h change</p>
          </div>
        </div>

        {/* Time period changes */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-zinc-800">
          <div>
            <p className="text-gray-500 text-xs uppercase">24 Hours</p>
            <p className={`font-semibold ${
              (summary?.change_24h_percent || 0) >= 0 ? 'text-green-500' : 'text-red-500'
            }`}>
              ${summary?.change_24h || '0.00'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs uppercase">7 Days</p>
            <p className={`font-semibold ${
              (summary?.change_7d_percent || 0) >= 0 ? 'text-green-500' : 'text-red-500'
            }`}>
              ${summary?.change_7d || '0.00'}
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-xs uppercase">30 Days</p>
            <p className={`font-semibold ${
              (summary?.change_30d_percent || 0) >= 0 ? 'text-green-500' : 'text-red-500'
            }`}>
              ${summary?.change_30d || '0.00'}
            </p>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-gray-500 text-xs uppercase">Total Cards</p>
          <p className="text-2xl font-bold text-white mt-1">
            {summary?.total_cards?.toLocaleString() || 0}
          </p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-gray-500 text-xs uppercase">Unique Cards</p>
          <p className="text-2xl font-bold text-white mt-1">
            {summary?.total_unique_cards?.toLocaleString() || 0}
          </p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-gray-500 text-xs uppercase">Cost Basis</p>
          <p className="text-2xl font-bold text-white mt-1">
            ${summary?.total_cost_basis || '0.00'}
          </p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-gray-500 text-xs uppercase">Unrealized P/L</p>
          <p className={`text-2xl font-bold mt-1 ${
            parseFloat(summary?.unrealized_profit || '0') >= 0 ? 'text-green-500' : 'text-red-500'
          }`}>
            ${summary?.unrealized_profit || '0.00'}
          </p>
        </div>
      </div>

      {/* Top Movers */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Top Gainers */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-green-500">▲</span> Top Gainers (24h)
          </h2>
          {stats?.top_gainers?.length ? (
            <div className="space-y-3">
              {stats.top_gainers.slice(0, 5).map((card) => (
                <div key={card.product_id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {card.image_url && (
                      <img
                        src={card.image_url}
                        alt={card.name}
                        className="w-10 h-14 object-cover rounded"
                      />
                    )}
                    <div>
                      <p className="text-white font-medium text-sm">{card.name}</p>
                      <p className="text-gray-500 text-xs">{card.set_name}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-green-500 font-semibold">
                      +${card.price_change_24h}
                    </p>
                    <p className="text-green-500 text-xs">
                      +{card.percent_change_24h.toFixed(1)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">No data yet</p>
          )}
        </div>

        {/* Top Losers */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <span className="text-red-500">▼</span> Top Losers (24h)
          </h2>
          {stats?.top_losers?.length ? (
            <div className="space-y-3">
              {stats.top_losers.slice(0, 5).map((card) => (
                <div key={card.product_id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {card.image_url && (
                      <img
                        src={card.image_url}
                        alt={card.name}
                        className="w-10 h-14 object-cover rounded"
                      />
                    )}
                    <div>
                      <p className="text-white font-medium text-sm">{card.name}</p>
                      <p className="text-gray-500 text-xs">{card.set_name}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-red-500 font-semibold">
                      -${Math.abs(parseFloat(card.price_change_24h))}
                    </p>
                    <p className="text-red-500 text-xs">
                      {card.percent_change_24h.toFixed(1)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">No data yet</p>
          )}
        </div>
      </div>

      {/* Liquidity Breakdown */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Liquidity Breakdown</h2>
        <div className="grid grid-cols-4 gap-4">
          <div className="text-center">
            <div className="w-full bg-zinc-800 rounded-full h-2 mb-2">
              <div className="bg-green-500 h-2 rounded-full" style={{ width: '75%' }}></div>
            </div>
            <p className="text-green-500 font-semibold">${summary?.high_liquidity_value || '0'}</p>
            <p className="text-gray-500 text-xs">High Liquidity</p>
            <p className="text-gray-600 text-xs">Sells in 24h</p>
          </div>
          <div className="text-center">
            <div className="w-full bg-zinc-800 rounded-full h-2 mb-2">
              <div className="bg-yellow-500 h-2 rounded-full" style={{ width: '50%' }}></div>
            </div>
            <p className="text-yellow-500 font-semibold">${summary?.medium_liquidity_value || '0'}</p>
            <p className="text-gray-500 text-xs">Medium Liquidity</p>
            <p className="text-gray-600 text-xs">1-7 days</p>
          </div>
          <div className="text-center">
            <div className="w-full bg-zinc-800 rounded-full h-2 mb-2">
              <div className="bg-orange-500 h-2 rounded-full" style={{ width: '25%' }}></div>
            </div>
            <p className="text-orange-500 font-semibold">${summary?.low_liquidity_value || '0'}</p>
            <p className="text-gray-500 text-xs">Low Liquidity</p>
            <p className="text-gray-600 text-xs">7-30 days</p>
          </div>
          <div className="text-center">
            <div className="w-full bg-zinc-800 rounded-full h-2 mb-2">
              <div className="bg-red-500 h-2 rounded-full" style={{ width: '10%' }}></div>
            </div>
            <p className="text-red-500 font-semibold">${summary?.illiquid_value || '0'}</p>
            <p className="text-gray-500 text-xs">Illiquid</p>
            <p className="text-gray-600 text-xs">Hard to sell</p>
          </div>
        </div>
      </div>

      {/* Last Updated */}
      {summary?.calculated_at && (
        <p className="text-center text-gray-600 text-sm">
          Last updated: {new Date(summary.calculated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

