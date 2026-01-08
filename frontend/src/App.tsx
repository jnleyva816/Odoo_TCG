import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { Sidebar } from './components/Sidebar'
import ScannerPage from './pages/ScannerPage'
import InventoryPage from './pages/InventoryPage'
import SetsPage from './pages/SetsPage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import SettingsPage from './pages/SettingsPage'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { FeaturesProvider, useFeatures } from './contexts/FeaturesContext'

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-50 dark:bg-surface-950 transition-colors">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-primary-500 border-t-transparent"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  const { features } = useFeatures()

  // Apply saved theme on mount
  useEffect(() => {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark')
    }
  }, [])

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected routes with Sidebar */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Navigate to="/dashboard" replace />
          </ProtectedRoute>
        }
      />

      {/* Dashboard */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Sidebar>
              <DashboardPage />
            </Sidebar>
          </ProtectedRoute>
        }
      />

      {/* Scanner Page - conditionally enabled */}
      {features.scanner_page && (
        <Route
          path="/scanner"
          element={
            <ProtectedRoute>
              <Sidebar>
                <ScannerPage />
              </Sidebar>
            </ProtectedRoute>
          }
        />
      )}

      {/* Inventory Page - conditionally enabled */}
      {features.inventory_page && (
        <Route
          path="/inventory"
          element={
            <ProtectedRoute>
              <Sidebar>
                <InventoryPage />
              </Sidebar>
            </ProtectedRoute>
          }
        />
      )}

      {/* Sets Page - conditionally enabled */}
      {features.sets_page && (
        <Route
          path="/sets"
          element={
            <ProtectedRoute>
              <Sidebar>
                <SetsPage />
              </Sidebar>
            </ProtectedRoute>
          }
        />
      )}

      {/* Settings */}
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Sidebar>
              <SettingsPage />
            </Sidebar>
          </ProtectedRoute>
        }
      />

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <FeaturesProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </FeaturesProvider>
    </BrowserRouter>
  )
}

export default App
