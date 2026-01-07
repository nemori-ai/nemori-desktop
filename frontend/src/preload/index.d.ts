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

interface CustomAPI {
  window: WindowAPI
  shell: ShellAPI
  app: AppAPI
  backend: BackendAPI
  on: (channel: string, callback: (...args: any[]) => void) => void
  off: (channel: string, callback: (...args: any[]) => void) => void
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: CustomAPI
  }
}
