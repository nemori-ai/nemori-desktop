import { desktopCapturer, screen, systemPreferences, app } from 'electron'
import http from 'http'
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'

export interface MonitorInfo {
  id: string
  name: string
  width: number
  height: number
  x: number
  y: number
  selected?: boolean // Whether this monitor is selected for capture
}

export interface CaptureResult {
  success: boolean
  imageData?: string // Base64 encoded PNG
  monitorId?: string
  error?: string
}

// Saved monitor preference - use display properties for matching instead of dynamic IDs
interface SavedMonitorPreference {
  name: string
  width: number
  height: number
  x: number
  y: number
}

const MONITOR_PREFS_FILE = 'monitor_preferences.json'

export class ScreenshotService {
  // Support multiple selected monitors for independent capture
  private selectedMonitorIds: Set<string> = new Set()
  private captureInterval: NodeJS.Timeout | null = null
  private isCapturing: boolean = false
  private intervalMs: number = 10000
  private getBackendUrl: () => string
  private prefsPath: string

  /**
   * Create a ScreenshotService with a dynamic backend URL getter
   * @param getBackendUrl - Function that returns the current backend URL (required)
   */
  constructor(getBackendUrl: () => string) {
    // Dynamic getter is required to ensure correct port is used
    this.getBackendUrl = getBackendUrl
    // Store preferences in user data directory
    this.prefsPath = join(app.getPath('userData'), MONITOR_PREFS_FILE)
    // Load saved preferences on startup
    this.loadMonitorPreferences()
  }

  /**
   * Save monitor preferences to disk
   * Uses monitor properties (not IDs) since IDs change between sessions
   */
  private async saveMonitorPreferences(): Promise<void> {
    try {
      const monitors = await this.getMonitors()
      const selectedMonitors = monitors.filter(m => this.selectedMonitorIds.has(m.id))

      // Save monitor properties that can be matched later
      const preferences: SavedMonitorPreference[] = selectedMonitors.map(m => ({
        name: m.name,
        width: m.width,
        height: m.height,
        x: m.x,
        y: m.y
      }))

      // Ensure directory exists
      const dir = dirname(this.prefsPath)
      if (!existsSync(dir)) {
        mkdirSync(dir, { recursive: true })
      }

      writeFileSync(this.prefsPath, JSON.stringify(preferences, null, 2))
      console.log(`Monitor preferences saved: ${preferences.length} monitor(s)`)
    } catch (error) {
      console.error('Failed to save monitor preferences:', error)
    }
  }

  /**
   * Load monitor preferences from disk and match with current monitors
   */
  private async loadMonitorPreferences(): Promise<void> {
    try {
      if (!existsSync(this.prefsPath)) {
        console.log('No saved monitor preferences found')
        return
      }

      const data = readFileSync(this.prefsPath, 'utf-8')
      const savedPrefs: SavedMonitorPreference[] = JSON.parse(data)

      if (!savedPrefs || savedPrefs.length === 0) {
        return
      }

      // Get current monitors
      const currentMonitors = await this.getMonitors()

      // Match saved preferences with current monitors by properties
      const matchedIds: string[] = []
      for (const pref of savedPrefs) {
        const match = currentMonitors.find(m =>
          m.width === pref.width &&
          m.height === pref.height &&
          m.x === pref.x &&
          m.y === pref.y
        )
        if (match) {
          matchedIds.push(match.id)
          console.log(`Matched saved monitor: ${pref.name} -> ${match.id}`)
        } else {
          console.log(`Could not match saved monitor: ${pref.name} (${pref.width}x${pref.height} at ${pref.x},${pref.y})`)
        }
      }

      if (matchedIds.length > 0) {
        this.selectedMonitorIds = new Set(matchedIds)
        console.log(`Restored ${matchedIds.length} monitor selection(s) from preferences`)
      }
    } catch (error) {
      console.error('Failed to load monitor preferences:', error)
    }
  }

  /**
   * Set the backend URL getter (for compatibility)
   * @deprecated Use constructor parameter instead
   */
  setBackendUrl(url: string): void {
    this.getBackendUrl = () => url
  }

  /**
   * Check if screen recording permission is granted (macOS only)
   */
  checkPermission(): { granted: boolean; canRequest: boolean } {
    if (process.platform !== 'darwin') {
      return { granted: true, canRequest: false }
    }

    const status = systemPreferences.getMediaAccessStatus('screen')
    return {
      granted: status === 'granted',
      canRequest: status === 'not-determined'
    }
  }

  /**
   * Get list of available monitors/screens
   * Each monitor can be independently selected for capture
   */
  async getMonitors(): Promise<MonitorInfo[]> {
    const displays = screen.getAllDisplays()
    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width: 320, height: 180 }
    })

    const monitors: MonitorInfo[] = []
    const primaryDisplay = screen.getPrimaryDisplay()
    const hasSelection = this.selectedMonitorIds.size > 0

    // Add individual screens (no "All Screens" option - each screen is captured independently)
    for (const source of sources) {
      const display = displays.find((d) => source.display_id === String(d.id))
      const isPrimary = display?.id === primaryDisplay.id

      // If user has saved preferences, use those; otherwise default to primary screen
      const isSelected = hasSelection
        ? this.selectedMonitorIds.has(source.id)
        : isPrimary

      if (display) {
        monitors.push({
          id: source.id,
          name: isPrimary ? 'Primary Screen' : source.name || `Screen ${monitors.length + 1}`,
          width: display.bounds.width,
          height: display.bounds.height,
          x: display.bounds.x,
          y: display.bounds.y,
          selected: isSelected
        })
      } else {
        // Fallback for screens without matching display
        monitors.push({
          id: source.id,
          name: source.name || `Screen ${monitors.length + 1}`,
          width: primaryDisplay.bounds.width,
          height: primaryDisplay.bounds.height,
          x: 0,
          y: 0,
          selected: hasSelection ? this.selectedMonitorIds.has(source.id) : monitors.length === 0
        })
      }
    }

    return monitors
  }

  /**
   * Get preview thumbnail for a specific monitor
   * Uses higher resolution (960x540) for better quality in picker UI
   */
  async getMonitorPreview(monitorId: string): Promise<string | null> {
    try {
      // Use higher resolution for better preview quality
      const previewSize = { width: 960, height: 540 }

      const sources = await desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: previewSize
      })

      const source = sources.find((s) => s.id === monitorId)
      if (source) {
        return source.thumbnail.toDataURL()
      }

      // Fallback to first source if specific monitor not found
      if (sources.length > 0) {
        return sources[0].thumbnail.toDataURL()
      }

      return null
    } catch (error) {
      console.error('Failed to get monitor preview:', error)
      return null
    }
  }

  /**
   * Set the selected monitor for capture (legacy single-select)
   */
  setSelectedMonitor(monitorId: string): void {
    this.selectedMonitorIds.clear()
    this.selectedMonitorIds.add(monitorId)
    // Save preferences when selection changes
    this.saveMonitorPreferences()
  }

  /**
   * Get currently selected monitor (legacy - returns first selected)
   */
  getSelectedMonitor(): string | null {
    return this.selectedMonitorIds.size > 0 ? Array.from(this.selectedMonitorIds)[0] : null
  }

  /**
   * Toggle monitor selection (for multi-select)
   */
  toggleMonitorSelection(monitorId: string): void {
    if (this.selectedMonitorIds.has(monitorId)) {
      this.selectedMonitorIds.delete(monitorId)
    } else {
      this.selectedMonitorIds.add(monitorId)
    }
    // Save preferences when selection changes
    this.saveMonitorPreferences()
  }

  /**
   * Set multiple monitors for capture
   */
  setSelectedMonitors(monitorIds: string[]): void {
    this.selectedMonitorIds = new Set(monitorIds)
    // Save preferences when selection changes
    this.saveMonitorPreferences()
  }

  /**
   * Get all selected monitor IDs
   */
  getSelectedMonitors(): string[] {
    return Array.from(this.selectedMonitorIds)
  }

  /**
   * Check if a monitor is selected
   */
  isMonitorSelected(monitorId: string): boolean {
    return this.selectedMonitorIds.has(monitorId)
  }

  /**
   * Capture screenshot from selected monitor (legacy - single monitor)
   */
  async capture(): Promise<CaptureResult> {
    const results = await this.captureAllSelected()
    return results.length > 0 ? results[0] : { success: false, error: 'No monitors selected' }
  }

  /**
   * Capture screenshots from all selected monitors independently
   * Each monitor is captured separately with its own deduplication channel
   */
  async captureAllSelected(): Promise<CaptureResult[]> {
    try {
      // Check permission first
      const permission = this.checkPermission()
      if (!permission.granted) {
        return [{ success: false, error: 'Screen recording permission not granted' }]
      }

      // Get full resolution screenshots
      const sources = await desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: { width: 3840, height: 2160 } // 4K max
      })

      if (sources.length === 0) {
        return [{ success: false, error: 'No screens available' }]
      }

      // If no monitors selected, select all by default
      if (this.selectedMonitorIds.size === 0) {
        sources.forEach((s) => this.selectedMonitorIds.add(s.id))
      }

      const results: CaptureResult[] = []

      // Capture each selected monitor independently
      for (const source of sources) {
        if (this.selectedMonitorIds.has(source.id)) {
          const imageData = source.thumbnail.toPNG().toString('base64')
          results.push({
            success: true,
            imageData,
            monitorId: source.id
          })
        }
      }

      return results.length > 0 ? results : [{ success: false, error: 'No selected monitors found' }]
    } catch (error) {
      console.error('Screenshot capture failed:', error)
      return [{ success: false, error: error instanceof Error ? error.message : 'Unknown error' }]
    }
  }

  /**
   * Start automatic screenshot capture
   */
  async startCapture(intervalMs?: number): Promise<boolean> {
    if (this.isCapturing) {
      return true
    }

    if (intervalMs) {
      this.intervalMs = intervalMs
    }

    // Check permission first
    const permission = this.checkPermission()
    if (!permission.granted) {
      console.error('Cannot start capture: permission not granted')
      return false
    }

    this.isCapturing = true

    // Capture immediately on start (non-blocking)
    console.log('Capturing first screenshot immediately...')
    this.captureAndUpload().catch((err) => console.error('First capture failed:', err))

    // Then set up interval for subsequent captures
    this.captureInterval = setInterval(async () => {
      await this.captureAndUpload()
    }, this.intervalMs)

    console.log(`Screenshot capture started with interval ${this.intervalMs}ms`)
    return true
  }

  /**
   * Stop automatic screenshot capture
   */
  stopCapture(): boolean {
    if (!this.isCapturing) {
      return true
    }

    if (this.captureInterval) {
      clearInterval(this.captureInterval)
      this.captureInterval = null
    }

    this.isCapturing = false
    console.log('Screenshot capture stopped')
    return true
  }

  /**
   * Get capture status
   */
  getCaptureStatus(): { isCapturing: boolean; intervalMs: number } {
    return {
      isCapturing: this.isCapturing,
      intervalMs: this.intervalMs
    }
  }

  /**
   * Capture and upload to backend
   * Captures all selected monitors and uploads each independently
   * Each monitor has its own deduplication channel on the backend
   */
  private async captureAndUpload(): Promise<void> {
    try {
      console.log('Starting capture for all selected monitors...')
      const results = await this.captureAllSelected()

      let uploadedCount = 0
      for (const result of results) {
        if (!result.success || !result.imageData) {
          console.log(`Capture skipped for monitor ${result.monitorId}:`, result.error)
          continue
        }

        console.log(
          `Captured screenshot from monitor ${result.monitorId} (${result.imageData.length} bytes), uploading...`
        )
        // Upload to backend with monitor_id for per-monitor deduplication
        await this.uploadToBackend(result.imageData, result.monitorId)
        uploadedCount++
      }

      if (uploadedCount > 0) {
        console.log(`${uploadedCount} screenshot(s) uploaded successfully`)
      }
    } catch (error) {
      console.error('Capture and upload failed:', error)
    }
  }

  /**
   * Upload screenshot to backend
   */
  private uploadToBackend(imageData: string, monitorId?: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const data = JSON.stringify({
        image_data: imageData,
        monitor_id: monitorId
      })

      // Get the current backend URL dynamically
      const backendUrl = this.getBackendUrl()
      console.log(`Uploading to backend: ${backendUrl}/api/screenshots/upload`)

      const url = new URL(backendUrl)
      const options = {
        hostname: url.hostname,
        port: url.port || 80,
        path: '/api/screenshots/upload',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(data)
        }
      }

      const req = http.request(options, (res) => {
        let responseData = ''
        res.on('data', (chunk) => {
          responseData += chunk
        })
        res.on('end', () => {
          if (res.statusCode === 200) {
            console.log('Backend response:', responseData)
            resolve()
          } else {
            console.error(`Upload failed with status ${res.statusCode}:`, responseData)
            reject(new Error(`Upload failed with status ${res.statusCode}: ${responseData}`))
          }
        })
      })

      req.on('error', (error) => {
        console.error('HTTP request error:', error)
        reject(error)
      })

      req.write(data)
      req.end()
    })
  }
}
