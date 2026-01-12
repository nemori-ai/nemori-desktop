import { useState, useEffect, useRef } from 'react'
import { Camera, CameraOff, Trash2, RefreshCw, X, Monitor, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Calendar } from 'lucide-react'
import { api, Screenshot, CaptureStatus } from '../services/api'
import { formatDateDisplay, getTodayDateStr } from '../utils/file'

// Cache for blob URLs to avoid re-fetching
const blobUrlCache = new Map<string, string>()

// Pagination config
const PAGE_SIZE = 20

export default function ScreenshotsPage(): JSX.Element {
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
        // First load available dates
        const { dates } = await api.getScreenshotDates()
        setAvailableDates(dates)

        // Determine which date to show
        const today = getTodayDateStr()
        const dateToLoad = dates.includes(today) ? today : (dates[0] || today)

        // Set the ref BEFORE setting state to prevent the second useEffect from triggering a duplicate load
        loadingDateRef.current = dateToLoad
        setSelectedDate(dateToLoad)
        setCurrentPage(1)
        await loadScreenshotsPage(dateToLoad, 1)
      } catch (error) {
        console.error('Failed to initialize:', error)
        // Fallback to today
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

  // Load screenshots when date changes (but not on initial mount)
  useEffect(() => {
    // Skip if no date selected yet (initial mount handled above)
    if (!selectedDate || loadingDateRef.current === selectedDate) {
      return
    }
    setCurrentPage(1)
    loadScreenshotsPage(selectedDate, 1)
  }, [selectedDate])

  // Load screenshots when page changes
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

  // Load screenshots with pagination
  const loadScreenshotsPage = async (date: string, page: number): Promise<void> => {
    // Track which date we're loading
    loadingDateRef.current = date
    setIsLoading(true)

    try {
      const offset = (page - 1) * PAGE_SIZE
      const { screenshots: data, total } = await api.getScreenshotsByDate(date, PAGE_SIZE, offset)

      // Only update state if this is still the date we want
      if (loadingDateRef.current === date) {
        setScreenshots(data)
        setTotalCount(total)
      }
    } catch (error) {
      console.error('Failed to load screenshots:', error)
      // Only clear if this is still the date we want
      if (loadingDateRef.current === date) {
        setScreenshots([])
        setTotalCount(0)
      }
    } finally {
      // Only clear loading if this is still the date we want
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
        // If viewing today and on first page, add the new screenshot
        if (selectedDate === getTodayDateStr() && currentPage === 1) {
          setScreenshots((prev) => [result.screenshot!, ...prev.slice(0, PAGE_SIZE - 1)])
          setTotalCount((prev) => prev + 1)
        } else if (selectedDate === getTodayDateStr()) {
          // Just update total count if not on first page
          setTotalCount((prev) => prev + 1)
        }
        // Refresh dates in case this is the first screenshot of the day
        loadAvailableDates()
      } else if (result.error) {
        // Show permission error with option to open settings
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

  const handleSelectMonitor = async (monitorId: number): Promise<void> => {
    try {
      const { selected, monitors } = await api.selectMonitor(monitorId)
      setCaptureStatus((prev) =>
        prev ? { ...prev, selected_monitor: selected, monitors } : null
      )
      setShowMonitorPicker(false)
    } catch (error) {
      console.error('Failed to select monitor:', error)
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
          // Handle both data URL string and Blob
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
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Screenshots</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Capture and manage screen activity
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-muted/60 hover:bg-muted transition-all duration-200 shadow-warm-sm"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleCaptureNow}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-muted/60 hover:bg-muted transition-all duration-200 shadow-warm-sm"
          >
            <Camera className="w-4 h-4" />
            <span>Capture Now</span>
          </button>
          <button
            onClick={handleToggleCapture}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all duration-200 shadow-warm ${
              captureStatus?.is_capturing
                ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
                : 'bg-primary text-primary-foreground hover:bg-primary/90'
            }`}
          >
            {captureStatus?.is_capturing ? (
              <>
                <CameraOff className="w-4 h-4" />
                <span>Stop</span>
              </>
            ) : (
              <>
                <Camera className="w-4 h-4" />
                <span>Start</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Permission error banner */}
      {permissionError && (
        <div className="mb-4 p-4 rounded-lg bg-destructive/10 border border-destructive/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-destructive/20 flex items-center justify-center">
              <CameraOff className="w-4 h-4 text-destructive" />
            </div>
            <div>
              <p className="text-sm font-medium text-destructive">Screen Recording Permission Required</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Please enable screen recording permission for Nemori in System Settings.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => api.openScreenshotPermissionSettings()}
              className="px-3 py-1.5 text-sm rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
            >
              Open Settings
            </button>
            <button
              onClick={() => setPermissionError(null)}
              className="p-1.5 rounded-lg hover:bg-destructive/20 transition-colors"
            >
              <X className="w-4 h-4 text-destructive" />
            </button>
          </div>
        </div>
      )}

      {/* Date navigator and status bar */}
      <div className="flex items-center gap-4 mb-6 p-4 rounded-lg glass-card">
        {/* Date navigator */}
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-muted-foreground" />
          <button
            onClick={() => navigateDate('prev')}
            disabled={!hasPrevDate}
            className="p-1.5 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm font-medium min-w-[100px] text-center">
            {formatDateDisplay(selectedDate)}
          </span>
          <button
            onClick={() => navigateDate('next')}
            disabled={!hasNextDate}
            className="p-1.5 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="h-4 w-px bg-border/50" />

        {/* Capture status */}
        {captureStatus && (
          <>
            <div className="flex items-center gap-2">
              <div
                className={`w-2.5 h-2.5 rounded-full ${
                  captureStatus.is_capturing ? 'bg-primary animate-pulse' : 'bg-muted-foreground/50'
                }`}
              />
              <span className="text-sm">
                {captureStatus.is_capturing ? 'Capturing' : 'Stopped'}
              </span>
            </div>
            <span className="text-sm text-muted-foreground">
              {totalCount} screenshots
            </span>

            {/* Monitor selector */}
            {captureStatus.monitors && captureStatus.monitors.length > 1 && (
              <button
                onClick={openMonitorPicker}
                className="flex items-center gap-2 ml-auto px-3 py-2 rounded-lg bg-background/80 border border-input/50 hover:bg-muted/60 transition-all duration-200"
              >
                <Monitor className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm">
                  {captureStatus.monitors.find((m) => m.id === captureStatus.selected_monitor)?.name ||
                    'Select Screen'}
                </span>
              </button>
            )}
          </>
        )}
      </div>

      {/* Screenshots grid */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
            </div>
          ) : screenshots.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <Camera className="w-16 h-16 mb-4 opacity-50" />
              <h2 className="text-xl font-semibold mb-2">No screenshots</h2>
              <p className="text-sm">No screenshots for {formatDateDisplay(selectedDate)}</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {screenshots.map((screenshot) => (
                <ScreenshotCard
                  key={screenshot.id}
                  screenshot={screenshot}
                  onClick={() => setSelectedScreenshot(screenshot)}
                  onDelete={() => handleDelete(screenshot.id)}
                  formatTime={formatTime}
                />
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
          />
        )}
      </div>

      {/* Image viewer modal */}
      {selectedScreenshot && (
        <ImageViewerModal
          screenshot={selectedScreenshot}
          onClose={() => setSelectedScreenshot(null)}
        />
      )}

      {/* Monitor picker modal */}
      {showMonitorPicker && (
        <MonitorPickerModal
          captureStatus={captureStatus}
          monitorPreviews={monitorPreviews}
          loadingPreviews={loadingPreviews}
          onSelect={handleSelectMonitor}
          onClose={() => setShowMonitorPicker(false)}
        />
      )}
    </div>
  )
}

// Screenshot card with blob URL loading (bypasses CSP)
function ScreenshotCard({
  screenshot,
  onClick,
  onDelete,
  formatTime
}: {
  screenshot: Screenshot
  onClick: () => void
  onDelete: () => void
  formatTime: (t: number) => string
}): JSX.Element {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const cardRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Check cache first
    const cached = blobUrlCache.get(screenshot.id)
    if (cached) {
      setBlobUrl(cached)
      setIsLoading(false)
      return
    }

    // Use IntersectionObserver for lazy loading
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
    <div
      ref={cardRef}
      className="group relative rounded-lg overflow-hidden glass-card hover:shadow-warm transition-all duration-200 cursor-pointer"
      onClick={onClick}
    >
      <div className="aspect-video bg-muted">
        {isLoading ? (
          <div className="w-full h-full flex items-center justify-center">
            <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground/50" />
          </div>
        ) : blobUrl ? (
          <img
            src={blobUrl}
            alt={screenshot.window_title || 'Screenshot'}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Camera className="w-8 h-8 text-muted-foreground/50" />
          </div>
        )}
      </div>
      <div className="p-2">
        <p className="text-xs font-medium truncate">{screenshot.window_title || 'Unknown'}</p>
        <p className="text-xs text-muted-foreground">{formatTime(screenshot.timestamp)}</p>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
        className="absolute top-2 right-2 p-1.5 rounded-full bg-black/50 text-white opacity-0 group-hover:opacity-100 hover:bg-destructive transition-all"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

// Image viewer modal with blob URL loading
function ImageViewerModal({
  screenshot,
  onClose
}: {
  screenshot: Screenshot
  onClose: () => void
}): JSX.Element {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check cache first
    const cached = blobUrlCache.get(screenshot.id)
    if (cached) {
      setBlobUrl(cached)
      setIsLoading(false)
      return
    }

    // Load image
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
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="relative max-w-[90vw] max-h-[90vh] glass-card rounded-xl overflow-hidden shadow-warm-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-3 right-3 flex gap-2 z-10">
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-black/40 text-white hover:bg-black/60 transition-all duration-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        {isLoading ? (
          <div className="w-96 h-64 flex items-center justify-center">
            <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
          </div>
        ) : blobUrl ? (
          <img
            src={blobUrl}
            alt="Screenshot"
            className="max-w-full max-h-[80vh] object-contain"
          />
        ) : (
          <div className="w-96 h-64 flex items-center justify-center">
            <Camera className="w-16 h-16 text-muted-foreground/30" />
          </div>
        )}
        <div className="p-4 border-t border-border/50 bg-background/50">
          <p className="text-sm font-medium">{screenshot.window_title || 'Unknown'}</p>
          <p className="text-xs text-muted-foreground mt-1">
            {formatDateTime(screenshot.timestamp)}
          </p>
          {screenshot.app_name && (
            <p className="text-xs text-muted-foreground">App: {screenshot.app_name}</p>
          )}
        </div>
      </div>
    </div>
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
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      pages.push(1)

      if (currentPage > 3) {
        pages.push('...')
      }

      const start = Math.max(2, currentPage - 1)
      const end = Math.min(totalPages - 1, currentPage + 1)

      for (let i = start; i <= end; i++) {
        if (!pages.includes(i)) {
          pages.push(i)
        }
      }

      if (currentPage < totalPages - 2) {
        pages.push('...')
      }

      if (!pages.includes(totalPages)) {
        pages.push(totalPages)
      }
    }

    return pages
  }

  return (
    <div className="flex items-center justify-center gap-1 py-4 mt-4 border-t border-border/50">
      <button
        onClick={() => onPageChange(1)}
        disabled={currentPage === 1}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="First page"
      >
        <ChevronsLeft className="w-4 h-4" />
      </button>

      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="Previous page"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-1 mx-2">
        {getVisiblePages().map((page, idx) =>
          typeof page === 'number' ? (
            <button
              key={idx}
              onClick={() => onPageChange(page)}
              className={`min-w-[36px] h-9 px-3 rounded-lg text-sm font-medium transition-all ${
                currentPage === page
                  ? 'bg-primary text-primary-foreground shadow-warm-sm'
                  : 'hover:bg-muted/60'
              }`}
            >
              {page}
            </button>
          ) : (
            <span key={idx} className="px-2 text-muted-foreground">
              {page}
            </span>
          )
        )}
      </div>

      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="Next page"
      >
        <ChevronRight className="w-4 h-4" />
      </button>

      <button
        onClick={() => onPageChange(totalPages)}
        disabled={currentPage === totalPages}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="Last page"
      >
        <ChevronsRight className="w-4 h-4" />
      </button>

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
  onSelect: (id: number) => void
  onClose: () => void
}): JSX.Element {
  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="glass-card rounded-xl p-6 max-w-4xl w-full mx-4 shadow-warm-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">Select Screen to Capture</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-muted/60 transition-all duration-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {loadingPreviews ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
            <span className="ml-3 text-muted-foreground">Loading previews...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {captureStatus?.monitors.map((mon) => (
              <button
                key={mon.id}
                onClick={() => onSelect(mon.id)}
                className={`relative rounded-xl border-2 overflow-hidden transition-all duration-200 hover:shadow-warm ${
                  captureStatus.selected_monitor === mon.id
                    ? 'border-primary ring-2 ring-primary/20 shadow-warm'
                    : 'border-border/50 hover:border-primary/50'
                }`}
              >
                <div className="aspect-video bg-muted/50">
                  {monitorPreviews[mon.id] ? (
                    <img
                      src={monitorPreviews[mon.id]}
                      alt={mon.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Monitor className="w-12 h-12 text-muted-foreground/30" />
                    </div>
                  )}
                </div>
                <div className="p-3 text-left bg-background/50">
                  <p className="font-medium text-sm">{mon.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {mon.width} x {mon.height}
                  </p>
                </div>
                {captureStatus.selected_monitor === mon.id && (
                  <div className="absolute top-2 right-2 bg-primary text-primary-foreground text-xs px-2.5 py-1 rounded-full shadow-warm-sm">
                    Selected
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
