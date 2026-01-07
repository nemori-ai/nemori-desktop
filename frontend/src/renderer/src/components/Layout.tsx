import { ReactNode, useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  MessageSquare,
  Brain,
  Image,
  Settings,
  ChevronLeft,
  ChevronRight,
  Minus,
  Square,
  X,
  BarChart2
} from 'lucide-react'

interface LayoutProps {
  children: ReactNode
}

const navItems = [
  { path: '/chat', icon: MessageSquare, label: 'Chat' },
  { path: '/memories', icon: Brain, label: 'Memories' },
  { path: '/insights', icon: BarChart2, label: 'Insights' },
  { path: '/screenshots', icon: Image, label: 'Screenshots' },
  { path: '/settings', icon: Settings, label: 'Settings' }
]

// Detect platform from user agent (renderer process doesn't have process.platform)
const isMacOS = navigator.userAgent.includes('Mac')

export default function Layout({ children }: LayoutProps): JSX.Element {
  const navigate = useNavigate()
  const location = useLocation()
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [isMaximized, setIsMaximized] = useState(false)

  const handleMinimize = (): void => {
    window.api.window.minimize()
  }

  const handleMaximize = async (): Promise<void> => {
    const maximized = await window.api.window.maximize()
    setIsMaximized(maximized)
  }

  const handleClose = (): void => {
    window.api.window.close()
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside
        className={`flex flex-col border-r border-border bg-card transition-all duration-300 ${
          isCollapsed ? 'w-16' : 'w-56'
        }`}
      >
        {/* Title bar / drag region */}
        <div
          className={`drag-region h-12 flex items-center border-b border-border ${
            isMacOS ? 'pl-20 pr-4' : 'px-4'
          }`}
        >
          {!isCollapsed && (
            <span className="font-semibold text-lg text-primary no-drag">Nemori</span>
          )}
          {!isMacOS && (
            <div className="flex items-center gap-1 no-drag ml-auto">
              <button
                onClick={handleMinimize}
                className="p-1.5 rounded hover:bg-muted transition-colors"
              >
                <Minus className="w-4 h-4" />
              </button>
              <button
                onClick={handleMaximize}
                className="p-1.5 rounded hover:bg-muted transition-colors"
              >
                <Square className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleClose}
                className="p-1.5 rounded hover:bg-destructive hover:text-destructive-foreground transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname.startsWith(item.path)

            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                }`}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {!isCollapsed && <span className="text-sm font-medium">{item.label}</span>}
              </button>
            )
          })}
        </nav>

        {/* Collapse toggle */}
        <div className="p-2 border-t border-border">
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-full flex items-center justify-center p-2 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            {isCollapsed ? (
              <ChevronRight className="w-5 h-5" />
            ) : (
              <ChevronLeft className="w-5 h-5" />
            )}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* macOS title bar drag region */}
        {isMacOS && <div className="drag-region h-8 flex-shrink-0" />}

        {/* Page content */}
        <div className="flex-1 overflow-auto">{children}</div>
      </main>
    </div>
  )
}
