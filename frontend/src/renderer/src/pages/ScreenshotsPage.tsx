import { useState, useEffect, useRef } from 'react'
import { Camera, CameraOff, Trash2, RefreshCw, X, Monitor, ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { api, Screenshot, CaptureStatus } from '../services/api'
import { formatDateDisplay, getTodayDateStr } from '../utils/file'

// Cache for blob URLs to avoid re-fetching
const blobUrlCache = new Map<string, string>()

export default function ScreenshotsPage(): JSX.Element {
  const [screenshots, setScreenshots] = useState<Screenshot[]>([])
  const [captureStatus, setCaptureStatus] = useState<CaptureStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedScreenshot, setSelectedScreenshot] = useState<Screenshot | null>(null)
  const [showMonitorPicker, setShowMonitorPicker] = useState(false)
  const [monitorPreviews, setMonitorPreviews] = useState<Record<number, string>>({})
  const [loadingPreviews, setLoadingPreviews] = useState(false)

  // Date-based loading state
  const [availableDates, setAvailableDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState<string>('')
  const loadingDateRef = useRef<string>('')

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
        await loadScreenshotsByDateSafe(dateToLoad)
      } catch (error) {
        console.error('Failed to initialize:', error)
        // Fallback to today
        const today = getTodayDateStr()
        loadingDateRef.current = today
        setSelectedDate(today)
        await loadScreenshotsByDateSafe(today)
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
    loadScreenshotsByDateSafe(selectedDate)
  }, [selectedDate])

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

  // Safe screenshot loading that prevents race conditions
  const loadScreenshotsByDateSafe = async (date: string): Promise<void> => {
    // Track which date we're loading
    loadingDateRef.current = date
    setIsLoading(true)

    try {
      const { screenshots: data } = await api.getScreenshotsByDate(date)

      // Only update state if this is still the date we want
      if (loadingDateRef.current === date) {
        setScreenshots(data)
      }
    } catch (error) {
      console.error('Failed to load screenshots:', error)
      // Only clear if this is still the date we want
      if (loadingDateRef.current === date) {
        setScreenshots([])
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
      loadScreenshotsByDateSafe(selectedDate),
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
      const { success, screenshot } = await api.captureNow()
      if (success && screenshot) {
        // If viewing today, add the new screenshot
        if (selectedDate === getTodayDateStr()) {
          setScreenshots((prev) => [screenshot, ...prev])
        }
        // Refresh dates in case this is the first screenshot of the day
        loadAvailableDates()
      }
    } catch (error) {
      console.error('Failed to capture:', error)
    }
  }

  const handleDelete = async (id: string): Promise<void> => {
    try {
      await api.deleteScreenshot(id)
      setScreenshots((prev) => prev.filter((s) => s.id !== id))
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
          const blob = await api.getMonitorPreview(mon.id)
          previews[mon.id] = URL.createObjectURL(blob)
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
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted hover:bg-muted/80 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleCaptureNow}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-muted hover:bg-muted/80 transition-colors"
          >
            <Camera className="w-4 h-4" />
            <span>Capture Now</span>
          </button>
          <button
            onClick={handleToggleCapture}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
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

      {/* Date navigator and status bar */}
      <div className="flex items-center gap-4 mb-6 p-3 rounded-lg bg-muted/50">
        {/* Date navigator */}
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-muted-foreground" />
          <button
            onClick={() => navigateDate('prev')}
            disabled={!hasPrevDate}
            className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm font-medium min-w-[100px] text-center">
            {formatDateDisplay(selectedDate)}
          </span>
          <button
            onClick={() => navigateDate('next')}
            disabled={!hasNextDate}
            className="p-1 rounded hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        <div className="h-4 w-px bg-border" />

        {/* Capture status */}
        {captureStatus && (
          <>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  captureStatus.is_capturing ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
                }`}
              />
              <span className="text-sm">
                {captureStatus.is_capturing ? 'Capturing' : 'Stopped'}
              </span>
            </div>
            <span className="text-sm text-muted-foreground">
              {screenshots.length} screenshots
            </span>

            {/* Monitor selector */}
            {captureStatus.monitors && captureStatus.monitors.length > 1 && (
              <button
                onClick={openMonitorPicker}
                className="flex items-center gap-2 ml-auto px-3 py-1.5 rounded-md bg-background border border-input hover:bg-muted transition-colors"
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
      className="group relative rounded-lg border border-border overflow-hidden bg-card hover:shadow-md transition-shadow cursor-pointer"
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
      className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="relative max-w-[90vw] max-h-[90vh] bg-card rounded-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-2 right-2 flex gap-2 z-10">
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-black/50 text-white hover:bg-black/70 transition-colors"
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
        <div className="p-4 border-t border-border">
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
      className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-lg p-6 max-w-4xl w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold">Select Screen to Capture</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-muted transition-colors"
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
                className={`relative rounded-lg border-2 overflow-hidden transition-all hover:shadow-lg ${
                  captureStatus.selected_monitor === mon.id
                    ? 'border-primary ring-2 ring-primary/30'
                    : 'border-border hover:border-primary/50'
                }`}
              >
                <div className="aspect-video bg-muted">
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
                <div className="p-3 text-left">
                  <p className="font-medium text-sm">{mon.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {mon.width} x {mon.height}
                  </p>
                </div>
                {captureStatus.selected_monitor === mon.id && (
                  <div className="absolute top-2 right-2 bg-primary text-primary-foreground text-xs px-2 py-1 rounded-full">
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
