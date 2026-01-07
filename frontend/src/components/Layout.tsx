import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Sun, Moon, ScanLine, Package, Database, LogOut, User } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { useFeatures } from '../contexts/FeaturesContext'

interface LayoutProps {
  children: ReactNode
  darkMode: boolean
  onToggleDark: () => void
}

export default function Layout({ children, darkMode, onToggleDark }: LayoutProps) {
  const location = useLocation()
  const { user, logout } = useAuth()
  const { features } = useFeatures()

  // Build nav items based on enabled features
  const navItems = [
    features.scanner_page && { path: '/scanner', label: 'Scanner', icon: ScanLine },
    features.inventory_page && { path: '/inventory', label: 'Inventory', icon: Package },
    features.sets_page && { path: '/sets', label: 'Sets', icon: Database },
  ].filter(Boolean) as { path: string; label: string; icon: typeof ScanLine }[]

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-surface-950 text-white border-b border-surface-800">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
              <span className="font-display font-bold text-white">T</span>
            </div>
            <span className="font-display font-semibold text-lg tracking-tight">
              TCG Inventory
            </span>
          </Link>

          {/* Navigation */}
          <nav className="flex items-center gap-1">
            {navItems.map(({ path, label, icon: Icon }) => {
              const isActive = location.pathname === path
              return (
                <Link
                  key={path}
                  to={path}
                  className={`
                    flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm
                    transition-all duration-150
                    ${isActive
                      ? 'bg-primary-600 text-white'
                      : 'text-surface-300 hover:text-white hover:bg-surface-800'
                    }
                  `}
                >
                  <Icon size={18} />
                  <span className="hidden sm:inline">{label}</span>
                </Link>
              )
            })}
          </nav>

          {/* User menu */}
          <div className="flex items-center gap-2">
            {/* Current user */}
            {user && (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-800/50 text-sm">
                <User size={16} className="text-surface-400" />
                <span className="text-surface-300">{user.username}</span>
                {user.role === 'admin' && (
                  <span className="px-1.5 py-0.5 text-xs font-medium bg-purple-500/20 text-purple-400 rounded">
                    Admin
                  </span>
                )}
              </div>
            )}

            {/* Theme toggle */}
            <button
              onClick={onToggleDark}
              className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 transition-colors"
              aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {darkMode ? <Sun size={20} /> : <Moon size={20} />}
            </button>

            {/* Logout */}
            <button
              onClick={logout}
              className="p-2 rounded-lg text-surface-400 hover:text-red-400 hover:bg-surface-800 transition-colors"
              aria-label="Logout"
              title="Logout"
            >
              <LogOut size={20} />
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 bg-surface-50 dark:bg-surface-950">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-surface-100 dark:bg-surface-900 border-t border-surface-200 dark:border-surface-800 py-4">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-surface-500">
          TCG Inventory Management v2.0
        </div>
      </footer>
    </div>
  )
}
