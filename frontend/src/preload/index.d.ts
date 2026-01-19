import { ElectronAPI } from '@electron-toolkit/preload'

interface WindowAPI {
  minimize: () => Promise<void>
  maximize: () => Promise<boolean>
  close: () => Promise<void>
  isMaximized: () => Promise<boolean>
}

interface ShellAPI {
  openExternal: (url: string) => Promise<void>
}

interface AppAPI {
  getVersion: () => Promise<string>
  getPath: (name: string) => Promise<string>
}

interface BackendAPI {
  getUrl: () => Promise<string>
  isRunning: () => Promise<boolean>
  restart: () => Promise<boolean>
}

interface ScreenshotPermission {
  granted: boolean
  canRequest: boolean
}

interface MonitorInfo {
  id: string
  name: string
  width: number
  height: number
  x: number
  y: number
}

interface CaptureResult {
  success: boolean
  imageData?: string
  monitorId?: string
  error?: string
}

interface ElectronCaptureStatus {
  isCapturing: boolean
  intervalMs: number
}

interface ScreenshotAPI {
  checkPermission: () => Promise<ScreenshotPermission>
  getMonitors: () => Promise<MonitorInfo[]>
  getPreview: (monitorId: string) => Promise<string | null>
  setMonitor: (monitorId: string) => Promise<boolean>
  setMonitors: (monitorIds: string[]) => Promise<boolean>
  getSelectedMonitor: () => Promise<string | null>
  getSelectedMonitors: () => Promise<string[]>
  capture: () => Promise<CaptureResult>
  openPermissionSettings: () => Promise<boolean>
  startCapture: (intervalMs?: number) => Promise<boolean>
  stopCapture: () => Promise<boolean>
  getCaptureStatus: () => Promise<ElectronCaptureStatus>
}

interface PetAPI {
  summon: () => Promise<boolean>
  close: () => Promise<boolean>
  toggle: () => Promise<boolean>
  isOpen: () => Promise<boolean>
  move: (deltaX: number, deltaY: number) => void
}

interface CustomAPI {
  window: WindowAPI
  shell: ShellAPI
  app: AppAPI
  backend: BackendAPI
  pet: PetAPI
  screenshot: ScreenshotAPI
  on: (channel: string, callback: (...args: any[]) => void) => void
  off: (channel: string, callback: (...args: any[]) => void) => void
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: CustomAPI
  }
}
