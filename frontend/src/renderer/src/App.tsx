import { useEffect } from 'react'
import { Routes, Route, useNavigate } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import Layout from './components/Layout'
import ChatPage from './pages/ChatPage'
import MemoriesPage from './pages/MemoriesPage'
import SettingsPage from './pages/SettingsPage'
import ScreenshotsPage from './pages/ScreenshotsPage'
import VisualizationPage from './pages/VisualizationPage'

function App(): JSX.Element {
  const navigate = useNavigate()

  useEffect(() => {
    // Listen for navigation events from main process
    window.api.on('navigate', (path: string) => {
      navigate(path)
    })

    return () => {
      window.api.off('navigate', () => {})
    }
  }, [navigate])

  // Detect system dark mode
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: {
          colorPrimary: '#2D5A45',
          colorSuccess: '#2D5A45',
          colorWarning: '#E69500',
          borderRadius: 8,
          fontSize: 14,
          colorBgContainer: isDark ? '#1E1E1E' : '#FDFCF9'
        }
      }}
    >
      <div className={isDark ? 'dark' : ''}>
        <Layout>
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:conversationId" element={<ChatPage />} />
            <Route path="/memories" element={<MemoriesPage />} />
            <Route path="/screenshots" element={<ScreenshotsPage />} />
            <Route path="/insights" element={<VisualizationPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Layout>
      </div>
    </ConfigProvider>
  )
}

export default App
