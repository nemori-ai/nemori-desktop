import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
  // Window controls
  window: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized')
  },

  // Shell operations
  shell: {
    openExternal: (url: string) => ipcRenderer.invoke('shell:openExternal', url)
  },

  // App info
  app: {
    getVersion: () => ipcRenderer.invoke('app:getVersion'),
    getPath: (name: string) => ipcRenderer.invoke('app:getPath', name)
  },

  // Backend service
  backend: {
    getUrl: () => ipcRenderer.invoke('backend:getUrl'),
    isRunning: () => ipcRenderer.invoke('backend:isRunning'),
    restart: () => ipcRenderer.invoke('backend:restart')
  },

  // Screenshot service (captures from Electron main process)
  screenshot: {
    checkPermission: () =>
      ipcRenderer.invoke('screenshot:checkPermission') as Promise<{
        granted: boolean
        canRequest: boolean
      }>,
    getMonitors: () =>
      ipcRenderer.invoke('screenshot:getMonitors') as Promise<
        Array<{ id: string; name: string; width: number; height: number; x: number; y: number }>
      >,
    getPreview: (monitorId: string) =>
      ipcRenderer.invoke('screenshot:getPreview', monitorId) as Promise<string | null>,
    setMonitor: (monitorId: string) =>
      ipcRenderer.invoke('screenshot:setMonitor', monitorId) as Promise<boolean>,
    getSelectedMonitor: () =>
      ipcRenderer.invoke('screenshot:getSelectedMonitor') as Promise<string | null>,
    capture: () =>
      ipcRenderer.invoke('screenshot:capture') as Promise<{
        success: boolean
        imageData?: string
        monitorId?: string
        error?: string
      }>,
    openPermissionSettings: () => ipcRenderer.invoke('screenshot:openPermissionSettings'),
    startCapture: (intervalMs?: number) =>
      ipcRenderer.invoke('screenshot:startCapture', intervalMs) as Promise<boolean>,
    stopCapture: () => ipcRenderer.invoke('screenshot:stopCapture') as Promise<boolean>,
    getCaptureStatus: () =>
      ipcRenderer.invoke('screenshot:getCaptureStatus') as Promise<{
        isCapturing: boolean
        intervalMs: number
      }>
  },

  // Event listeners
  on: (channel: string, callback: (...args: any[]) => void) => {
    const validChannels = ['navigate', 'screenshot-captured', 'backend-status']
    if (validChannels.includes(channel)) {
      ipcRenderer.on(channel, (_, ...args) => callback(...args))
    }
  },

  off: (channel: string, callback: (...args: any[]) => void) => {
    ipcRenderer.removeListener(channel, callback)
  }
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}
