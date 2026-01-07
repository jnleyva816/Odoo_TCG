import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Sun, Moon, ScanLine, Package, Database } from 'lucide-react'

interface LayoutProps {
  children: ReactNode
  darkMode: boolean
  onToggleDark: () => void
}

export default function Layout({ children, darkMode, onToggleDark }: LayoutProps) {
  const location = useLocation()

  const navItems = [
    { path: '/scanner', label: 'Scanner', icon: ScanLine },
    { path: '/inventory', label: 'Inventory', icon: Package },
    { path: '/sets', label: 'Sets', icon: Database },
  ]

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

          {/* Theme toggle */}
          <button
            onClick={onToggleDark}
            className="p-2 rounded-lg text-surface-400 hover:text-white hover:bg-surface-800 transition-colors"
            aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? <Sun size={20} /> : <Moon size={20} />}
          </button>
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

