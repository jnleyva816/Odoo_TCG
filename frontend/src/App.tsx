import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import ScannerPage from './pages/ScannerPage'
import InventoryPage from './pages/InventoryPage'
import SetsPage from './pages/SetsPage'
import LoginPage from './pages/LoginPage'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { FeaturesProvider, useFeatures } from './contexts/FeaturesContext'
import { InstallPrompt } from './components/InstallPrompt'

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function AppRoutes() {
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : true
  })
  const { features } = useFeatures()

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  // Determine default route based on enabled features
  const defaultRoute = features.scanner_page ? '/scanner' : 
                       features.inventory_page ? '/inventory' : '/login'

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Navigate to={defaultRoute} replace />
          </ProtectedRoute>
        }
      />

      {/* Scanner Page - conditionally enabled */}
      {features.scanner_page && (
        <Route
          path="/scanner"
          element={
            <ProtectedRoute>
              <Layout darkMode={darkMode} onToggleDark={() => setDarkMode(!darkMode)}>
                <ScannerPage />
              </Layout>
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
              <Layout darkMode={darkMode} onToggleDark={() => setDarkMode(!darkMode)}>
                <InventoryPage />
              </Layout>
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
              <Layout darkMode={darkMode} onToggleDark={() => setDarkMode(!darkMode)}>
                <SetsPage />
              </Layout>
            </ProtectedRoute>
          }
        />
      )}

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to={defaultRoute} replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <FeaturesProvider>
        <AuthProvider>
          <AppRoutes />
          <InstallPrompt />
        </AuthProvider>
      </FeaturesProvider>
    </BrowserRouter>
  )
}

export default App
