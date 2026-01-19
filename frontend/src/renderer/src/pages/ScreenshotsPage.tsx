import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, Pause, Trash2, RefreshCw, X, Monitor, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Calendar, Sparkles, PenLine, Play } from 'lucide-react'
import { api, Screenshot, CaptureStatus } from '../services/api'
import { formatDateDisplay, getTodayDateStr } from '../utils/file'
import { useLanguage } from '../contexts/LanguageContext'
import { NemoriBot } from '../components/NemoriBot'
import { useAgent } from '../contexts/AgentContext'

// Cache for blob URLs to avoid re-fetching
const blobUrlCache = new Map<string, string>()

// Pagination config
const PAGE_SIZE = 20

export default function ScreenshotsPage(): JSX.Element {
  const { t, language } = useLanguage()
  const { isRecording } = useAgent()
  const isZh = language === 'zh'
  const [screenshots, setScreenshots] = useState<Screenshot[]>([])
  const [captureStatus, setCaptureStatus] = useState<CaptureStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedScreenshot, setSelectedScreenshot] = useState<Screenshot | null>(null)
  const [showMonitorPicker, setShowMonitorPicker] = useState(false)
  const [monitorPreviews, setMonitorPreviews] = useState<Record<number, string>>({})
  const [loadingPreviews, setLoadingPreviews] = useState(false)
  const [permissionError, setPermissionError] = useState<string | null>(null)

  // Date-based loading state
  const [availableDates, setAvailableDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState<string>('')
  const loadingDateRef = useRef<string>('')

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)

  // Load available dates on mount and determine initial date
  useEffect(() => {
    const initializeData = async (): Promise<void> => {
      try {
        const { dates } = await api.getScreenshotDates()
        setAvailableDates(dates)
        const today = getTodayDateStr()
        const dateToLoad = dates.includes(today) ? today : (dates[0] || today)
        loadingDateRef.current = dateToLoad
        setSelectedDate(dateToLoad)
        setCurrentPage(1)
        await loadScreenshotsPage(dateToLoad, 1)
      } catch (error) {
        console.error('Failed to initialize:', error)
        const today = getTodayDateStr()
        loadingDateRef.current = today
        setSelectedDate(today)
        setCurrentPage(1)
        await loadScreenshotsPage(today, 1)
      }
    }

    initializeData()
    loadCaptureStatus()
  }, [])

  useEffect(() => {
    if (!selectedDate || loadingDateRef.current === selectedDate) return
    setCurrentPage(1)
    loadScreenshotsPage(selectedDate, 1)
  }, [selectedDate])

  useEffect(() => {
    if (selectedDate && loadingDateRef.current === selectedDate) {
      loadScreenshotsPage(selectedDate, currentPage)
    }
  }, [currentPage])

  const loadAvailableDates = async (): Promise<void> => {
    try {
      const { dates } = await api.getScreenshotDates()
      setAvailableDates(dates)
    } catch (error) {
      console.error('Failed to load dates:', error)
    }
  }

  const loadCaptureStatus = async (): Promise<void> => {
    try {
      const status = await api.getCaptureStatus()
      setCaptureStatus(status)
    } catch (error) {
      console.error('Failed to load capture status:', error)
    }
  }

  const loadScreenshotsPage = async (date: string, page: number): Promise<void> => {
    loadingDateRef.current = date
    setIsLoading(true)

    try {
      const offset = (page - 1) * PAGE_SIZE
      const { screenshots: data, total } = await api.getScreenshotsByDate(date, PAGE_SIZE, offset)

      if (loadingDateRef.current === date) {
        setScreenshots(data)
        setTotalCount(total)
      }
    } catch (error) {
      console.error('Failed to load screenshots:', error)
      if (loadingDateRef.current === date) {
        setScreenshots([])
        setTotalCount(0)
      }
    } finally {
      if (loadingDateRef.current === date) {
        setIsLoading(false)
      }
    }
  }

  const handleRefresh = async (): Promise<void> => {
    await Promise.all([
      loadAvailableDates(),
      loadScreenshotsPage(selectedDate, currentPage),
      loadCaptureStatus()
    ])
  }

  const handleToggleCapture = async (): Promise<void> => {
    try {
      if (captureStatus?.is_capturing) {
        const { status } = await api.stopCapture()
        setCaptureStatus(status)
      } else {
        const { status } = await api.startCapture()
        setCaptureStatus(status)
      }
    } catch (error) {
      console.error('Failed to toggle capture:', error)
    }
  }

  const handleCaptureNow = async (): Promise<void> => {
    try {
      const result = await api.captureNow()
      if (result.success && result.screenshot) {
        if (selectedDate === getTodayDateStr() && currentPage === 1) {
          setScreenshots((prev) => [result.screenshot!, ...prev.slice(0, PAGE_SIZE - 1)])
          setTotalCount((prev) => prev + 1)
        } else if (selectedDate === getTodayDateStr()) {
          setTotalCount((prev) => prev + 1)
        }
        loadAvailableDates()
      } else if (result.error) {
        if (result.error.includes('permission')) {
          setPermissionError(result.error)
        } else {
          console.error('Capture failed:', result.error)
        }
      }
    } catch (error) {
      console.error('Failed to capture:', error)
    }
  }

  const handleDelete = async (id: string): Promise<void> => {
    try {
      await api.deleteScreenshot(id)
      setScreenshots((prev) => prev.filter((s) => s.id !== id))
      setTotalCount((prev) => Math.max(0, prev - 1))
      if (selectedScreenshot?.id === id) {
        setSelectedScreenshot(null)
      }
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  const handleSelectMonitors = async (monitorIds: number[]): Promise<void> => {
    try {
      const { selected_monitors, monitors } = await api.selectMonitors(monitorIds)
      setCaptureStatus((prev) =>
        prev ? { ...prev, selected_monitors, selected_monitor: selected_monitors[0], monitors } : null
      )
      setShowMonitorPicker(false)
    } catch (error) {
      console.error('Failed to select monitors:', error)
    }
  }

  const openMonitorPicker = async (): Promise<void> => {
    setShowMonitorPicker(true)
    if (captureStatus?.monitors) {
      setLoadingPreviews(true)
      const previews: Record<number, string> = {}
      for (const mon of captureStatus.monitors) {
        try {
          const result = await api.getMonitorPreview(mon.id)
          if (typeof result === 'string') {
            previews[mon.id] = result
          } else {
            previews[mon.id] = URL.createObjectURL(result)
          }
        } catch (e) {
          console.error(`Failed to load preview for monitor ${mon.id}:`, e)
        }
      }
      setMonitorPreviews(previews)
      setLoadingPreviews(false)
    }
  }

  const navigateDate = (direction: 'prev' | 'next'): void => {
    const currentIndex = availableDates.indexOf(selectedDate)
    if (direction === 'prev' && currentIndex < availableDates.length - 1) {
      setSelectedDate(availableDates[currentIndex + 1])
    } else if (direction === 'next' && currentIndex > 0) {
      setSelectedDate(availableDates[currentIndex - 1])
    }
  }

  const formatTime = (timestamp: number): string => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const currentDateIndex = availableDates.indexOf(selectedDate)
  const hasPrevDate = currentDateIndex < availableDates.length - 1
  const hasNextDate = currentDateIndex > 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header with Nemori branding - friendly language */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <motion.div
            className="w-12 h-12"
            animate={isRecording ? { scale: [1, 1.1, 1] } : {}}
            transition={{ repeat: Infinity, duration: 2 }}
          >
            <NemoriBot showStatus={false} size="lg" interactive={false} />
          </motion.div>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-primary" />
              {isZh ? '我的日记' : 'My Journal'}
            </h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              {isRecording ? (
                <span className="flex items-center gap-1.5">
                  <motion.span
                    className="w-2 h-2 rounded-full bg-green-500"
                    animate={{ opacity: [1, 0.5, 1] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                  />
                  {isZh ? '正在记录你的精彩时刻~' : 'Taking notes about your day~'}
                </span>
              ) : (
                isZh ? '记录着你每天的点点滴滴' : 'Memories of your daily moments'
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <motion.button
            onClick={handleRefresh}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-muted/60 hover:bg-muted transition-all duration-200 shadow-warm-sm"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </motion.button>
          <motion.button
            onClick={handleCaptureNow}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-muted/60 hover:bg-muted transition-all duration-200 shadow-warm-sm"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <PenLine className="w-4 h-4" />
            <span>{isZh ? '记一笔' : 'Note Now'}</span>
          </motion.button>
          <motion.button
            onClick={handleToggleCapture}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl transition-all duration-200 shadow-warm ${
              captureStatus?.is_capturing
                ? 'bg-amber-500/90 text-white hover:bg-amber-600'
                : 'bg-primary text-primary-foreground hover:bg-primary/90'
            }`}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {captureStatus?.is_capturing ? (
              <>
                <Pause className="w-4 h-4" />
                <span>{isZh ? '暂停记录' : 'Pause'}</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                <span>{isZh ? '开始记录' : 'Start'}</span>
              </>
            )}
          </motion.button>
        </div>
      </div>

      {/* Permission error banner - friendly language */}
      <AnimatePresence>
        {permissionError && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-4 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
                <BookOpen className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
                  {isZh ? '需要你的允许才能帮你记录~' : 'I need your permission to take notes~'}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {isZh ? '请在系统设置中授权屏幕录制权限' : 'Please grant screen recording permission in System Settings'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => api.openScreenshotPermissionSettings()}
                className="px-3 py-1.5 text-sm rounded-lg bg-amber-500 text-white hover:bg-amber-600 transition-colors"
              >
                {isZh ? '打开设置' : 'Open Settings'}
              </button>
              <button
                onClick={() => setPermissionError(null)}
                className="p-1.5 rounded-lg hover:bg-amber-500/20 transition-colors"
              >
                <X className="w-4 h-4 text-amber-600" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Timeline navigator */}
      <div className="flex items-center gap-4 mb-6 p-4 rounded-xl glass-card">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-muted-foreground" />
          <motion.button
            onClick={() => navigateDate('prev')}
            disabled={!hasPrevDate}
            className="p-1.5 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            <ChevronLeft className="w-4 h-4" />
          </motion.button>
          <span className="text-sm font-medium min-w-[100px] text-center">
            {formatDateDisplay(selectedDate)}
          </span>
          <motion.button
            onClick={() => navigateDate('next')}
            disabled={!hasNextDate}
            className="p-1.5 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            <ChevronRight className="w-4 h-4" />
          </motion.button>
        </div>

        <div className="h-4 w-px bg-border/50" />

        {captureStatus && (
          <>
            <div className="flex items-center gap-2">
              <motion.div
                className={`w-2.5 h-2.5 rounded-full ${
                  captureStatus.is_capturing ? 'bg-green-500' : 'bg-muted-foreground/50'
                }`}
                animate={captureStatus.is_capturing ? { scale: [1, 1.2, 1], opacity: [1, 0.6, 1] } : {}}
                transition={{ repeat: Infinity, duration: 2 }}
              />
              <span className="text-sm">
                {captureStatus.is_capturing
                  ? (isZh ? '记录中' : 'Recording')
                  : (isZh ? '休息中' : 'Resting')
                }
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Sparkles className="w-3.5 h-3.5" />
              {totalCount} {isZh ? '条记忆' : 'memories'}
            </div>

            {captureStatus.monitors && captureStatus.monitors.length >= 1 && (
              <motion.button
                onClick={openMonitorPicker}
                className="flex items-center gap-2 ml-auto px-3 py-2 rounded-lg bg-background/80 border border-input/50 hover:bg-muted/60 transition-all"
                whileHover={{ scale: 1.02 }}
              >
                <Monitor className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">
                  {captureStatus.monitors.find((m) => m.id === captureStatus.selected_monitor)?.name || (isZh ? '选择屏幕' : 'Select Screen')}
                </span>
              </motion.button>
            )}
          </>
        )}
      </div>

      {/* Memory grid */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-full">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
              >
                <RefreshCw className="w-8 h-8 text-primary/60" />
              </motion.div>
              <p className="text-sm text-muted-foreground mt-3">
                {isZh ? '翻阅记忆中...' : 'Flipping through memories...'}
              </p>
            </div>
          ) : screenshots.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <motion.div
                className="w-24 h-24 mb-4"
                animate={{ y: [0, -8, 0] }}
                transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
              >
                <NemoriBot showStatus={false} size="xl" interactive={false} />
              </motion.div>
              <h2 className="text-xl font-semibold mb-2">
                {isZh ? '这天还没有记录' : 'No notes yet'}
              </h2>
              <p className="text-sm text-center max-w-md">
                {isZh
                  ? `${formatDateDisplay(selectedDate)} 还没有任何记录。点击"开始记录"让我帮你记住精彩时刻！`
                  : `Nothing noted on ${formatDateDisplay(selectedDate)}. Start recording to let me remember your moments!`
                }
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {screenshots.map((screenshot, index) => (
                <MemoryCard
                  key={screenshot.id}
                  screenshot={screenshot}
                  onClick={() => setSelectedScreenshot(screenshot)}
                  onDelete={() => handleDelete(screenshot.id)}
                  formatTime={formatTime}
                  index={index}
                />
              ))}
            </div>
          )}
        </div>

        {totalPages > 1 && (
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
          />
        )}
      </div>

      {/* Holographic viewer modal */}
      <AnimatePresence>
        {selectedScreenshot && (
          <HolographicViewer
            screenshot={selectedScreenshot}
            onClose={() => setSelectedScreenshot(null)}
            onDelete={() => handleDelete(selectedScreenshot.id)}
          />
        )}
      </AnimatePresence>

      {/* Monitor picker modal */}
      {showMonitorPicker && (
        <MonitorPickerModal
          captureStatus={captureStatus}
          monitorPreviews={monitorPreviews}
          loadingPreviews={loadingPreviews}
          onSelect={handleSelectMonitors}
          onClose={() => setShowMonitorPicker(false)}
        />
      )}
    </div>
  )
}

// Memory card with animated entrance
function MemoryCard({
  screenshot,
  onClick,
  onDelete,
  formatTime,
  index
}: {
  screenshot: Screenshot
  onClick: () => void
  onDelete: () => void
  formatTime: (ts: number) => string
  index: number
}): JSX.Element {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const cached = blobUrlCache.get(screenshot.id)
    if (cached) {
      setBlobUrl(cached)
      setIsLoading(false)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadImage()
          observer.disconnect()
        }
      },
      { rootMargin: '100px' }
    )

    if (cardRef.current) {
      observer.observe(cardRef.current)
    }

    return () => observer.disconnect()
  }, [screenshot.id])

  const loadImage = async (): Promise<void> => {
    try {
      const blob = await api.getScreenshotImage(screenshot.id)
      const url = URL.createObjectURL(blob)
      blobUrlCache.set(screenshot.id, url)
      setBlobUrl(url)
    } catch (error) {
      console.error('Failed to load image:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <motion.div
      ref={cardRef}
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: index * 0.03, duration: 0.3 }}
      className="group relative rounded-xl overflow-hidden glass-card hover:shadow-warm cursor-pointer"
      onClick={onClick}
      whileHover={{ scale: 1.02, y: -2 }}
    >
      <div className="aspect-video bg-muted/50 relative overflow-hidden">
        {isLoading ? (
          <div className="w-full h-full flex items-center justify-center">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
            >
              <RefreshCw className="w-5 h-5 text-muted-foreground/50" />
            </motion.div>
          </div>
        ) : blobUrl ? (
          <>
            <img
              src={blobUrl}
              alt={screenshot.window_title || 'Memory'}
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            />
            {/* Holographic overlay on hover */}
            <motion.div
              className="absolute inset-0 bg-gradient-to-t from-primary/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"
            />
          </>
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Eye className="w-8 h-8 text-muted-foreground/30" />
          </div>
        )}

        {/* Scan line effect on hover */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 pointer-events-none"
          initial={{ y: '-100%' }}
          whileHover={{ y: '200%' }}
          transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
        />
      </div>

      <div className="p-2.5">
        <p className="text-xs font-medium truncate">{screenshot.window_title || 'Unknown'}</p>
        <p className="text-xs text-muted-foreground flex items-center gap-1">
          <span className="w-1 h-1 rounded-full bg-primary/50" />
          {formatTime(screenshot.timestamp)}
        </p>
      </div>

      <motion.button
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
        className="absolute top-2 right-2 p-1.5 rounded-full bg-black/50 text-white opacity-0 group-hover:opacity-100 hover:bg-red-500 transition-all"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        <Trash2 className="w-3.5 h-3.5" />
      </motion.button>
    </motion.div>
  )
}

// Holographic viewer modal
function HolographicViewer({
  screenshot,
  onClose,
  onDelete
}: {
  screenshot: Screenshot
  onClose: () => void
  onDelete: () => void
}): JSX.Element {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const cached = blobUrlCache.get(screenshot.id)
    if (cached) {
      setBlobUrl(cached)
      setIsLoading(false)
      return
    }

    const loadImage = async (): Promise<void> => {
      try {
        const blob = await api.getScreenshotImage(screenshot.id)
        const url = URL.createObjectURL(blob)
        blobUrlCache.set(screenshot.id, url)
        setBlobUrl(url)
      } catch (error) {
        console.error('Failed to load image:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadImage()
  }, [screenshot.id])

  const formatDateTime = (timestamp: number): string => {
    return new Date(timestamp).toLocaleString('zh-CN')
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50"
      onClick={onClose}
    >
      {/* Holographic projection beam */}
      <motion.div
        className="absolute bottom-0 left-1/2 -translate-x-1/2 w-32 h-[60vh] opacity-20"
        style={{
          background: 'linear-gradient(to top, rgba(45, 90, 69, 0.8), transparent)',
          clipPath: 'polygon(35% 100%, 65% 100%, 80% 0, 20% 0)'
        }}
        initial={{ opacity: 0, scaleY: 0 }}
        animate={{ opacity: 0.3, scaleY: 1 }}
        transition={{ duration: 0.5 }}
      />

      <motion.div
        initial={{ scale: 0.8, y: 50, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        exit={{ scale: 0.8, y: 50, opacity: 0 }}
        transition={{ type: "spring", damping: 25 }}
        className="relative max-w-[85vw] max-h-[85vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Holographic frame */}
        <div className="relative rounded-2xl overflow-hidden shadow-2xl">
          {/* Scan lines overlay */}
          <div
            className="absolute inset-0 z-10 pointer-events-none opacity-[0.03]"
            style={{
              backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.1) 2px, rgba(255,255,255,0.1) 4px)'
            }}
          />

          {/* Animated scan line */}
          <motion.div
            className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-primary/50 to-transparent z-20 pointer-events-none"
            animate={{ y: ['-100%', '4000%'] }}
            transition={{ repeat: Infinity, duration: 4, ease: "linear" }}
          />

          {/* Image */}
          {isLoading ? (
            <div className="w-[60vw] h-[50vh] flex items-center justify-center bg-black/50">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
              >
                <RefreshCw className="w-8 h-8 text-primary" />
              </motion.div>
            </div>
          ) : blobUrl ? (
            <img
              src={blobUrl}
              alt="Memory"
              className="max-w-full max-h-[70vh] object-contain"
            />
          ) : (
            <div className="w-[60vw] h-[50vh] flex items-center justify-center bg-black/50">
              <Eye className="w-16 h-16 text-muted-foreground/30" />
            </div>
          )}

          {/* Holographic glow */}
          <div className="absolute inset-0 rounded-2xl pointer-events-none"
            style={{
              boxShadow: 'inset 0 0 30px rgba(45, 90, 69, 0.3), 0 0 60px rgba(45, 90, 69, 0.2)'
            }}
          />
        </div>

        {/* Metadata panel */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mt-4 p-4 rounded-xl bg-black/40 backdrop-blur-sm border border-primary/20"
        >
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-white font-medium flex items-center gap-2">
                <Eye className="w-4 h-4 text-primary" />
                {screenshot.window_title || 'Unknown Window'}
              </h3>
              <p className="text-sm text-white/60 mt-1">
                Captured at {formatDateTime(screenshot.timestamp)}
              </p>
              {screenshot.app_name && (
                <p className="text-xs text-white/40 mt-0.5">
                  App: {screenshot.app_name}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <motion.button
                onClick={onDelete}
                className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <Trash2 className="w-4 h-4" />
              </motion.button>
              <motion.button
                onClick={onClose}
                className="p-2 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-colors"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
              >
                <X className="w-4 h-4" />
              </motion.button>
            </div>
          </div>
        </motion.div>

        {/* Nemori projection indicator */}
        <motion.div
          className="absolute -bottom-16 left-1/2 -translate-x-1/2"
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
        >
          <div className="w-12 h-12 relative">
            <NemoriBot showStatus={false} size="lg" interactive={false} />
            <motion.div
              className="absolute inset-0 rounded-full"
              style={{ boxShadow: '0 0 20px rgba(45, 90, 69, 0.6)' }}
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ repeat: Infinity, duration: 2 }}
            />
          </div>
        </motion.div>
      </motion.div>
    </motion.div>
  )
}

// Pagination component
function Pagination({
  currentPage,
  totalPages,
  onPageChange
}: {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}): JSX.Element {
  const getVisiblePages = (): (number | string)[] => {
    const pages: (number | string)[] = []
    const maxVisible = 5

    if (totalPages <= maxVisible + 2) {
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      pages.push(1)
      if (currentPage > 3) pages.push('...')
      const start = Math.max(2, currentPage - 1)
      const end = Math.min(totalPages - 1, currentPage + 1)
      for (let i = start; i <= end; i++) {
        if (!pages.includes(i)) pages.push(i)
      }
      if (currentPage < totalPages - 2) pages.push('...')
      if (!pages.includes(totalPages)) pages.push(totalPages)
    }
    return pages
  }

  return (
    <div className="flex items-center justify-center gap-1 py-4 mt-4 border-t border-border/50">
      <motion.button
        onClick={() => onPageChange(1)}
        disabled={currentPage === 1}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        <ChevronsLeft className="w-4 h-4" />
      </motion.button>

      <motion.button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        <ChevronLeft className="w-4 h-4" />
      </motion.button>

      <div className="flex items-center gap-1 mx-2">
        {getVisiblePages().map((page, idx) =>
          typeof page === 'number' ? (
            <motion.button
              key={idx}
              onClick={() => onPageChange(page)}
              className={`min-w-[36px] h-9 px-3 rounded-lg text-sm font-medium transition-all ${
                currentPage === page
                  ? 'bg-primary text-primary-foreground shadow-warm-sm'
                  : 'hover:bg-muted/60'
              }`}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              {page}
            </motion.button>
          ) : (
            <span key={idx} className="px-2 text-muted-foreground">{page}</span>
          )
        )}
      </div>

      <motion.button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        <ChevronRight className="w-4 h-4" />
      </motion.button>

      <motion.button
        onClick={() => onPageChange(totalPages)}
        disabled={currentPage === totalPages}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
      >
        <ChevronsRight className="w-4 h-4" />
      </motion.button>

      <span className="ml-4 text-sm text-muted-foreground">
        Page {currentPage} of {totalPages}
      </span>
    </div>
  )
}

// Monitor picker modal
function MonitorPickerModal({
  captureStatus,
  monitorPreviews,
  loadingPreviews,
  onSelect,
  onClose
}: {
  captureStatus: CaptureStatus | null
  monitorPreviews: Record<number, string>
  loadingPreviews: boolean
  onSelect: (ids: number[]) => void
  onClose: () => void
}): JSX.Element {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => {
    const initial = new Set<number>()
    if (captureStatus?.selected_monitors) {
      captureStatus.selected_monitors.forEach(id => initial.add(id))
    } else if (captureStatus?.selected_monitor !== undefined) {
      initial.add(captureStatus.selected_monitor)
    }
    return initial
  })

  const toggleMonitor = (id: number): void => {
    setSelectedIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) newSet.delete(id)
      else newSet.add(id)
      return newSet
    })
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        className="glass-card rounded-2xl p-6 max-w-4xl w-full mx-4 shadow-warm-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10">
              <NemoriBot showStatus={false} size="md" interactive={false} />
            </div>
            <div>
              <h2 className="text-xl font-bold">{t('screenshots.whereToLook')}</h2>
              <p className="text-sm text-muted-foreground">{isZh ? '选择我应该观察的屏幕' : 'Select the screens I should observe'}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-muted/60 transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex items-center gap-2 mb-4">
          <button
            onClick={() => captureStatus?.monitors && setSelectedIds(new Set(captureStatus.monitors.map(m => m.id)))}
            className="px-3 py-1.5 text-sm rounded-lg bg-muted/60 hover:bg-muted transition-all"
          >
            {t('screenshots.selectAll')}
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="px-3 py-1.5 text-sm rounded-lg bg-muted/60 hover:bg-muted transition-all"
          >
            {isZh ? '清除' : 'Clear'}
          </button>
          <span className="text-sm text-muted-foreground ml-2">
            {selectedIds.size} {t('screenshots.selected')}
          </span>
        </div>

        {loadingPreviews ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {captureStatus?.monitors.map((mon) => (
              <motion.button
                key={mon.id}
                onClick={() => toggleMonitor(mon.id)}
                className={`relative rounded-xl border-2 overflow-hidden transition-all ${
                  selectedIds.has(mon.id)
                    ? 'border-primary ring-2 ring-primary/20'
                    : 'border-border/50 hover:border-primary/50'
                }`}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
              >
                <div className="aspect-video bg-muted/50">
                  {monitorPreviews[mon.id] ? (
                    <img src={monitorPreviews[mon.id]} alt={mon.name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Monitor className="w-12 h-12 text-muted-foreground/30" />
                    </div>
                  )}
                </div>
                <div className="p-3 text-left bg-background/50">
                  <p className="font-medium text-sm">{mon.name}</p>
                  <p className="text-xs text-muted-foreground">{mon.width} x {mon.height}</p>
                </div>
                <div className={`absolute top-3 left-3 w-6 h-6 rounded-md border-2 flex items-center justify-center transition-all ${
                  selectedIds.has(mon.id) ? 'bg-primary border-primary' : 'bg-background/80 border-border'
                }`}>
                  {selectedIds.has(mon.id) && (
                    <svg className="w-4 h-4 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
              </motion.button>
            ))}
          </div>
        )}

        <div className="flex justify-end mt-6 pt-4 border-t border-border/50">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg hover:bg-muted/60 transition-all mr-2">
            Cancel
          </button>
          <motion.button
            onClick={() => onSelect(Array.from(selectedIds))}
            disabled={selectedIds.size === 0}
            className="px-4 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            Confirm Selection
          </motion.button>
        </div>
      </motion.div>
    </motion.div>
  )
}
