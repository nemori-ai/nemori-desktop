import { desktopCapturer, screen, systemPreferences } from 'electron'
import http from 'http'

export interface MonitorInfo {
  id: string
  name: string
  width: number
  height: number
  x: number
  y: number
}

export interface CaptureResult {
  success: boolean
  imageData?: string // Base64 encoded PNG
  monitorId?: string
  error?: string
}

export class ScreenshotService {
  private selectedMonitorId: string | null = null
  private captureInterval: NodeJS.Timeout | null = null
  private isCapturing: boolean = false
  private intervalMs: number = 10000
  private getBackendUrl: () => string

  /**
   * Create a ScreenshotService with a dynamic backend URL getter
   * @param getBackendUrl - Function that returns the current backend URL
   */
  constructor(getBackendUrl?: () => string) {
    // Default to development port, but should be overridden with dynamic getter
    this.getBackendUrl = getBackendUrl || (() => 'http://127.0.0.1:21978')
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
   */
  async getMonitors(): Promise<MonitorInfo[]> {
    const displays = screen.getAllDisplays()
    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width: 320, height: 180 }
    })

    const monitors: MonitorInfo[] = []

    // Add "All Screens" option
    const primaryDisplay = screen.getPrimaryDisplay()
    const allBounds = displays.reduce(
      (acc, d) => ({
        width: Math.max(acc.width, d.bounds.x + d.bounds.width),
        height: Math.max(acc.height, d.bounds.y + d.bounds.height)
      }),
      { width: 0, height: 0 }
    )

    monitors.push({
      id: 'all',
      name: 'All Screens',
      width: allBounds.width,
      height: allBounds.height,
      x: 0,
      y: 0
    })

    // Add individual screens
    for (const source of sources) {
      const display = displays.find((d) => source.display_id === String(d.id))
      if (display) {
        monitors.push({
          id: source.id,
          name: source.name || `Screen ${monitors.length}`,
          width: display.bounds.width,
          height: display.bounds.height,
          x: display.bounds.x,
          y: display.bounds.y
        })
      } else {
        // Fallback for screens without matching display
        monitors.push({
          id: source.id,
          name: source.name || `Screen ${monitors.length}`,
          width: primaryDisplay.bounds.width,
          height: primaryDisplay.bounds.height,
          x: 0,
          y: 0
        })
      }
    }

    return monitors
  }

  /**
   * Get preview thumbnail for a specific monitor
   */
  async getMonitorPreview(monitorId: string): Promise<string | null> {
    try {
      if (monitorId === 'all') {
        // For "all screens", capture primary and resize
        const sources = await desktopCapturer.getSources({
          types: ['screen'],
          thumbnailSize: { width: 320, height: 180 }
        })
        if (sources.length > 0) {
          return sources[0].thumbnail.toDataURL()
        }
        return null
      }

      const sources = await desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: { width: 320, height: 180 }
      })

      const source = sources.find((s) => s.id === monitorId)
      if (source) {
        return source.thumbnail.toDataURL()
      }

      return null
    } catch (error) {
      console.error('Failed to get monitor preview:', error)
      return null
    }
  }

  /**
   * Set the selected monitor for capture
   */
  setSelectedMonitor(monitorId: string): void {
    this.selectedMonitorId = monitorId
  }

  /**
   * Get currently selected monitor
   */
  getSelectedMonitor(): string | null {
    return this.selectedMonitorId
  }

  /**
   * Capture screenshot from selected monitor
   */
  async capture(): Promise<CaptureResult> {
    try {
      // Check permission first
      const permission = this.checkPermission()
      if (!permission.granted) {
        return {
          success: false,
          error: 'Screen recording permission not granted'
        }
      }

      const sources = await desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: { width: 1920, height: 1080 },
        fetchWindowIcons: false
      })

      if (sources.length === 0) {
        return {
          success: false,
          error: 'No screens available'
        }
      }

      let targetSource = sources[0]

      // If a specific monitor is selected, find it
      if (this.selectedMonitorId && this.selectedMonitorId !== 'all') {
        const found = sources.find((s) => s.id === this.selectedMonitorId)
        if (found) {
          targetSource = found
        }
      }

      // Get full resolution screenshot
      const fullSources = await desktopCapturer.getSources({
        types: ['screen'],
        thumbnailSize: { width: 3840, height: 2160 } // 4K max
      })

      const fullSource = fullSources.find((s) => s.id === targetSource.id) || fullSources[0]
      const imageData = fullSource.thumbnail.toPNG().toString('base64')

      return {
        success: true,
        imageData,
        monitorId: targetSource.id
      }
    } catch (error) {
      console.error('Screenshot capture failed:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      }
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
   */
  private async captureAndUpload(): Promise<void> {
    try {
      console.log('Starting capture...')
      const result = await this.capture()
      if (!result.success || !result.imageData) {
        console.log('Capture skipped:', result.error)
        return
      }

      console.log(`Captured screenshot (${result.imageData.length} bytes), uploading to backend...`)
      // Upload to backend
      await this.uploadToBackend(result.imageData, result.monitorId)
      console.log('Screenshot uploaded successfully')
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
