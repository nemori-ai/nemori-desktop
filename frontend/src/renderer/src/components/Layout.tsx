import { ReactNode, useState } from 'react'
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
  BarChart2,
  Zap
} from 'lucide-react'
import { useLanguage } from '../contexts/LanguageContext'
import { TranslationKey } from '../i18n'

interface LayoutProps {
  children: ReactNode
}

interface NavItem {
  path: string
  icon: typeof MessageSquare
  labelKey: TranslationKey
}

const navItems: NavItem[] = [
  { path: '/chat', icon: MessageSquare, labelKey: 'nav.chat' },
  { path: '/memories', icon: Brain, labelKey: 'nav.memories' },
  { path: '/insights', icon: BarChart2, labelKey: 'nav.insights' },
  { path: '/proactive', icon: Zap, labelKey: 'nav.proactive' },
  { path: '/screenshots', icon: Image, labelKey: 'nav.screenshots' },
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' }
]

// Detect platform from user agent (renderer process doesn't have process.platform)
const isMacOS = navigator.userAgent.includes('Mac')

export default function Layout({ children }: LayoutProps): JSX.Element {
  const navigate = useNavigate()
  const location = useLocation()
  const [isCollapsed, setIsCollapsed] = useState(false)
  const { t } = useLanguage()

  const handleMinimize = (): void => {
    window.api.window.minimize()
  }

  const handleMaximize = (): void => {
    window.api.window.maximize()
  }

  const handleClose = (): void => {
    window.api.window.close()
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Glassmorphism Sidebar */}
      <aside
        className={`flex flex-col glass-sidebar transition-all duration-300 ${
          isCollapsed ? 'w-16' : 'w-56'
        }`}
      >
        {/* Title bar / drag region */}
        <div
          className={`drag-region h-12 flex items-center border-b border-border/50 ${
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
                className="p-1.5 rounded-lg hover:bg-muted/60 transition-all duration-200"
              >
                <Minus className="w-4 h-4" />
              </button>
              <button
                onClick={handleMaximize}
                className="p-1.5 rounded-lg hover:bg-muted/60 transition-all duration-200"
              >
                <Square className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleClose}
                className="p-1.5 rounded-lg hover:bg-destructive hover:text-destructive-foreground transition-all duration-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>

        {/* Navigation with warm minimalism */}
        <nav className="flex-1 p-3 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname.startsWith(item.path)

            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-primary/12 text-primary shadow-warm-sm'
                    : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                }`}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {!isCollapsed && <span className="text-sm font-medium">{t(item.labelKey)}</span>}
              </button>
            )
          })}
        </nav>

        {/* Collapse toggle */}
        <div className="p-3 border-t border-border/50">
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="w-full flex items-center justify-center p-2.5 rounded-lg text-muted-foreground hover:bg-muted/60 hover:text-foreground transition-all duration-200"
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
