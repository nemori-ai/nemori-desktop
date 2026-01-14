import { useState, useEffect } from 'react'
import { Save, Check, AlertCircle, Loader2, Eye, EyeOff, ExternalLink, User, RefreshCw, Trash2, Sun, Moon, Monitor, Globe } from 'lucide-react'
import { api, AppSettings, LLMConfig, ProfileContext } from '../services/api'
import { useTheme } from '../contexts/ThemeContext'
import { useLanguage } from '../contexts/LanguageContext'

export default function SettingsPage(): JSX.Element {
  const { theme, setTheme } = useTheme()
  const { language, setLanguage, t } = useLanguage()
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [appSettings, setAppSettings] = useState<AppSettings | null>(null)
  const [llmConfigured, setLlmConfigured] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [isSavingApp, setIsSavingApp] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [appResult, setAppResult] = useState<{ success: boolean; message: string } | null>(null)
  const [profileContext, setProfileContext] = useState<ProfileContext | null>(null)
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false)
  const [profileResult, setProfileResult] = useState<{ success: boolean; message: string } | null>(null)

  // Chat Model Form state
  const [chatApiKey, setChatApiKey] = useState('')
  const [chatBaseUrl, setChatBaseUrl] = useState('')
  const [chatModel, setChatModel] = useState('')

  // Embedding Model Form state
  const [embeddingApiKey, setEmbeddingApiKey] = useState('')
  const [embeddingBaseUrl, setEmbeddingBaseUrl] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState('')

  // Show/hide API keys
  const [showChatApiKey, setShowChatApiKey] = useState(false)
  const [showEmbeddingApiKey, setShowEmbeddingApiKey] = useState(false)

  // Track if user is editing API keys (to distinguish empty string from "not editing")
  const [isEditingChatApiKey, setIsEditingChatApiKey] = useState(false)
  const [isEditingEmbeddingApiKey, setIsEditingEmbeddingApiKey] = useState(false)

  // App settings form state
  const [captureInterval, setCaptureInterval] = useState(10000)
  const [batchSize, setBatchSize] = useState(20)
  const [similarityThreshold, setSimilarityThreshold] = useState(0.95)
  const [maxStorage, setMaxStorage] = useState(500)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async (): Promise<void> => {
    try {
      const [settingsRes, appRes, statusRes, profileRes] = await Promise.all([
        api.getAllSettings(),
        api.getAppSettings(),
        api.getLLMStatus(),
        api.getProfileContext().catch(() => null)
      ])

      setSettings(settingsRes.settings)
      setAppSettings(appRes)
      setLlmConfigured(statusRes.configured)
      if (profileRes) setProfileContext(profileRes)

      // Set Chat Model form values
      setChatBaseUrl(settingsRes.settings.chat_base_url || 'https://openrouter.ai/api/v1')
      setChatModel(settingsRes.settings.chat_model || 'google/gemini-3-flash-preview')

      // Set Embedding Model form values
      setEmbeddingBaseUrl(settingsRes.settings.embedding_base_url || 'https://openrouter.ai/api/v1')
      setEmbeddingModel(settingsRes.settings.embedding_model || 'google/gemini-embedding-001')

      // Set app settings form values
      setCaptureInterval(appRes.capture_interval_ms)
      setBatchSize(appRes.batch_size)
      setSimilarityThreshold(appRes.similarity_threshold)
      setMaxStorage(appRes.max_local_storage_mb)
    } catch (error) {
      console.error('Failed to load settings:', error)
    }
  }

  const handleUpdateProfile = async (): Promise<void> => {
    setIsUpdatingProfile(true)
    setProfileResult(null)

    try {
      const result = await api.updateProfileFromMemories(30)
      const profileRes = await api.getProfileContext()
      setProfileContext(profileRes)
      setProfileResult({
        success: true,
        message: `Profile updated: ${result.updated} items added/updated, ${result.pruned} pruned`
      })
    } catch (error: any) {
      setProfileResult({ success: false, message: error.message || 'Failed to update profile' })
    } finally {
      setIsUpdatingProfile(false)
    }
  }

  const handleClearProfile = async (): Promise<void> => {
    if (!confirm('Are you sure you want to clear your profile? This cannot be undone.')) {
      return
    }

    try {
      await api.clearProfile()
      const profileRes = await api.getProfileContext()
      setProfileContext(profileRes)
      setProfileResult({ success: true, message: 'Profile cleared successfully' })
    } catch (error: any) {
      setProfileResult({ success: false, message: error.message || 'Failed to clear profile' })
    }
  }

  const handleSaveLLMConfig = async (): Promise<void> => {
    setIsSaving(true)
    setTestResult(null)

    try {
      const config: LLMConfig = {}

      // Chat model config - if editing, use the value (even if empty to clear)
      if (isEditingChatApiKey) {
        config.chat_api_key = chatApiKey  // Can be empty string to clear
      }
      if (chatBaseUrl) config.chat_base_url = chatBaseUrl
      if (chatModel) config.chat_model = chatModel

      // Embedding model config - if editing, use the value (even if empty to clear)
      if (isEditingEmbeddingApiKey) {
        config.embedding_api_key = embeddingApiKey  // Can be empty string to clear
      }
      if (embeddingBaseUrl) config.embedding_base_url = embeddingBaseUrl
      if (embeddingModel) config.embedding_model = embeddingModel

      // Check if anything to save
      if (Object.keys(config).length === 0) {
        setTestResult({ success: false, message: 'No changes to save. Please enter values first.' })
        setIsSaving(false)
        return
      }

      const { configured } = await api.configureLLM(config)
      setLlmConfigured(configured)

      // Clear the API key fields and flags after saving
      setChatApiKey('')
      setEmbeddingApiKey('')
      setIsEditingChatApiKey(false)
      setIsEditingEmbeddingApiKey(false)

      await loadSettings()

      const savedItems: string[] = []
      const clearedItems: string[] = []
      if (config.chat_api_key) savedItems.push('Chat API Key')
      else if (isEditingChatApiKey && !config.chat_api_key) clearedItems.push('Chat API Key')
      if (config.chat_base_url) savedItems.push('Chat Base URL')
      if (config.chat_model) savedItems.push('Chat Model')
      if (config.embedding_api_key) savedItems.push('Embedding API Key')
      else if (isEditingEmbeddingApiKey && !config.embedding_api_key) clearedItems.push('Embedding API Key')
      if (config.embedding_base_url) savedItems.push('Embedding Base URL')
      if (config.embedding_model) savedItems.push('Embedding Model')

      let message = ''
      if (savedItems.length > 0) message += `Saved: ${savedItems.join(', ')}. `
      if (clearedItems.length > 0) message += `Cleared: ${clearedItems.join(', ')}. `
      message += `LLM ${configured ? 'is now configured' : 'needs API key'}.`

      setTestResult({ success: true, message })
    } catch (error: any) {
      setTestResult({ success: false, message: error.message || 'Failed to save settings' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleTestConnection = async (): Promise<void> => {
    setIsTesting(true)
    setTestResult(null)

    try {
      const { success, error } = await api.testLLMConnection()
      setTestResult({
        success,
        message: success ? 'Connection successful!' : error || 'Connection failed'
      })
    } catch (error: any) {
      setTestResult({ success: false, message: error.message || 'Connection test failed' })
    } finally {
      setIsTesting(false)
    }
  }

  const handleOpenExternal = (url: string): void => {
    window.api.shell.openExternal(url)
  }

  const handleSaveAppSettings = async (): Promise<void> => {
    setIsSavingApp(true)
    setAppResult(null)

    try {
      await api.updateAppSettings({
        capture_interval_ms: captureInterval,
        batch_size: batchSize,
        similarity_threshold: similarityThreshold,
        max_local_storage_mb: maxStorage
      })

      await loadSettings()
      setAppResult({ success: true, message: 'Settings saved successfully!' })
    } catch (error: any) {
      setAppResult({ success: false, message: error.message || 'Failed to save settings' })
    } finally {
      setIsSavingApp(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Configure Nemori to work with your preferred AI provider
          </p>
        </div>

        {/* Appearance */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">{t('settings.appearance')}</h2>
          <div className="p-5 rounded-xl glass-card space-y-6">
            {/* Theme */}
            <div className="space-y-3">
              <label className="text-sm font-medium">{t('settings.theme')}</label>
              <div className="flex gap-2">
                <ThemeButton
                  active={theme === 'light'}
                  onClick={() => setTheme('light')}
                  icon={<Sun className="w-4 h-4" />}
                  label={t('settings.themeLight')}
                />
                <ThemeButton
                  active={theme === 'dark'}
                  onClick={() => setTheme('dark')}
                  icon={<Moon className="w-4 h-4" />}
                  label={t('settings.themeDark')}
                />
                <ThemeButton
                  active={theme === 'system'}
                  onClick={() => setTheme('system')}
                  icon={<Monitor className="w-4 h-4" />}
                  label={t('settings.themeSystem')}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {language === 'zh' ? '选择您喜欢的颜色主题。跟随系统将自动适应您的操作系统设置。' : 'Choose your preferred color theme. System will follow your OS settings.'}
              </p>
            </div>

            {/* Language */}
            <div className="space-y-3">
              <label className="text-sm font-medium">{t('settings.language')}</label>
              <div className="flex gap-2">
                <LanguageButton
                  active={language === 'en'}
                  onClick={() => setLanguage('en')}
                  icon={<Globe className="w-4 h-4" />}
                  label="English"
                />
                <LanguageButton
                  active={language === 'zh'}
                  onClick={() => setLanguage('zh')}
                  icon={<Globe className="w-4 h-4" />}
                  label="中文"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {language === 'zh' ? '选择界面语言。同时影响AI生成内容的语言。' : 'Choose the interface language. Also affects the language of AI generated content.'}
              </p>
            </div>
          </div>
        </section>

        {/* LLM Configuration */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">LLM Configuration</h2>
            <div className="flex items-center gap-2">
              <div
                className={`w-2.5 h-2.5 rounded-full ${llmConfigured ? 'bg-primary' : 'bg-amber-500'}`}
              />
              <span className="text-sm text-muted-foreground">
                {llmConfigured ? 'Configured' : 'Not configured'}
              </span>
            </div>
          </div>

          {/* Chat Model Configuration */}
          <div className="space-y-4 p-5 rounded-xl glass-card">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Chat Model</h3>

            {/* Chat API Key */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Chat API Key</label>
                {settings.chat_api_key && !isEditingChatApiKey && (
                  <span className="text-xs text-primary flex items-center gap-1">
                    <Check className="w-3 h-3" />
                    Configured
                  </span>
                )}
              </div>
              <div className="relative">
                <input
                  type={showChatApiKey ? 'text' : 'password'}
                  value={isEditingChatApiKey ? chatApiKey : (settings.chat_api_key || '')}
                  onChange={(e) => {
                    setChatApiKey(e.target.value)
                    setIsEditingChatApiKey(true)
                  }}
                  onFocus={() => {
                    if (!isEditingChatApiKey) {
                      setChatApiKey('')
                      setIsEditingChatApiKey(true)
                    }
                  }}
                  placeholder="Enter your Chat API key"
                  className="w-full px-4 py-2.5 pr-10 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
                />
                <button
                  onClick={() => setShowChatApiKey(!showChatApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showChatApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                Get your API key from{' '}
                <button
                  onClick={() => handleOpenExternal('https://openrouter.ai/keys')}
                  className="text-primary hover:underline inline-flex items-center gap-1"
                >
                  OpenRouter <ExternalLink className="w-3 h-3" />
                </button>
              </p>
            </div>

            {/* Chat Base URL */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Chat Base URL</label>
              <input
                type="text"
                value={chatBaseUrl}
                onChange={(e) => setChatBaseUrl(e.target.value)}
                placeholder="https://openrouter.ai/api/v1"
                className="w-full px-4 py-2.5 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
              />
            </div>

            {/* Chat Model */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Chat Model</label>
              <input
                type="text"
                value={chatModel}
                onChange={(e) => setChatModel(e.target.value)}
                placeholder="google/gemini-3-flash-preview"
                className="w-full px-4 py-2.5 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
              />
              <p className="text-xs text-muted-foreground">
                Recommended: google/gemini-3-flash-preview
              </p>
            </div>
          </div>

          {/* Embedding Model Configuration */}
          <div className="space-y-4 p-5 rounded-xl glass-card">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Embedding Model</h3>

            {/* Embedding API Key */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">Embedding API Key</label>
                {settings.embedding_api_key && !isEditingEmbeddingApiKey && (
                  <span className="text-xs text-primary flex items-center gap-1">
                    <Check className="w-3 h-3" />
                    Configured
                  </span>
                )}
              </div>
              <div className="relative">
                <input
                  type={showEmbeddingApiKey ? 'text' : 'password'}
                  value={isEditingEmbeddingApiKey ? embeddingApiKey : (settings.embedding_api_key || '')}
                  onChange={(e) => {
                    setEmbeddingApiKey(e.target.value)
                    setIsEditingEmbeddingApiKey(true)
                  }}
                  onFocus={() => {
                    if (!isEditingEmbeddingApiKey) {
                      setEmbeddingApiKey('')
                      setIsEditingEmbeddingApiKey(true)
                    }
                  }}
                  placeholder="Enter your Embedding API key"
                  className="w-full px-4 py-2.5 pr-10 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
                />
                <button
                  onClick={() => setShowEmbeddingApiKey(!showEmbeddingApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showEmbeddingApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                Get your API key from{' '}
                <button
                  onClick={() => handleOpenExternal('https://openrouter.ai/settings/keys')}
                  className="text-primary hover:underline inline-flex items-center gap-1"
                >
                  OpenRouter <ExternalLink className="w-3 h-3" />
                </button>
              </p>
            </div>

            {/* Embedding Base URL */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Embedding Base URL</label>
              <input
                type="text"
                value={embeddingBaseUrl}
                onChange={(e) => setEmbeddingBaseUrl(e.target.value)}
                placeholder="https://openrouter.ai/api/v1"
                className="w-full px-4 py-2.5 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
              />
            </div>

            {/* Embedding Model */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Embedding Model</label>
              <input
                type="text"
                value={embeddingModel}
                onChange={(e) => setEmbeddingModel(e.target.value)}
                placeholder="google/gemini-embedding-001"
                className="w-full px-4 py-2.5 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
              />
              <p className="text-xs text-muted-foreground">
                OpenRouter: google/gemini-embedding-001, baai/bge-base-en-v1.5
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="space-y-4 p-5 rounded-xl glass-card">
            {/* Test result */}
            {testResult && (
              <div
                className={`flex items-center gap-2 p-3 rounded-lg ${
                  testResult.success
                    ? 'bg-primary/10 text-primary dark:bg-primary/20'
                    : 'bg-destructive/10 text-destructive dark:bg-destructive/20'
                }`}
              >
                {testResult.success ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <AlertCircle className="w-4 h-4" />
                )}
                <span className="text-sm">{testResult.message}</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={handleSaveLLMConfig}
                disabled={isSaving}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all duration-200 shadow-warm"
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>Save All</span>
              </button>
              <button
                onClick={handleTestConnection}
                disabled={isTesting || !llmConfigured}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-muted/60 hover:bg-muted disabled:opacity-50 transition-all duration-200 shadow-warm-sm"
              >
                {isTesting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                <span>Test Connection</span>
              </button>
            </div>
          </div>
        </section>

        {/* App Settings */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Application Settings</h2>

          <div className="space-y-4 p-5 rounded-xl glass-card">
            {/* Capture Interval */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Screenshot Capture Interval (ms)</label>
              <input
                type="number"
                value={captureInterval}
                onChange={(e) => setCaptureInterval(Number(e.target.value))}
                min={1000}
                step={1000}
                className="w-full px-4 py-2.5 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
              />
              <p className="text-xs text-muted-foreground">
                How often to capture screenshots (default: 10000ms = 10s)
              </p>
            </div>

            {/* Batch Size */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Memory Batch Size</label>
              <input
                type="number"
                value={batchSize}
                onChange={(e) => setBatchSize(Number(e.target.value))}
                min={5}
                max={100}
                className="w-full px-4 py-2.5 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
              />
              <p className="text-xs text-muted-foreground">
                Number of events to accumulate before generating memories (default: 20)
              </p>
            </div>

            {/* Similarity Threshold */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Image Similarity Threshold</label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  value={similarityThreshold}
                  onChange={(e) => setSimilarityThreshold(Number(e.target.value))}
                  min={0.5}
                  max={1}
                  step={0.01}
                  className="flex-1 accent-primary"
                />
                <span className="text-sm font-mono w-16 px-2 py-1 rounded bg-muted/50">{(similarityThreshold * 100).toFixed(0)}%</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Skip screenshots that are this similar to the previous one (default: 95%)
              </p>
            </div>

            {/* Max Storage */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Local Storage (MB)</label>
              <input
                type="number"
                value={maxStorage}
                onChange={(e) => setMaxStorage(Number(e.target.value))}
                min={100}
                step={100}
                className="w-full px-4 py-2.5 rounded-lg border border-border/50 bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all duration-200"
              />
              <p className="text-xs text-muted-foreground">
                Maximum storage for screenshots (default: 500 MB)
              </p>
            </div>

            {/* App settings result */}
            {appResult && (
              <div
                className={`flex items-center gap-2 p-3 rounded-lg ${
                  appResult.success
                    ? 'bg-primary/10 text-primary dark:bg-primary/20'
                    : 'bg-destructive/10 text-destructive dark:bg-destructive/20'
                }`}
              >
                {appResult.success ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <AlertCircle className="w-4 h-4" />
                )}
                <span className="text-sm">{appResult.message}</span>
              </div>
            )}

            {/* Save button */}
            <div className="pt-2">
              <button
                onClick={handleSaveAppSettings}
                disabled={isSavingApp}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all duration-200 shadow-warm"
              >
                {isSavingApp ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                <span>Save Settings</span>
              </button>
            </div>
          </div>
        </section>

        {/* User Profile */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <User className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">User Profile</h2>
          </div>

          <div className="space-y-4 p-5 rounded-xl glass-card">
            <p className="text-sm text-muted-foreground">
              Your profile is automatically built from semantic memories. It helps personalize AI responses.
            </p>

            {/* Profile Stats */}
            {profileContext && (
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
                  <p className="text-2xl font-bold text-primary">{profileContext.total_items}</p>
                  <p className="text-xs text-muted-foreground">Total Items</p>
                </div>
                <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
                  <p className="text-2xl font-bold text-primary">{Object.keys(profileContext.categories).length}</p>
                  <p className="text-xs text-muted-foreground">Categories</p>
                </div>
              </div>
            )}

            {/* Profile Summary Preview */}
            {profileContext?.summary && profileContext.summary !== 'No profile data yet.' && (
              <div className="p-4 rounded-xl bg-muted/30 border border-border/50">
                <p className="text-xs font-medium text-muted-foreground mb-2">Profile Summary</p>
                <p className="text-sm whitespace-pre-wrap">{profileContext.summary}</p>
              </div>
            )}

            {/* Profile result */}
            {profileResult && (
              <div
                className={`flex items-center gap-2 p-3 rounded-lg ${
                  profileResult.success
                    ? 'bg-primary/10 text-primary dark:bg-primary/20'
                    : 'bg-destructive/10 text-destructive dark:bg-destructive/20'
                }`}
              >
                {profileResult.success ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <AlertCircle className="w-4 h-4" />
                )}
                <span className="text-sm">{profileResult.message}</span>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={handleUpdateProfile}
                disabled={isUpdatingProfile}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all duration-200 shadow-warm"
              >
                {isUpdatingProfile ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                <span>Update from Memories</span>
              </button>
              <button
                onClick={handleClearProfile}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20 transition-all duration-200"
              >
                <Trash2 className="w-4 h-4" />
                <span>Clear</span>
              </button>
            </div>
          </div>
        </section>

        {/* Data Directory Info */}
        {appSettings && (
          <section className="space-y-4">
            <h2 className="text-lg font-semibold">Storage Info</h2>
            <div className="p-5 rounded-xl glass-card">
              <InfoRow label="Data Directory" value={appSettings.data_dir} />
            </div>
          </section>
        )}

        {/* About */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">About</h2>

          <div className="p-5 rounded-xl glass-card space-y-3">
            <InfoRow label="Application" value="Nemori" />
            <InfoRow label="Version" value="1.0.0" />
            <InfoRow label="Author" value="nemori-ai" />
            <div className="pt-2">
              <button
                onClick={() => handleOpenExternal('https://github.com/nemori-ai')}
                className="text-sm text-primary hover:underline inline-flex items-center gap-1 transition-colors"
              >
                View on GitHub <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-mono">{value}</span>
    </div>
  )
}

function ThemeButton({
  active,
  onClick,
  icon,
  label
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}): JSX.Element {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border transition-all duration-200 ${
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-border/50 bg-background/80 text-foreground hover:border-primary/50 hover:bg-primary/5'
      }`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}

function LanguageButton({
  active,
  onClick,
  icon,
  label
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}): JSX.Element {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border transition-all duration-200 ${
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-border/50 bg-background/80 text-foreground hover:border-primary/50 hover:bg-primary/5'
      }`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}
