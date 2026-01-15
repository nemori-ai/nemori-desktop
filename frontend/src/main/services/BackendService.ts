import { spawn, ChildProcess, spawnSync } from 'child_process'
import { app } from 'electron'
import { join, dirname } from 'path'
import { existsSync, chmodSync } from 'fs'
import { homedir } from 'os'
import http from 'http'
import { getRandomPort } from 'get-port-please'

export class BackendService {
  private process: ChildProcess | null = null
  private host: string = '127.0.0.1'
  private port: number = 0  // Will be set dynamically
  private isStarted: boolean = false
  private isDev: boolean = process.env.NODE_ENV === 'development' || !app.isPackaged

  constructor(host?: string) {
    if (host) this.host = host
  }

  getUrl(): string {
    if (this.port === 0) {
      throw new Error('Backend service not started yet - port not assigned')
    }
    return `http://${this.host}:${this.port}`
  }

  isRunning(): boolean {
    return this.isStarted && this.process !== null
  }

  async start(): Promise<boolean> {
    if (this.isStarted) {
      console.log('Backend already started')
      return true
    }

    try {
      // In production, use bundled executable; in development, use Python
      // Always get a random port first to avoid conflicts
      if (this.isDev) {
        return await this.startDevelopment()
      } else {
        return await this.startProduction()
      }
    } catch (error) {
      console.error('Failed to start backend:', error)
      return false
    }
  }

  private async startDevelopment(): Promise<boolean> {
    // Find Python executable and backend path
    const pythonPath = this.findPythonPath()
    const backendPath = this.findBackendPath()

    if (!pythonPath) {
      console.error('Python not found')
      return false
    }

    if (!backendPath) {
      console.error('Backend not found')
      return false
    }

    // Use random port in development too for consistency with production
    this.port = await getRandomPort(this.host)
    console.log('[Dev] Starting backend with Python:', pythonPath)
    console.log('[Dev] Backend path:', backendPath)
    console.log('[Dev] Using port:', this.port)

    // Start the backend process
    this.process = spawn(
      pythonPath,
      ['-m', 'uvicorn', 'main:app', '--host', this.host, '--port', String(this.port)],
      {
        cwd: backendPath,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1'
        },
        stdio: ['ignore', 'pipe', 'pipe']
      }
    )

    return await this.setupProcessHandlers()
  }

  private async startProduction(): Promise<boolean> {
    const executablePath = this.findBundledBackend()

    if (!executablePath) {
      console.error('Bundled backend not found, falling back to Python')
      return await this.startDevelopment()
    }

    // Get a random available port
    this.port = await getRandomPort(this.host)
    console.log('[Production] Starting bundled backend:', executablePath)
    console.log('[Production] Using port:', this.port)

    // On macOS, remove quarantine attributes to allow execution
    // This is needed because the backend is not signed with an Apple Developer certificate
    if (process.platform === 'darwin') {
      const backendDir = dirname(executablePath)
      console.log('[Production] Removing quarantine attributes from:', backendDir)
      try {
        // Remove quarantine attributes recursively from the backend directory
        const result = spawnSync('xattr', ['-cr', backendDir], { timeout: 10000 })
        if (result.status === 0) {
          console.log('[Production] Quarantine attributes removed successfully')
        } else {
          console.warn('[Production] Failed to remove quarantine attributes:', result.stderr?.toString())
        }
      } catch (error) {
        console.warn('[Production] Error removing quarantine attributes:', error)
      }
    }

    // Ensure executable has correct permissions on Unix
    if (process.platform !== 'win32') {
      try {
        chmodSync(executablePath, '755')
      } catch {
        // Ignore permission errors
      }
    }

    // Start the bundled backend
    // Set NEMORI_DATA_DIR explicitly to ensure consistency between dev and production
    // Use XDG standard path: ~/.local/share/Nemori
    const dataDir = join(homedir(), '.local', 'share', 'Nemori')
    console.log('[Production] Using data directory:', dataDir)

    this.process = spawn(
      executablePath,
      ['--host', this.host, '--port', String(this.port)],
      {
        env: {
          ...process.env,
          NEMORI_DATA_DIR: dataDir
        },
        stdio: ['ignore', 'pipe', 'pipe']
      }
    )

    return await this.setupProcessHandlers()
  }

  private async setupProcessHandlers(): Promise<boolean> {
    if (!this.process) return false

    // Handle stdout
    this.process.stdout?.on('data', (data) => {
      console.log('[Backend]', data.toString().trim())
    })

    // Handle stderr
    this.process.stderr?.on('data', (data) => {
      console.error('[Backend Error]', data.toString().trim())
    })

    // Handle process exit
    this.process.on('exit', (code) => {
      console.log('Backend process exited with code:', code)
      this.isStarted = false
      this.process = null
    })

    this.process.on('error', (err) => {
      console.error('Backend process error:', err)
      this.isStarted = false
    })

    // Wait for backend to be ready
    const ready = await this.waitForReady(30000)
    this.isStarted = ready

    if (ready) {
      console.log('Backend is ready at', this.getUrl())
    } else {
      console.error('Backend failed to start')
    }

    return ready
  }

  private findBundledBackend(): string | null {
    const execName = process.platform === 'win32' ? 'nemori-backend.exe' : 'nemori-backend'

    // Check possible locations for bundled backend (directory mode)
    // PyInstaller directory mode outputs to: nemori-backend/nemori-backend (folder/executable)
    const candidates = [
      // Production: bundled in resources (directory mode structure)
      join(process.resourcesPath || '', 'backend', 'nemori-backend', execName),
      join(process.resourcesPath || '', 'backend', execName),
      join(process.resourcesPath || '', execName),
      // macOS app bundle
      join(app.getAppPath(), '..', 'backend', 'nemori-backend', execName),
      join(app.getAppPath(), '..', 'backend', execName),
      join(app.getAppPath(), 'backend', 'nemori-backend', execName),
      join(app.getAppPath(), 'backend', execName),
    ]

    for (const candidate of candidates) {
      console.log('Checking bundled backend at:', candidate)
      if (existsSync(candidate)) {
        return candidate
      }
    }

    return null
  }

  async stop(): Promise<void> {
    if (this.process) {
      console.log('Stopping backend...')

      // Try graceful shutdown first
      this.process.kill('SIGTERM')

      // Wait for process to exit
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
          if (this.process) {
            this.process.kill('SIGKILL')
          }
          resolve()
        }, 5000)

        this.process?.on('exit', () => {
          clearTimeout(timeout)
          resolve()
        })
      })

      this.process = null
      this.isStarted = false
      console.log('Backend stopped')
    }
  }

  private findPythonPath(): string | null {
    // First, try to find venv Python in backend directory (preferred for correct dependencies)
    const backendPath = this.findBackendPath()
    if (backendPath) {
      const venvPython = process.platform === 'win32'
        ? join(backendPath, '.venv', 'Scripts', 'python.exe')
        : join(backendPath, '.venv', 'bin', 'python3')

      if (existsSync(venvPython)) {
        console.log('[Dev] Using venv Python:', venvPython)
        return venvPython
      }
    }

    // Fallback to system Python
    const candidates = [
      'python3',
      'python',
      '/usr/bin/python3',
      '/usr/local/bin/python3',
      '/opt/homebrew/bin/python3'
    ]

    // On Windows
    if (process.platform === 'win32') {
      candidates.push(
        'python.exe',
        'C:\\Python310\\python.exe',
        'C:\\Python311\\python.exe',
        'C:\\Python312\\python.exe'
      )
    }

    // Try to find a working Python
    for (const candidate of candidates) {
      try {
        const result = require('child_process').spawnSync(candidate, ['--version'])
        if (result.status === 0) {
          return candidate
        }
      } catch {
        // Continue to next candidate
      }
    }

    return null
  }

  private findBackendPath(): string | null {
    // Check possible locations for backend
    const candidates = [
      // Development: backend is at project root
      join(app.getAppPath(), '..', 'backend'),
      join(app.getAppPath(), '..', '..', 'backend'),
      // Production: backend is bundled with app
      join(app.getAppPath(), 'backend'),
      join(process.resourcesPath || '', 'backend'),
      // Absolute path for development
      join(__dirname, '..', '..', '..', '..', 'backend')
    ]

    for (const candidate of candidates) {
      if (existsSync(join(candidate, 'main.py'))) {
        return candidate
      }
    }

    return null
  }

  private async checkHealth(): Promise<boolean> {
    return new Promise((resolve) => {
      const req = http.request(
        {
          host: this.host,
          port: this.port,
          path: '/health',
          method: 'GET',
          timeout: 2000
        },
        (res) => {
          resolve(res.statusCode === 200)
        }
      )

      req.on('error', () => {
        resolve(false)
      })

      req.on('timeout', () => {
        req.destroy()
        resolve(false)
      })

      req.end()
    })
  }

  private async waitForReady(timeoutMs: number): Promise<boolean> {
    const startTime = Date.now()
    const checkInterval = 500

    while (Date.now() - startTime < timeoutMs) {
      const ready = await this.checkHealth()
      if (ready) {
        return true
      }

      await new Promise((resolve) => setTimeout(resolve, checkInterval))
    }

    return false
  }
}
