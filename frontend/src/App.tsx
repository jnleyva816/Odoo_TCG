import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import ScannerPage from './pages/ScannerPage'
import InventoryPage from './pages/InventoryPage'
import SetsPage from './pages/SetsPage'

function App() {
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('darkMode')
    return saved ? JSON.parse(saved) : true
  })

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode))
    if (darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [darkMode])

  return (
    <BrowserRouter>
      <Layout darkMode={darkMode} onToggleDark={() => setDarkMode(!darkMode)}>
        <Routes>
          <Route path="/" element={<Navigate to="/scanner" replace />} />
          <Route path="/scanner" element={<ScannerPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/sets" element={<SetsPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App

