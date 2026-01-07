import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'
import http from 'http'

export class BackendService {
  private process: ChildProcess | null = null
  private host: string = '127.0.0.1'
  private port: number = 21978
  private isStarted: boolean = false

  constructor(host?: string, port?: number) {
    if (host) this.host = host
    if (port) this.port = port
  }

  getUrl(): string {
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
      // Check if backend is already running (maybe from another instance)
      const alreadyRunning = await this.checkHealth()
      if (alreadyRunning) {
        console.log('Backend already running on', this.getUrl())
        this.isStarted = true
        return true
      }

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

      console.log('Starting backend with Python:', pythonPath)
      console.log('Backend path:', backendPath)

      // Start the backend process
      this.process = spawn(pythonPath, ['-m', 'uvicorn', 'main:app', '--host', this.host, '--port', String(this.port)], {
        cwd: backendPath,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1'
        },
        stdio: ['ignore', 'pipe', 'pipe']
      })

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
    } catch (error) {
      console.error('Failed to start backend:', error)
      return false
    }
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
    // Check common Python locations
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
