import { Tray, Menu, nativeImage, BrowserWindow, app } from 'electron'
import { join } from 'path'

export class TrayService {
  private tray: Tray | null = null
  private mainWindow: BrowserWindow | null = null

  constructor(mainWindow: BrowserWindow | null) {
    this.mainWindow = mainWindow
    this.createTray()
  }

  private createTray(): void {
    // Create tray icon
    const iconPath = join(__dirname, '../../resources/icon.png')
    let trayIcon: Electron.NativeImage

    try {
      trayIcon = nativeImage.createFromPath(iconPath)
      // Resize for tray
      trayIcon = trayIcon.resize({ width: 16, height: 16 })
    } catch {
      // Create a simple icon if file not found
      trayIcon = nativeImage.createEmpty()
    }

    this.tray = new Tray(trayIcon)
    this.tray.setToolTip('Nemori - AI Memory Assistant')

    this.updateContextMenu()

    // Show window on click (macOS)
    this.tray.on('click', () => {
      this.showWindow()
    })
  }

  private updateContextMenu(): void {
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Show Nemori',
        click: () => this.showWindow()
      },
      { type: 'separator' },
      {
        label: 'New Chat',
        click: () => {
          this.showWindow()
          this.mainWindow?.webContents.send('navigate', '/chat')
        }
      },
      {
        label: 'View Memories',
        click: () => {
          this.showWindow()
          this.mainWindow?.webContents.send('navigate', '/memories')
        }
      },
      { type: 'separator' },
      {
        label: 'Settings',
        click: () => {
          this.showWindow()
          this.mainWindow?.webContents.send('navigate', '/settings')
        }
      },
      { type: 'separator' },
      {
        label: 'Quit Nemori',
        click: () => {
          app.quit()
        }
      }
    ])

    this.tray?.setContextMenu(contextMenu)
  }

  private showWindow(): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      if (this.mainWindow.isMinimized()) {
        this.mainWindow.restore()
      }
      this.mainWindow.show()
      this.mainWindow.focus()
    }
  }

  public setMainWindow(window: BrowserWindow): void {
    this.mainWindow = window
  }

  public destroy(): void {
    if (this.tray) {
      this.tray.destroy()
      this.tray = null
    }
  }
}
