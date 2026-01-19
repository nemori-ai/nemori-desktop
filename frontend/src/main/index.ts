import { app, shell, BrowserWindow, ipcMain, screen, Menu } from 'electron'
import { join } from 'path'
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'
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
let petWindow: BrowserWindow | null = null
let trayService: TrayService | null = null
let backendService: BackendService | null = null
let screenshotService: ScreenshotService | null = null

// Simple file-based store for persisting pet position
const petConfigPath = (): string => join(app.getPath('userData'), 'pet-config.json')

function getPetConfig(): { petPosition: { x: number; y: number } | null } {
  try {
    const configPath = petConfigPath()
    if (existsSync(configPath)) {
      return JSON.parse(readFileSync(configPath, 'utf-8'))
    }
  } catch (e) {
    console.error('Failed to read pet config:', e)
  }
  return { petPosition: null }
}

function savePetConfig(config: { petPosition: { x: number; y: number } | null }): void {
  try {
    const configPath = petConfigPath()
    const dir = join(app.getPath('userData'))
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }
    writeFileSync(configPath, JSON.stringify(config, null, 2))
  } catch (e) {
    console.error('Failed to save pet config:', e)
  }
}

// Create desktop pet window
function createPetWindow(): void {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.focus()
    return
  }

  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize
  const savedPosition = getPetConfig().petPosition

  // Default position: bottom right corner
  const defaultX = screenWidth - 200
  const defaultY = screenHeight - 250

  petWindow = new BrowserWindow({
    width: 140,
    height: 160,
    x: savedPosition?.x ?? defaultX,
    y: savedPosition?.y ?? defaultY,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    focusable: true,
    // Higher level to stay above fullscreen apps
    ...(process.platform === 'darwin' ? {
      type: 'panel' // macOS: panel windows float above other apps
    } : {}),
    // macOS specific for better transparency
    ...(process.platform === 'darwin' ? {
      vibrancy: undefined,
      visualEffectState: 'active',
      backgroundColor: '#00000000'
    } : {
      backgroundColor: '#00000000'
    }),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  // Load pet page
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    petWindow.loadURL(`${process.env['ELECTRON_RENDERER_URL']}#/pet`)
  } else {
    petWindow.loadFile(join(__dirname, '../renderer/index.html'), { hash: '/pet' })
  }

  // Set to float above fullscreen apps (macOS)
  if (process.platform === 'darwin') {
    petWindow.setAlwaysOnTop(true, 'screen-saver')
    petWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  }

  // Save position when window is moved
  petWindow.on('moved', () => {
    if (petWindow && !petWindow.isDestroyed()) {
      const [x, y] = petWindow.getPosition()
      savePetConfig({ petPosition: { x, y } })
    }
  })

  petWindow.on('closed', () => {
    petWindow = null
    // Notify main window that pet was closed
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('pet-status-changed', false)
    }
  })

  // Right-click context menu - friendly language
  petWindow.webContents.on('context-menu', () => {
    const isCapturing = screenshotService?.getCaptureStatus()?.isCapturing ?? false

    const contextMenu = Menu.buildFromTemplate([
      {
        label: '📖 我的日记 / My Journal',
        click: () => {
          if (mainWindow) {
            mainWindow.show()
            mainWindow.webContents.send('navigate', '/screenshots')
          }
        }
      },
      {
        label: '💬 和我聊天 / Talk with Me',
        click: () => {
          if (mainWindow) {
            mainWindow.show()
            mainWindow.webContents.send('navigate', '/chat')
          }
        }
      },
      {
        label: '💡 我学到的 / What I Learned',
        click: () => {
          if (mainWindow) {
            mainWindow.show()
            mainWindow.webContents.send('navigate', '/insights')
          }
        }
      },
      { type: 'separator' },
      {
        label: isCapturing ? '⏸ 暂停记录 / Pause' : '▶ 开始记录 / Start',
        click: async () => {
          if (isCapturing) {
            await screenshotService?.stopCapture()
          } else {
            await screenshotService?.startCapture()
          }
          // Notify pet window of state change
          petWindow?.webContents.send('capture-status-changed', !isCapturing)
        }
      },
      { type: 'separator' },
      {
        label: '🏠 打开 Nemori / Open',
        click: () => {
          if (mainWindow) {
            mainWindow.show()
            mainWindow.focus()
          }
        }
      },
      {
        label: '👋 收起 / Dismiss',
        click: () => {
          closePetWindow()
        }
      }
    ])

    contextMenu.popup({ window: petWindow! })
  })
}

function closePetWindow(): void {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.close()
    petWindow = null
  }
}

function isPetWindowOpen(): boolean {
  return petWindow !== null && !petWindow.isDestroyed()
}

function createWindow(): void {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize

  mainWindow = new BrowserWindow({
    width: Math.min(1600, Math.max(1400, Math.round(screenWidth * 0.9))),
    height: Math.min(1000, Math.max(850, Math.round(screenHeight * 0.9))),
    minWidth: 1100,
    minHeight: 750,
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    backgroundColor: '#FDFCF9', // Light theme default, actual theme is managed by renderer
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

  ipcMain.handle('screenshot:setMonitors', (_event, monitorIds: string[]) => {
    screenshotService?.setSelectedMonitors(monitorIds)
    return true
  })

  ipcMain.handle('screenshot:getSelectedMonitor', () => {
    return screenshotService?.getSelectedMonitor()
  })

  ipcMain.handle('screenshot:getSelectedMonitors', () => {
    return screenshotService?.getSelectedMonitors()
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

  // Pet window handlers
  ipcMain.handle('pet:summon', () => {
    createPetWindow()
    return true
  })

  ipcMain.handle('pet:close', () => {
    closePetWindow()
    return true
  })

  ipcMain.handle('pet:toggle', () => {
    if (isPetWindowOpen()) {
      closePetWindow()
    } else {
      createPetWindow()
    }
    return isPetWindowOpen()
  })

  ipcMain.handle('pet:isOpen', () => {
    return isPetWindowOpen()
  })

  // Pet window movement (for dragging)
  ipcMain.on('pet:move', (_, deltaX: number, deltaY: number) => {
    if (petWindow && !petWindow.isDestroyed()) {
      const [x, y] = petWindow.getPosition()
      petWindow.setPosition(x + deltaX, y + deltaY)
    }
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
    // Show error dialog with helpful instructions
    const { dialog } = require('electron')
    const isMac = process.platform === 'darwin'
    const message = isMac
      ? 'Failed to start the Nemori backend service.\n\n' +
        'This is usually caused by macOS security restrictions.\n\n' +
        'Please run this command in Terminal:\n\n' +
        'xattr -cr /Applications/Nemori.app\n\n' +
        'Then restart Nemori.'
      : 'Failed to start the Nemori backend service. Please check the logs and try again.'
    dialog.showErrorBox('Backend Start Failed', message)
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
