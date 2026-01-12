import { app, shell, BrowserWindow, ipcMain, screen, nativeTheme, systemPreferences } from 'electron'
import { join } from 'path'
import icon from '../../resources/icon.png?asset'
import { BackendService } from './services/BackendService'
import { TrayService } from './services/TrayService'
import { ScreenshotService } from './services/ScreenshotService'

// Replace @electron-toolkit/utils with native implementations
// Use getter to delay app.isPackaged check until electron is ready
const is = {
  get dev(): boolean {
    return process.env.NODE_ENV === 'development' || !app.isPackaged
  }
}

const electronApp = {
  setAppUserModelId(id: string): void {
    if (process.platform === 'win32') {
      app.setAppUserModelId(is.dev ? process.execPath : id)
    }
  }
}

const optimizer = {
  watchWindowShortcuts(window: BrowserWindow): void {
    window.webContents.on('before-input-event', (event, input) => {
      if (input.type === 'keyDown') {
        // Only enable dev shortcuts in development mode
        if (is.dev) {
          // F12 to toggle DevTools
          if (input.key === 'F12') {
            window.webContents.toggleDevTools()
            event.preventDefault()
          }
          // Ctrl+R / Cmd+R to reload
          if (input.key === 'r' && (input.control || input.meta)) {
            window.webContents.reload()
            event.preventDefault()
          }
          // Ctrl+Shift+I / Cmd+Option+I to open DevTools
          if (input.key === 'i' && (input.control || input.meta) && input.shift) {
            window.webContents.toggleDevTools()
            event.preventDefault()
          }
        } else {
          // In production, block all DevTools shortcuts
          if (
            input.key === 'F12' ||
            (input.key === 'i' && (input.control || input.meta) && input.shift) ||
            (input.key === 'I' && (input.control || input.meta) && input.shift)
          ) {
            event.preventDefault()
          }
        }
      }
    })
  }
}

let mainWindow: BrowserWindow | null = null
let trayService: TrayService | null = null
let backendService: BackendService | null = null
let screenshotService: ScreenshotService | null = null

function createWindow(): void {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize

  mainWindow = new BrowserWindow({
    width: Math.min(1400, Math.max(1200, screenWidth * 0.85)),
    height: Math.min(900, Math.max(750, screenHeight * 0.85)),
    minWidth: 1000,
    minHeight: 700,
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#1a1a1a' : '#ffffff',
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: true
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // Disable DevTools in production
  if (!is.dev) {
    mainWindow.webContents.on('devtools-opened', () => {
      mainWindow?.webContents.closeDevTools()
    })
  }

  // HMR for renderer base on electron-vite cli
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  // Open DevTools in development
  if (is.dev) {
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// Setup IPC handlers for window controls
function setupIpcHandlers(): void {
  // Window controls
  ipcMain.handle('window:minimize', (event) => {
    BrowserWindow.fromWebContents(event.sender)?.minimize()
  })

  ipcMain.handle('window:maximize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (win?.isMaximized()) {
      win.unmaximize()
    } else {
      win?.maximize()
    }
    return win?.isMaximized()
  })

  ipcMain.handle('window:close', (event) => {
    BrowserWindow.fromWebContents(event.sender)?.close()
  })

  ipcMain.handle('window:isMaximized', (event) => {
    return BrowserWindow.fromWebContents(event.sender)?.isMaximized()
  })

  // Shell operations
  ipcMain.handle('shell:openExternal', (_event, url: string) => {
    return shell.openExternal(url)
  })

  // App info
  ipcMain.handle('app:getVersion', () => {
    return app.getVersion()
  })

  ipcMain.handle('app:getPath', (_event, name: string) => {
    return app.getPath(name as any)
  })

  // Backend service
  ipcMain.handle('backend:getUrl', () => {
    if (!backendService) {
      throw new Error('Backend service not initialized')
    }
    return backendService.getUrl()
  })

  ipcMain.handle('backend:isRunning', () => {
    return backendService?.isRunning() || false
  })

  ipcMain.handle('backend:restart', async () => {
    await backendService?.stop()
    await backendService?.start()
    return backendService?.isRunning()
  })

  // Screenshot service handlers
  ipcMain.handle('screenshot:checkPermission', () => {
    return screenshotService?.checkPermission() || { granted: false, canRequest: false }
  })

  ipcMain.handle('screenshot:getMonitors', async () => {
    return (await screenshotService?.getMonitors()) || []
  })

  ipcMain.handle('screenshot:getPreview', async (_event, monitorId: string) => {
    return await screenshotService?.getMonitorPreview(monitorId)
  })

  ipcMain.handle('screenshot:setMonitor', (_event, monitorId: string) => {
    screenshotService?.setSelectedMonitor(monitorId)
    return true
  })

  ipcMain.handle('screenshot:getSelectedMonitor', () => {
    return screenshotService?.getSelectedMonitor()
  })

  ipcMain.handle('screenshot:capture', async () => {
    return await screenshotService?.capture()
  })

  ipcMain.handle('screenshot:openPermissionSettings', () => {
    if (process.platform === 'darwin') {
      shell.openExternal(
        'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'
      )
    }
    return true
  })

  ipcMain.handle('screenshot:startCapture', async (_event, intervalMs?: number) => {
    // Backend URL is now dynamically retrieved via getter function
    return await screenshotService?.startCapture(intervalMs)
  })

  ipcMain.handle('screenshot:stopCapture', () => {
    return screenshotService?.stopCapture()
  })

  ipcMain.handle('screenshot:getCaptureStatus', () => {
    return screenshotService?.getCaptureStatus()
  })

  console.log('IPC handlers registered')
}

app.whenReady().then(async () => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.fellou.nemori')

  // Default open or close DevTools by F12 in development
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Setup IPC handlers
  setupIpcHandlers()

  // Start Python backend first (to get dynamic port)
  backendService = new BackendService()
  const backendStarted = await backendService.start()

  if (!backendStarted) {
    console.error('Failed to start backend service')
    // Show error dialog and quit
    const { dialog } = require('electron')
    dialog.showErrorBox(
      'Backend Start Failed',
      'Failed to start the Nemori backend service. Please check the logs and try again.'
    )
    app.quit()
    return
  }

  console.log('Backend service started at', backendService.getUrl())

  // Initialize screenshot service with dynamic URL getter
  // This ensures ScreenshotService always uses the current backend port
  screenshotService = new ScreenshotService(() => {
    if (!backendService) {
      throw new Error('Backend service not initialized')
    }
    return backendService.getUrl()
  })
  console.log('Screenshot service initialized')

  // Create window
  createWindow()

  // Create tray
  trayService = new TrayService(mainWindow)

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// Cleanup on quit
app.on('before-quit', async () => {
  console.log('Shutting down...')
  await backendService?.stop()
  trayService?.destroy()
})

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error)
})

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled rejection at:', promise, 'reason:', reason)
})

export { mainWindow }
