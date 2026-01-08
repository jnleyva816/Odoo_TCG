import { useQuery } from '@tanstack/react-query';
import { Package, TrendingUp, Warehouse, ScanLine, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useFeatures } from '../contexts/FeaturesContext';
import { getInventory } from '../api/client';

export default function DashboardPage() {
  const { user, currentWarehouse } = useAuth();
  const { features } = useFeatures();

  const { data: inventoryData, isLoading } = useQuery({
    queryKey: ['inventory-stats', currentWarehouse?.id],
    queryFn: () => getInventory({ page: 1, page_size: 100 }),
    staleTime: 60000,
  });

  const inStockCount = inventoryData?.items.filter((c) => c.quantity > 0).length || 0;

  const stats = [
    {
      label: 'Total Cards',
      value: inventoryData?.total || 0,
      icon: Package,
      color: 'from-blue-500 to-blue-600',
      bg: 'bg-blue-50 dark:bg-blue-500/10',
    },
    {
      label: 'In Stock',
      value: inStockCount,
      icon: TrendingUp,
      color: 'from-green-500 to-green-600',
      bg: 'bg-green-50 dark:bg-green-500/10',
    },
    {
      label: 'Warehouse',
      value: currentWarehouse?.name || 'Not Set',
      icon: Warehouse,
      color: 'from-purple-500 to-purple-600',
      bg: 'bg-purple-50 dark:bg-purple-500/10',
      isText: true,
    },
  ];

  const quickActions = [
    {
      to: '/scanner',
      label: 'Scan Cards',
      description: 'Add cards to inventory with barcode scanner',
      icon: ScanLine,
      color: 'from-primary-500 to-primary-600',
      enabled: features.scanner_page,
    },
    {
      to: '/inventory',
      label: 'View Inventory',
      description: 'Browse and manage your collection',
      icon: Package,
      color: 'from-blue-500 to-blue-600',
      enabled: features.inventory_page,
    },
  ];

  return (
    <div className="p-4 lg:p-6 max-w-5xl mx-auto">
      {/* Welcome Header */}
      <div className="mb-8 animate-slide-in-up">
        <h1 className="text-2xl lg:text-3xl font-semibold text-surface-900 dark:text-white">
          Welcome back, <span className="text-primary-500">{user?.username?.split('@')[0] || 'User'}</span> 👋
        </h1>
        <p className="text-surface-500 mt-1">
          Here's an overview of your inventory
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {stats.map((stat, index) => (
          <div
            key={stat.label}
            className="card p-5 animate-slide-in-up hover:shadow-soft transition-shadow"
            style={{ animationDelay: `${(index + 1) * 50}ms` }}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-surface-500 mb-1">
                  {stat.label}
                </p>
                {isLoading ? (
                  <div className="h-8 w-20 bg-surface-100 dark:bg-surface-800 rounded-lg animate-pulse" />
                ) : (
                  <p className={`text-2xl font-semibold text-surface-900 dark:text-white ${stat.isText ? 'text-lg' : ''}`}>
                    {typeof stat.value === 'number' ? stat.value.toLocaleString() : stat.value}
                  </p>
                )}
              </div>
              <div className={`p-3 rounded-xl ${stat.bg}`}>
                <stat.icon className={`w-5 h-5 bg-gradient-to-r ${stat.color} bg-clip-text`} style={{ color: stat.color.includes('blue') ? '#3b82f6' : stat.color.includes('green') ? '#22c55e' : '#a855f7' }} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <h2 className="section-title">Quick Actions</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {quickActions.filter(a => a.enabled).map((action, index) => (
          <Link
            key={action.to}
            to={action.to}
            className="group card p-5 hover:shadow-soft-lg transition-all animate-slide-in-up"
            style={{ animationDelay: `${(index + 4) * 50}ms` }}
          >
            <div className="flex items-center gap-4">
              <div className={`p-4 rounded-xl bg-gradient-to-br ${action.color} shadow-sm`}>
                <action.icon className="w-6 h-6 text-white" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-surface-900 dark:text-white group-hover:text-primary-500 transition-colors">
                  {action.label}
                </h3>
                <p className="text-sm text-surface-500">{action.description}</p>
              </div>
              <ArrowRight className="w-5 h-5 text-surface-400 group-hover:text-primary-500 group-hover:translate-x-1 transition-all" />
            </div>
          </Link>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="mt-8 animate-slide-in-up" style={{ animationDelay: '300ms' }}>
        <h2 className="section-title">Recent Activity</h2>
        <div className="card p-8 text-center">
          <Package className="w-12 h-12 text-surface-300 dark:text-surface-700 mx-auto mb-3" />
          <p className="text-surface-500">Activity tracking coming soon</p>
        </div>
      </div>
    </div>
  );
}
