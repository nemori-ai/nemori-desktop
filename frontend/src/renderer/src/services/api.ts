/**
 * API Service for communicating with Python backend
 */

// BASE_URL starts empty - must be initialized via initializeApi()
let BASE_URL = ''
let isInitialized = false
let initializationPromise: Promise<void> | null = null

// Helper function to wait
const sleep = (ms: number): Promise<void> => new Promise(resolve => setTimeout(resolve, ms))

// Initialize API base URL from Electron main process with retry
export async function initializeApi(): Promise<void> {
  // Return existing promise if already initializing successfully
  if (isInitialized) {
    return
  }

  // If there's an existing promise that's still pending, wait for it
  if (initializationPromise) {
    try {
      await initializationPromise
      return
    } catch {
      // Previous attempt failed, clear and retry
      initializationPromise = null
    }
  }

  initializationPromise = (async () => {
    const maxRetries = 10
    const retryDelay = 500 // ms

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        if (!window.api?.backend?.getUrl) {
          throw new Error('Backend API not available - running outside Electron?')
        }

        BASE_URL = await window.api.backend.getUrl()
        isInitialized = true
        console.log(`[API] Initialized with URL: ${BASE_URL} (attempt ${attempt})`)
        return
      } catch (error) {
        console.warn(`[API] Initialization attempt ${attempt}/${maxRetries} failed:`, error)

        if (attempt === maxRetries) {
          throw new Error(`Failed to initialize API after ${maxRetries} attempts: ${error}`)
        }

        // Wait before retrying
        await sleep(retryDelay)
      }
    }
  })()

  try {
    await initializationPromise
  } catch (error) {
    // Clear the failed promise so next call can retry
    initializationPromise = null
    throw error
  }
}

class ApiService {
  // Get base URL dynamically to ensure we always use the latest value
  private get baseUrl(): string {
    return BASE_URL
  }

  async setBaseUrl(url: string): Promise<void> {
    BASE_URL = url
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    // Ensure API is initialized before making requests
    if (!isInitialized) {
      await initializeApi()
    }
    const url = `${this.baseUrl}/api${endpoint}`

    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `HTTP error! status: ${response.status}`)
    }

    return response.json()
  }

  // ==================== Chat API ====================

  async sendMessage(
    content: string,
    conversationId?: string,
    model?: string,
    useMemory: boolean = true
  ): Promise<{
    success: boolean
    message?: Message
    conversation_id?: string
    error?: string
  }> {
    return this.request('/chat/send', {
      method: 'POST',
      body: JSON.stringify({
        content,
        conversation_id: conversationId,
        model,
        use_memory: useMemory
      })
    })
  }

  async streamMessage(
    content: string,
    conversationId?: string,
    model?: string,
    useMemory: boolean = true,
    onChunk: (chunk: string) => void = () => {}
  ): Promise<{ content: string; conversationId: string }> {
    // Ensure API is initialized before making requests
    if (!isInitialized) {
      await initializeApi()
    }
    const url = `${this.baseUrl}/api/chat/stream`

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content,
        conversation_id: conversationId,
        model,
        use_memory: useMemory
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    // Get conversation ID from response header
    const newConversationId = response.headers.get('X-Conversation-Id') || conversationId || ''

    const reader = response.body?.getReader()
    // Use stream: true to handle multi-byte UTF-8 characters split across chunks
    const decoder = new TextDecoder('utf-8')
    let fullContent = ''
    let buffer = '' // Buffer for incomplete SSE lines

    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          // Flush any remaining data in decoder
          const remaining = decoder.decode()
          if (remaining) buffer += remaining
          break
        }

        // Decode with stream: true to handle partial UTF-8 sequences
        const chunk = decoder.decode(value, { stream: true })
        buffer += chunk

        // Process complete lines from buffer
        const lines = buffer.split('\n')
        // Keep the last potentially incomplete line in buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue
            try {
              // Parse JSON-encoded chunk to handle newlines and special characters
              const chunk = JSON.parse(data)
              fullContent += chunk
              onChunk(chunk)
            } catch {
              // Fallback for non-JSON data
              fullContent += data
              onChunk(data)
            }
          }
        }
      }

      // Process any remaining complete line in buffer
      if (buffer.startsWith('data: ')) {
        const data = buffer.slice(6)
        if (data !== '[DONE]') {
          try {
            const chunk = JSON.parse(data)
            fullContent += chunk
            onChunk(chunk)
          } catch {
            fullContent += data
            onChunk(data)
          }
        }
      }
    }

    return { content: fullContent, conversationId: newConversationId }
  }

  async getMessages(conversationId: string, limit: number = 100): Promise<{ messages: Message[] }> {
    return this.request(`/chat/messages/${conversationId}?limit=${limit}`)
  }

  // ==================== Conversations API ====================

  async getConversations(limit: number = 50): Promise<{ conversations: Conversation[] }> {
    return this.request(`/conversations/?limit=${limit}`)
  }

  async createConversation(title?: string): Promise<{ id: string; title: string }> {
    return this.request('/conversations/', {
      method: 'POST',
      body: JSON.stringify({ title })
    })
  }

  async updateConversation(id: string, title: string): Promise<{ success: boolean }> {
    return this.request(`/conversations/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ title })
    })
  }

  async deleteConversation(id: string): Promise<{ success: boolean }> {
    return this.request(`/conversations/${id}`, {
      method: 'DELETE'
    })
  }

  // ==================== Memories API ====================

  async getEpisodicMemories(
    limit: number = 100,
    offset: number = 0
  ): Promise<{ memories: EpisodicMemory[] }> {
    return this.request(`/memories/episodic?limit=${limit}&offset=${offset}`)
  }

  async getEpisodicMemoriesSince(
    sinceTimestamp: number,
    limit: number = 100
  ): Promise<{ memories: EpisodicMemory[]; since: number }> {
    return this.request(`/memories/episodic/since/${sinceTimestamp}?limit=${limit}`)
  }

  async getSemanticMemories(
    type?: SemanticCategory,
    limit: number = 100
  ): Promise<{ memories: SemanticMemory[] }> {
    const params = new URLSearchParams({ limit: String(limit) })
    if (type) params.append('type', type)
    return this.request(`/memories/semantic?${params}`)
  }

  async getSemanticMemoriesSince(
    sinceTimestamp: number,
    type?: SemanticCategory,
    limit: number = 100
  ): Promise<{ memories: SemanticMemory[]; since: number }> {
    const params = new URLSearchParams({ limit: String(limit) })
    if (type) params.append('type', type)
    return this.request(`/memories/semantic/since/${sinceTimestamp}?${params}`)
  }

  async searchMemories(
    query: string,
    limit: number = 10,
    type?: string
  ): Promise<{ results: Memory[] }> {
    const params = new URLSearchParams({ query, limit: String(limit) })
    if (type) params.append('type', type)
    return this.request(`/memories/search?${params}`)
  }

  async getMemoryStats(): Promise<MemoryStats> {
    return this.request('/memories/stats')
  }

  // ==================== Screenshots API ====================

  async getScreenshots(
    limit: number = 100,
    offset: number = 0
  ): Promise<{ screenshots: Screenshot[] }> {
    return this.request(`/screenshots/?limit=${limit}&offset=${offset}`)
  }

  async getScreenshotDates(): Promise<{ dates: string[] }> {
    return this.request('/screenshots/dates')
  }

  async getScreenshotsByDate(
    dateStr: string,
    limit: number = 500,
    offset: number = 0
  ): Promise<{ screenshots: Screenshot[]; date: string; total: number }> {
    return this.request(`/screenshots/by-date/${dateStr}?limit=${limit}&offset=${offset}`)
  }

  async getScreenshotsSince(
    sinceTimestamp: number,
    limit: number = 100
  ): Promise<{ screenshots: Screenshot[]; since: number }> {
    return this.request(`/screenshots/since/${sinceTimestamp}?limit=${limit}`)
  }

  async getScreenshotsPaginated(
    page: number = 1,
    pageSize: number = 50
  ): Promise<PaginatedResponse<Screenshot>> {
    return this.request(`/screenshots/paginated?page=${page}&page_size=${pageSize}`)
  }

  async getCaptureStatus(): Promise<CaptureStatus> {
    const status = await this.request<CaptureStatus>('/screenshots/status')

    // Get monitors and capture status from Electron (to avoid mss permission issues)
    if (window.api?.screenshot) {
      const monitors = await window.api.screenshot.getMonitors()
      const selected = await window.api.screenshot.getSelectedMonitor()
      const electronStatus = await window.api.screenshot.getCaptureStatus()

      status.monitors = monitors.map((m, index) => ({
        id: index,
        name: m.name,
        width: m.width,
        height: m.height,
        left: m.x,
        top: m.y
      }))
      status.selected_monitor = selected ? monitors.findIndex((m) => m.id === selected) : 0
      // Use Electron's capture status instead of backend's
      status.is_capturing = electronStatus.isCapturing
      status.interval_ms = electronStatus.intervalMs
    }

    return status
  }

  async startCapture(intervalMs?: number): Promise<{ success: boolean; status: CaptureStatus }> {
    // Use Electron's capture service to avoid mss permission issues
    if (window.api?.screenshot) {
      const success = await window.api.screenshot.startCapture(intervalMs)
      const status = await this.getCaptureStatus()
      return { success, status }
    }

    // Fallback to backend (for development without Electron)
    return this.request('/screenshots/start', {
      method: 'POST',
      body: JSON.stringify({ interval_ms: intervalMs })
    })
  }

  async stopCapture(): Promise<{ success: boolean; status: CaptureStatus }> {
    // Use Electron's capture service to avoid mss permission issues
    if (window.api?.screenshot) {
      const success = await window.api.screenshot.stopCapture()
      const status = await this.getCaptureStatus()
      return { success, status }
    }

    // Fallback to backend (for development without Electron)
    return this.request('/screenshots/stop', {
      method: 'POST'
    })
  }

  async captureNow(): Promise<{ success: boolean; screenshot?: Screenshot; error?: string }> {
    // Use Electron's screenshot API for proper permission handling on macOS
    if (window.api?.screenshot) {
      // Check permission first
      const permission = await window.api.screenshot.checkPermission()
      if (!permission.granted) {
        return {
          success: false,
          error: 'Screen recording permission not granted. Please enable it in System Settings > Privacy & Security > Screen Recording.'
        }
      }

      // Capture using Electron
      const result = await window.api.screenshot.capture()
      if (!result.success || !result.imageData) {
        return { success: false, error: result.error || 'Capture failed' }
      }

      // Upload to backend
      return this.request('/screenshots/upload', {
        method: 'POST',
        body: JSON.stringify({
          image_data: result.imageData,
          monitor_id: result.monitorId
        })
      })
    }

    // Fallback to backend capture (for development without Electron)
    return this.request('/screenshots/capture-now', {
      method: 'POST'
    })
  }

  async getScreenshotImage(id: string): Promise<Blob> {
    // Ensure API is initialized before making requests
    if (!isInitialized) {
      await initializeApi()
    }
    const response = await fetch(`${this.baseUrl}/api/screenshots/${id}/image`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return response.blob()
  }

  // Get screenshot image URL for direct use in <img src>
  // Note: This is async now to ensure API is initialized
  async getScreenshotImageUrl(id: string): Promise<string> {
    if (!isInitialized) {
      await initializeApi()
    }
    return `${this.baseUrl}/api/screenshots/${id}/image`
  }

  async deleteScreenshot(id: string): Promise<{ success: boolean }> {
    return this.request(`/screenshots/${id}`, {
      method: 'DELETE'
    })
  }

  async getMonitors(): Promise<{ monitors: Monitor[]; selected: number | string }> {
    // Use Electron's monitor API if available
    if (window.api?.screenshot) {
      const monitors = await window.api.screenshot.getMonitors()
      const selected = await window.api.screenshot.getSelectedMonitor()
      return {
        monitors: monitors.map((m, index) => ({
          id: index, // Convert string ID to index for compatibility
          name: m.name,
          width: m.width,
          height: m.height,
          left: m.x,
          top: m.y,
          electronId: m.id // Keep the original Electron ID
        })) as Monitor[],
        selected: selected ? monitors.findIndex((m) => m.id === selected) : 0
      }
    }

    // Fallback to backend
    return this.request('/screenshots/monitors')
  }

  async selectMonitor(
    monitorId: number | string
  ): Promise<{ success: boolean; selected: number | string; monitors: Monitor[] }> {
    // Use Electron's monitor selection if available
    if (window.api?.screenshot) {
      const monitors = await window.api.screenshot.getMonitors()
      const monitor = typeof monitorId === 'number' ? monitors[monitorId] : monitors.find((m) => m.id === monitorId)
      if (monitor) {
        await window.api.screenshot.setMonitor(monitor.id)
        return {
          success: true,
          selected: monitorId,
          monitors: monitors.map((m, index) => ({
            id: index,
            name: m.name,
            width: m.width,
            height: m.height,
            left: m.x,
            top: m.y,
            electronId: m.id
          })) as Monitor[]
        }
      }
      return { success: false, selected: 0, monitors: [] }
    }

    // Fallback to backend
    return this.request('/screenshots/monitors/select', {
      method: 'POST',
      body: JSON.stringify({ monitor_id: monitorId })
    })
  }

  async getMonitorPreview(monitorId: number | string): Promise<string | Blob> {
    // Use Electron's preview API if available
    if (window.api?.screenshot) {
      const monitors = await window.api.screenshot.getMonitors()
      const monitor = typeof monitorId === 'number' ? monitors[monitorId] : monitors.find((m) => m.id === monitorId)
      if (monitor) {
        const preview = await window.api.screenshot.getPreview(monitor.id)
        if (preview) {
          return preview // Returns data URL string
        }
      }
      throw new Error('Monitor not found')
    }

    // Fallback to backend - ensure API is initialized
    if (!isInitialized) {
      await initializeApi()
    }
    const response = await fetch(`${this.baseUrl}/api/screenshots/monitors/${monitorId}/preview`)
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return response.blob()
  }

  async checkScreenshotPermission(): Promise<{ granted: boolean; canRequest: boolean }> {
    if (window.api?.screenshot) {
      return window.api.screenshot.checkPermission()
    }
    // Backend doesn't have permission issues on non-macOS
    return { granted: true, canRequest: false }
  }

  async openScreenshotPermissionSettings(): Promise<void> {
    if (window.api?.screenshot) {
      await window.api.screenshot.openPermissionSettings()
    }
  }

  // ==================== Settings API ====================

  async getAllSettings(): Promise<{ settings: Record<string, string> }> {
    return this.request('/settings/')
  }

  async getSetting(key: string): Promise<{ key: string; value: string | null }> {
    return this.request(`/settings/${key}`)
  }

  async updateSetting(key: string, value: string): Promise<{ success: boolean }> {
    return this.request(`/settings/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ value })
    })
  }

  async configureLLM(config: LLMConfig): Promise<{ success: boolean; configured: boolean }> {
    return this.request('/settings/llm', {
      method: 'POST',
      body: JSON.stringify(config)
    })
  }

  async getLLMStatus(): Promise<{ configured: boolean }> {
    return this.request('/settings/llm/status')
  }

  async testLLMConnection(): Promise<{ success: boolean; error?: string }> {
    return this.request('/settings/llm/test', {
      method: 'POST'
    })
  }

  async getAppSettings(): Promise<AppSettings> {
    return this.request('/settings/app')
  }

  async updateAppSettings(settings: Partial<AppSettings>): Promise<{ success: boolean }> {
    return this.request('/settings/app', {
      method: 'PUT',
      body: JSON.stringify(settings)
    })
  }

  // ==================== Profile API ====================

  async getProfile(): Promise<ProfileData> {
    return this.request('/profile/')
  }

  async getProfileSummary(maxChars: number = 800): Promise<{ summary: string }> {
    return this.request(`/profile/summary?max_chars=${maxChars}`)
  }

  async getProfileContext(): Promise<ProfileContext> {
    return this.request('/profile/context')
  }

  async updateProfileFromMemories(recentCount: number = 20): Promise<{ success: boolean; updated: number; pruned: number }> {
    return this.request(`/profile/update?recent_count=${recentCount}`, {
      method: 'POST'
    })
  }

  async addProfileItem(category: string, content: string, importance: number = 0.8): Promise<{ success: boolean }> {
    return this.request('/profile/add', {
      method: 'POST',
      body: JSON.stringify({ category, content, importance })
    })
  }

  async removeProfileItem(category: string, content: string): Promise<{ success: boolean }> {
    return this.request('/profile/remove', {
      method: 'POST',
      body: JSON.stringify({ category, content })
    })
  }

  async clearProfile(): Promise<{ success: boolean }> {
    return this.request('/profile/', {
      method: 'DELETE'
    })
  }

  // ==================== Visualization API ====================

  async getTimeline(
    days: number = 30,
    granularity: 'hour' | 'day' | 'week' = 'day'
  ): Promise<TimelineData> {
    return this.request(`/visualization/timeline?days=${days}&granularity=${granularity}`)
  }

  async getActivityHeatmap(days: number = 90): Promise<HeatmapData> {
    return this.request(`/visualization/heatmap?days=${days}`)
  }

  async getKnowledgeGraph(limit: number = 100): Promise<KnowledgeGraphData> {
    return this.request(`/visualization/knowledge-graph?limit=${limit}`)
  }

  async getTopicDistribution(): Promise<TopicData> {
    return this.request('/visualization/topics')
  }

  async getVisualizationStats(): Promise<VisualizationStats> {
    return this.request('/visualization/stats')
  }

  // ==================== Agent API ====================

  async getAgentInfo(): Promise<AgentInfo> {
    return this.request('/agent/info')
  }

  async getAgentTools(): Promise<{ tools: AgentToolInfo[] }> {
    return this.request('/agent/tools')
  }

  async streamAgentChat(
    content: string,
    conversationId?: string,
    maxSteps: number = 10,
    onEvent: (event: AgentStreamEvent) => void = () => {}
  ): Promise<{ conversationId: string; sessionId: string }> {
    // Ensure API is initialized before making requests
    if (!isInitialized) {
      await initializeApi()
    }
    const url = `${this.baseUrl}/api/agent/chat`

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content,
        conversation_id: conversationId,
        config: { max_steps: maxSteps }
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    // Get IDs from response headers
    const newConversationId = response.headers.get('X-Conversation-Id') || conversationId || ''
    const sessionId = response.headers.get('X-Session-Id') || ''

    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    if (reader) {
      while (true) {
        const { done, value } = await reader.read()
        if (done) {
          const remaining = decoder.decode()
          if (remaining) buffer += remaining
          break
        }

        const chunk = decoder.decode(value, { stream: true })
        buffer += chunk

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue
            try {
              const event = JSON.parse(data) as AgentStreamEvent
              onEvent(event)
            } catch {
              // Ignore parse errors
            }
          }
        }
      }

      // Process any remaining data
      if (buffer.startsWith('data: ')) {
        const data = buffer.slice(6)
        if (data !== '[DONE]') {
          try {
            const event = JSON.parse(data) as AgentStreamEvent
            onEvent(event)
          } catch {
            // Ignore parse errors
          }
        }
      }
    }

    return { conversationId: newConversationId, sessionId }
  }

  async getAgentSessions(conversationId?: string, limit: number = 20): Promise<AgentSession[]> {
    const params = new URLSearchParams({ limit: String(limit) })
    if (conversationId) params.append('conversation_id', conversationId)
    return this.request(`/agent/sessions?${params}`)
  }

  async getAgentSessionDetails(sessionId: string): Promise<AgentSessionDetails> {
    return this.request(`/agent/sessions/${sessionId}`)
  }

  // ==================== Health Check ====================

  async checkHealth(): Promise<{
    status: string
    database: string
    llm_configured: boolean
  }> {
    // Ensure API is initialized before making requests
    if (!isInitialized) {
      await initializeApi()
    }
    const response = await fetch(`${this.baseUrl}/health`)
    return response.json()
  }

  // ==================== Proactive Agent API ====================

  async getProactiveAgentStatus(): Promise<ProactiveAgentStatus> {
    return this.request('/proactive/status')
  }

  async startProactiveAgent(): Promise<{ success: boolean; message: string }> {
    return this.request('/proactive/start', { method: 'POST' })
  }

  async stopProactiveAgent(): Promise<{ success: boolean; message: string }> {
    return this.request('/proactive/stop', { method: 'POST' })
  }

  async wakeProactiveAgent(reason?: string): Promise<{ success: boolean; message: string; state: string }> {
    return this.request('/proactive/wake', {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'User request' })
    })
  }

  async sleepProactiveAgent(reason?: string): Promise<{ success: boolean; message: string; state: string }> {
    return this.request('/proactive/sleep', {
      method: 'POST',
      body: JSON.stringify({ reason: reason || 'User request' })
    })
  }

  async getProactiveTasks(status?: string, limit?: number): Promise<{ success: boolean; count: number; tasks: ProactiveTask[] }> {
    const params = new URLSearchParams()
    if (status) params.append('status', status)
    if (limit) params.append('limit', String(limit))
    return this.request(`/proactive/tasks?${params}`)
  }

  async getProactiveTaskHistory(limit?: number): Promise<{ success: boolean; count: number; history: ProactiveTask[] }> {
    const params = new URLSearchParams()
    if (limit) params.append('limit', String(limit))
    return this.request(`/proactive/tasks/history?${params}`)
  }

  async createProactiveTask(task: CreateProactiveTaskRequest): Promise<{ success: boolean; task_id: string; message: string }> {
    return this.request('/proactive/tasks', {
      method: 'POST',
      body: JSON.stringify(task)
    })
  }

  async cancelProactiveTask(taskId: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/proactive/tasks/${taskId}`, { method: 'DELETE' })
  }

  async deleteProactiveTaskHistory(taskId: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/proactive/tasks/history/${taskId}`, { method: 'DELETE' })
  }

  async getProactiveSchedule(): Promise<{ success: boolean; schedule: ProactiveSchedule }> {
    return this.request('/proactive/schedule')
  }

  async updateProactiveSchedule(schedule: UpdateProactiveScheduleRequest): Promise<{ success: boolean; message: string; schedule: ProactiveSchedule }> {
    return this.request('/proactive/schedule', {
      method: 'PUT',
      body: JSON.stringify(schedule)
    })
  }

  async getProactiveTriggers(): Promise<{ success: boolean; count: number; triggers: ProactiveTrigger[] }> {
    return this.request('/proactive/triggers')
  }

  async getProactiveTaskTypes(): Promise<{ success: boolean; task_types: { value: string; name: string }[] }> {
    return this.request('/proactive/task-types')
  }

  async runProactiveTaskNow(taskType: string, title?: string): Promise<{ success: boolean; task_id: string; message: string; agent_state: string }> {
    const params = new URLSearchParams({ task_type: taskType })
    if (title) params.append('title', title)
    return this.request(`/proactive/actions/run-task?${params}`, { method: 'POST' })
  }

  // ==================== Profile Files API ====================

  async getProfileFiles(includeTopics?: boolean, layer?: number): Promise<ProfileFilesResponse> {
    const params = new URLSearchParams()
    if (includeTopics !== undefined) params.append('include_topics', String(includeTopics))
    if (layer !== undefined) params.append('layer', String(layer))
    return this.request(`/profile-files/files?${params}`)
  }

  async getProfileFile(filename: string): Promise<ProfileFileResponse> {
    return this.request(`/profile-files/files/${encodeURIComponent(filename)}`)
  }

  async updateProfileFile(filename: string, content: string, changelogEntry: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/profile-files/files/${encodeURIComponent(filename)}`, {
      method: 'PUT',
      body: JSON.stringify({ content, changelog_entry: changelogEntry })
    })
  }

  async createProfileFile(filename: string, title: string, description: string, initialContent?: string): Promise<{ success: boolean; message: string; title: string }> {
    return this.request(`/profile-files/files/${encodeURIComponent(filename)}`, {
      method: 'POST',
      body: JSON.stringify({ title, description, initial_content: initialContent })
    })
  }

  async deleteProfileFile(filename: string): Promise<{ success: boolean; message: string }> {
    return this.request(`/profile-files/files/${encodeURIComponent(filename)}`, { method: 'DELETE' })
  }

  async searchProfileFiles(query: string, filenames?: string[]): Promise<ProfileSearchResponse> {
    return this.request('/profile-files/search', {
      method: 'POST',
      body: JSON.stringify({ query, filenames })
    })
  }

  async getProfileFilesSummary(includeKeyFacts?: boolean): Promise<ProfileSummaryResponse> {
    const params = new URLSearchParams()
    if (includeKeyFacts !== undefined) params.append('include_key_facts', String(includeKeyFacts))
    return this.request(`/profile-files/summary?${params}`)
  }

  async getProfileLayers(): Promise<{ success: boolean; layers: { id: number; name: string }[] }> {
    return this.request('/profile-files/layers')
  }

  async initializeProfile(): Promise<{ success: boolean; message: string; profile_dir: string }> {
    return this.request('/profile-files/initialize', { method: 'POST' })
  }
}

// Export singleton instance
export const api = new ApiService()

// Types
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  conversation_id: string
  metadata?: Record<string, any>
}

export interface Conversation {
  id: string
  title: string
  created_at: number
  updated_at: number
}

export interface EpisodicMemory {
  id: string
  title: string
  content: string
  start_time: number
  end_time: number
  participants?: string[]
  urls?: string[]
  screenshot_ids?: string[]
  embedding_id?: string
  created_at: number
}

// 8 life categories for semantic memories
export type SemanticCategory = 'career' | 'finance' | 'health' | 'family' | 'social' | 'growth' | 'leisure' | 'spirit'

export interface SemanticMemory {
  id: string
  type: SemanticCategory
  content: string
  confidence: number
  source?: string
  embedding_id?: string
  created_at: number
}

export interface Memory {
  id: string
  content: string
  metadata: Record<string, any>
  distance?: number
}

export interface MemoryStats {
  screenshots_count: number
  messages_count: number
  episodic_memories_count: number
  semantic_memories_count: number
  conversations_count: number
  vector_embeddings: number
  pending_batch: number
}

export interface Screenshot {
  id: string
  timestamp: number
  file_path: string
  window_title?: string
  app_name?: string
  url?: string
  phash?: string
  processed: boolean
  created_at: number
}

export interface Monitor {
  id: number
  name: string
  width: number
  height: number
  left: number
  top: number
}

export interface CaptureStatus {
  is_capturing: boolean
  interval_ms: number
  screenshots_path: string
  selected_monitor: number
  monitors: Monitor[]
}

export interface LLMConfig {
  // Chat model config
  chat_api_key?: string
  chat_base_url?: string
  chat_model?: string
  // Embedding model config
  embedding_api_key?: string
  embedding_base_url?: string
  embedding_model?: string
}

export interface AppSettings {
  capture_interval_ms: number
  similarity_threshold: number
  batch_size: number
  max_local_storage_mb: number
  default_model: string
  embedding_model: string
  data_dir: string
}

// Profile Types
export interface ProfileItem {
  category: string
  content: string
  importance: number
  created_at: number
  last_seen: number
  occurrence_count: number
  score: number
}

export interface ProfileData {
  profile: Record<string, ProfileItem[]>
}

export interface ProfileContext {
  summary: string
  total_items: number
  categories: Record<string, number>
  last_updated: string
}

// Visualization Types
export interface TimelineEvent {
  id: string
  title: string
  content: string
  start_time: number
  end_time: number
  urls: string[]
  screenshot_count: number
}

export interface TimelineData {
  timeline: Array<{
    date: string
    events: TimelineEvent[]
  }>
  total_events: number
  date_range: {
    start: string
    end: string
  }
}

export interface HeatmapDay {
  date: string
  count: number
  weekday: number
}

export interface HeatmapData {
  heatmap: HeatmapDay[]
  stats: {
    total_memories: number
    active_days: number
    max_daily: number
    average_daily: number
  }
}

export interface KnowledgeNode {
  id: string
  label: string
  content: string
  type: 'knowledge' | 'preference'
  confidence: number
  created_at: number
  size: number
}

export interface KnowledgeEdge {
  source: string
  target: string
  strength: number
}

export interface KnowledgeGraphData {
  nodes: KnowledgeNode[]
  edges: KnowledgeEdge[]
  clusters: Array<{
    type: string
    node_ids: string[]
  }>
}

export interface TopicData {
  type_distribution: Record<string, number>
  top_keywords: Array<{
    word: string
    count: number
  }>
  total_memories: number
}

export interface VisualizationStats {
  episodic: {
    total: number
    today: number
    this_week: number
    this_month: number
  }
  semantic: {
    total: number
    today: number
    this_week: number
    knowledge: number
    preference: number
    avg_confidence: number
  }
  growth: {
    weekly_episodic: number
    weekly_semantic: number
  }
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Agent Types
export interface AgentInfo {
  available_tools: Record<string, string>
  max_steps: number
  version: string
}

export interface AgentToolInfo {
  name: string
  description: string
  input_schema?: Record<string, any>
}

export type AgentEventType =
  | 'session_start'
  | 'session_end'
  | 'thinking_start'
  | 'thinking_chunk'
  | 'thinking_end'
  | 'tool_call_start'
  | 'tool_call_args'
  | 'tool_call_result'
  | 'tool_call_error'
  | 'response_start'
  | 'response_chunk'
  | 'response_end'
  | 'error'

export interface AgentStreamEvent {
  type: AgentEventType
  session_id: string
  timestamp: number
  step?: number
  tool_call_id?: string
  data: Record<string, any>
}

export interface AgentToolCall {
  id: string
  session_id: string
  step: number
  tool_name: string
  tool_args: Record<string, any>
  status: 'pending' | 'running' | 'completed' | 'error'
  result?: any
  error?: string
  started_at?: number
  completed_at?: number
  duration_ms?: number
}

export interface AgentSession {
  session_id: string
  conversation_id: string
  status: string
  current_step: number
  tool_calls_count: number
  created_at: number
  completed_at?: number
}

export interface AgentSessionDetails {
  session: {
    id: string
    conversation_id: string
    status: string
    current_step: number
    max_steps: number
    created_at: number
    updated_at: number
    started_at?: number
    completed_at?: number
  }
  tool_calls: AgentToolCall[]
}

// Proactive Agent Types
export interface ProactiveAgentStatus {
  success: boolean
  agent: {
    state: string
    is_awake: boolean
    last_wakeup: string | null
    last_sleep: string | null
    tasks_completed_today: number
    next_scheduled_task: string | null
    recent_transitions: Array<{
      from: string
      to: string
      timestamp: string
      reason: string
    }>
  }
  wakeup: {
    initialized: boolean
    triggers_count: number
    enabled_triggers: number
    schedule: ProactiveSchedule
    next_trigger: {
      id: string
      name: string
      type: string
      scheduled_for: string | null
      time_until: string | null
    } | null
  }
  scheduler: {
    initialized: boolean
    tasks_in_queue: number
    pending: number
    scheduled: number
    in_progress: number
    history_size: number
    next_task: {
      id: string
      title: string
      type: string
      scheduled_time: string
      priority: number
    } | null
  }
}

export interface ProactiveTask {
  id: string
  type: string
  title: string
  description: string
  scheduled_time: string | null
  recurring: boolean
  priority: number
  status: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  execution_time_ms: number | null
  result: string | null
  error: string | null
  target_file: string | null
}

export interface CreateProactiveTaskRequest {
  type: string
  title: string
  description?: string
  scheduled_time?: string
  priority?: number
  recurring?: boolean
  recurrence_hours?: number
  target_file?: string
}

export interface ProactiveSchedule {
  enabled: boolean
  morning_wakeup: string
  evening_wakeup: string
  active_days: number[]
  next_wakeup: string | null
}

export interface UpdateProactiveScheduleRequest {
  morning_hour?: number
  morning_minute?: number
  evening_hour?: number
  evening_minute?: number
  active_days?: number[]
  enabled?: boolean
}

export interface ProactiveTrigger {
  id: string
  type: string
  name: string
  enabled: boolean
  scheduled_time: string | null
  interval_minutes: number | null
  last_triggered: string | null
  priority: number
  reason: string
}

// Profile Files Types
export interface ProfileFileInfo {
  name: string
  relative_path: string
  title: string
  summary: string
  keywords: string[]
  confidence: number
  layer: number
  layer_name: string
  updated_at: string | null
  size: number
}

export interface ProfileFilesResponse {
  success: boolean
  total_files: number
  files_by_layer: Record<string, ProfileFileInfo[]>
}

export interface ProfileFileResponse {
  success: boolean
  filename: string
  content: string
  metadata?: {
    title: string
    summary: string
    keywords: string[]
    confidence: number
    layer: number
    updated_at: string | null
  }
}

export interface ProfileSearchMatch {
  line: number
  content: string
  context: string
}

export interface ProfileSearchResult {
  filename: string
  matches_count: number
  matches: ProfileSearchMatch[]
}

export interface ProfileSearchResponse {
  success: boolean
  query: string
  total_matches: number
  files_matched: number
  results: ProfileSearchResult[]
}

export interface ProfileSummaryResponse {
  success: boolean
  total_files: number
  last_updated: string | null
  categories: Record<string, number>
  recent_changes: Array<{
    date: string
    filename: string
    description: string
  }>
  key_facts?: string[]
}
