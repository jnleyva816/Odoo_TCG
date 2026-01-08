import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Menu,
  X,
  LayoutDashboard,
  ScanLine,
  Package,
  Settings,
  LogOut,
  Warehouse,
  Sun,
  Moon,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useFeatures } from '../contexts/FeaturesContext';

interface SidebarProps {
  children: React.ReactNode;
}

export function Sidebar({ children }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved ? saved === 'dark' : true;
  });
  const { user, logout, warehouses, currentWarehouse, switchWarehouse, canSwitchWarehouse } = useAuth();
  const { features } = useFeatures();
  const location = useLocation();

  // Apply theme
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setIsOpen(false);
  }, [location.pathname]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', enabled: true },
    { to: '/scanner', icon: ScanLine, label: 'Scanner', enabled: features.scanner_page },
    { to: '/inventory', icon: Package, label: 'Inventory', enabled: features.inventory_page },
    { to: '/settings', icon: Settings, label: 'Settings', enabled: true },
  ];

  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-950 transition-colors duration-200">
      {/* Mobile Header */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-white dark:bg-surface-900 border-b border-surface-200 dark:border-surface-800">
        <div className="flex items-center justify-between px-4 h-14">
          <button
            onClick={() => setIsOpen(true)}
            className="p-2 text-surface-500 hover:text-primary-500 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          
          <h1 className="font-semibold text-surface-900 dark:text-white">
            TCG Inventory
          </h1>
          
          <button
            onClick={() => setIsDark(!isDark)}
            className="p-2 text-surface-500 hover:text-primary-500 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
            aria-label="Toggle theme"
          >
            {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>
      </header>

      {/* Overlay */}
      {isOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-sm animate-fade-in"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-full w-72 
          bg-white dark:bg-surface-900 
          border-r border-surface-200 dark:border-surface-800
          transform transition-transform duration-300 ease-out
          lg:translate-x-0
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-200 dark:border-surface-800">
          <div className="flex items-center gap-3">
            {/* Logo */}
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center shadow-sm">
              <Package className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-white">
                TCG Inventory
              </h2>
              <p className="text-xs text-surface-500">v2.0.0</p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="lg:hidden p-2 text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Info */}
        {user && (
          <div className="p-4 border-b border-surface-200 dark:border-surface-800">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center text-white font-semibold shadow-sm">
                {user.username[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-surface-900 dark:text-white truncate">
                  {user.username}
                </p>
                <p className="text-xs text-surface-500 capitalize">{user.role}</p>
              </div>
            </div>
            
            {/* Warehouse Selector */}
            {currentWarehouse && (
              <div className="mt-3 p-3 bg-surface-50 dark:bg-surface-800 rounded-lg">
                <div className="flex items-center gap-2 text-xs text-surface-500 mb-2">
                  <Warehouse className="w-3.5 h-3.5" />
                  <span>Current Warehouse</span>
                </div>
                {canSwitchWarehouse ? (
                  <select
                    value={currentWarehouse.id}
                    onChange={(e) => switchWarehouse(Number(e.target.value))}
                    className="w-full bg-white dark:bg-surface-900 text-surface-900 dark:text-white text-sm rounded-lg px-3 py-2 border border-surface-200 dark:border-surface-700 focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                  >
                    {warehouses.map((w) => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                ) : (
                  <p className="text-sm font-medium text-surface-900 dark:text-white truncate">
                    {currentWarehouse.name}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <nav className="p-3 space-y-1">
          {navItems.filter(item => item.enabled).map((item, index) => (
            <NavLink
              key={item.to}
              to={item.to}
              style={{ animationDelay: `${index * 50}ms` }}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-lg
                font-medium text-sm
                transition-all duration-200 animate-fade-in
                ${isActive
                  ? 'bg-primary-500 text-white shadow-sm'
                  : 'text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-900 dark:hover:text-white'
                }
              `}
            >
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Bottom Section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-surface-200 dark:border-surface-800">
          {/* Theme Toggle */}
          <div className="hidden lg:flex items-center justify-between p-3 bg-surface-50 dark:bg-surface-800 rounded-lg mb-3">
            <span className="text-sm text-surface-600 dark:text-surface-400">Theme</span>
            <button
              onClick={() => setIsDark(!isDark)}
              className={`
                relative w-14 h-7 rounded-full transition-colors duration-200
                ${isDark ? 'bg-primary-500' : 'bg-surface-300'}
              `}
            >
              <div className={`
                absolute top-1 w-5 h-5 rounded-full bg-white shadow-sm
                transition-transform duration-200 flex items-center justify-center
                ${isDark ? 'translate-x-8' : 'translate-x-1'}
              `}>
                {isDark ? <Moon className="w-3 h-3 text-primary-500" /> : <Sun className="w-3 h-3 text-amber-500" />}
              </div>
            </button>
          </div>

          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
                       text-surface-600 dark:text-surface-400 
                       font-medium text-sm
                       hover:bg-red-50 dark:hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-400 
                       transition-colors"
          >
            <LogOut className="w-5 h-5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="lg:pl-72 pt-14 lg:pt-0 min-h-screen">
        <div className="animate-fade-in">
          {children}
        </div>
      </main>
    </div>
  );
}
