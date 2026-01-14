import { useState, useEffect } from 'react'
import {
  Play,
  Moon,
  Sun,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Calendar,
  ListTodo,
  User,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  FileText,
  Zap,
  AlertCircle,
  X,
  Eye,
  Code,
  BookOpen,
  Trash2
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import {
  api,
  ProactiveAgentStatus,
  ProactiveTask,
  ProfileFilesResponse,
  ProfileSummaryResponse,
  ProfileFileResponse
} from '../services/api'
import { useLanguage } from '../contexts/LanguageContext'

type AgentState = 'sleeping' | 'waking_up' | 'awake' | 'working' | 'going_to_sleep'

const stateConfig: Record<AgentState, { labelKey: string; color: string; icon: typeof Sun }> = {
  sleeping: { labelKey: 'proactive.state.sleeping', color: 'text-blue-500 bg-blue-500/10', icon: Moon },
  waking_up: { labelKey: 'proactive.state.wakingUp', color: 'text-amber-500 bg-amber-500/10', icon: Loader2 },
  awake: { labelKey: 'proactive.state.awake', color: 'text-green-500 bg-green-500/10', icon: Sun },
  working: { labelKey: 'proactive.state.working', color: 'text-purple-500 bg-purple-500/10', icon: Zap },
  going_to_sleep: { labelKey: 'proactive.state.goingToSleep', color: 'text-blue-400 bg-blue-400/10', icon: Moon }
}

const taskStatusConfig: Record<string, { labelKey: string; color: string; icon: typeof CheckCircle2 }> = {
  pending: { labelKey: 'proactive.taskStatus.pending', color: 'text-gray-500', icon: Clock },
  scheduled: { labelKey: 'proactive.taskStatus.scheduled', color: 'text-blue-500', icon: Calendar },
  in_progress: { labelKey: 'proactive.taskStatus.inProgress', color: 'text-purple-500', icon: Loader2 },
  completed: { labelKey: 'proactive.taskStatus.completed', color: 'text-green-500', icon: CheckCircle2 },
  failed: { labelKey: 'proactive.taskStatus.failed', color: 'text-red-500', icon: XCircle },
  cancelled: { labelKey: 'proactive.taskStatus.cancelled', color: 'text-gray-400', icon: XCircle }
}

/**
 * Strip YAML front matter from markdown content.
 * Front matter is delimited by --- at the start and end.
 */
const stripFrontMatter = (content: string): string => {
  const frontMatterRegex = /^---\s*\n[\s\S]*?\n---\s*\n?/
  return content.replace(frontMatterRegex, '').trim()
}

export default function ProactivePage(): JSX.Element {
  const { t } = useLanguage()
  const [status, setStatus] = useState<ProactiveAgentStatus | null>(null)
  const [tasks, setTasks] = useState<ProactiveTask[]>([])
  const [taskHistory, setTaskHistory] = useState<ProactiveTask[]>([])
  const [profileFiles, setProfileFiles] = useState<ProfileFilesResponse | null>(null)
  const [profileSummary, setProfileSummary] = useState<ProfileSummaryResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isActionLoading, setIsActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'status' | 'tasks' | 'profile'>('status')
  const [selectedFile, setSelectedFile] = useState<ProfileFileResponse | null>(null)
  const [isFileLoading, setIsFileLoading] = useState(false)
  const [viewMode, setViewMode] = useState<'preview' | 'code'>('preview')
  const [selectedTask, setSelectedTask] = useState<ProactiveTask | null>(null)
  const [historyPage, setHistoryPage] = useState(0)
  const historyPageSize = 10

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [])

  const loadData = async (): Promise<void> => {
    try {
      const [statusRes, tasksRes, historyRes, filesRes, summaryRes] = await Promise.all([
        api.getProactiveAgentStatus().catch(() => null),
        api.getProactiveTasks().catch(() => ({ tasks: [] })),
        api.getProactiveTaskHistory(20).catch(() => ({ history: [] })),
        api.getProfileFiles().catch(() => null),
        api.getProfileFilesSummary().catch(() => null)
      ])

      if (statusRes) setStatus(statusRes)
      setTasks(tasksRes.tasks || [])
      setTaskHistory(historyRes.history || [])
      if (filesRes) setProfileFiles(filesRes)
      if (summaryRes) setProfileSummary(summaryRes)
      setError(null)
    } catch (err: any) {
      setError(err.message || 'Failed to load data')
    } finally {
      setIsLoading(false)
    }
  }

  const handleWake = async (): Promise<void> => {
    setIsActionLoading(true)
    try {
      await api.wakeProactiveAgent('User woke agent from UI')
      await loadData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleSleep = async (): Promise<void> => {
    setIsActionLoading(true)
    try {
      await api.sleepProactiveAgent('User requested sleep from UI')
      await loadData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleStartAgent = async (): Promise<void> => {
    setIsActionLoading(true)
    try {
      await api.startProactiveAgent()
      await loadData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleInitializeProfile = async (): Promise<void> => {
    setIsActionLoading(true)
    try {
      await api.initializeProfile()
      await loadData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleRunTask = async (taskType: string): Promise<void> => {
    setIsActionLoading(true)
    try {
      await api.runProactiveTaskNow(taskType)
      await loadData()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleViewFile = async (filename: string): Promise<void> => {
    setIsFileLoading(true)
    try {
      const fileData = await api.getProfileFile(filename)
      setSelectedFile(fileData)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsFileLoading(false)
    }
  }

  const closeFileViewer = (): void => {
    setSelectedFile(null)
    setViewMode('preview')
  }

  const closeTaskViewer = (): void => {
    setSelectedTask(null)
  }

  const handleDeleteHistory = async (taskId: string, e: React.MouseEvent): Promise<void> => {
    e.stopPropagation() // Prevent opening task detail modal
    if (!confirm(t('proactive.confirmDeleteHistory'))) return

    try {
      await api.deleteProactiveTaskHistory(taskId)
      await loadData()
    } catch (err: any) {
      setError(err.message)
    }
  }

  // Sort tasks by scheduled time (earliest first)
  const sortedTasks = [...tasks].sort((a, b) => {
    if (!a.scheduled_time && !b.scheduled_time) return 0
    if (!a.scheduled_time) return 1
    if (!b.scheduled_time) return -1
    return new Date(a.scheduled_time).getTime() - new Date(b.scheduled_time).getTime()
  })

  // Paginate history
  const totalHistoryPages = Math.ceil(taskHistory.length / historyPageSize)
  const paginatedHistory = taskHistory.slice(
    historyPage * historyPageSize,
    (historyPage + 1) * historyPageSize
  )

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    )
  }

  const agentState = (status?.agent?.state || 'sleeping') as AgentState
  const stateInfo = stateConfig[agentState] || stateConfig.sleeping
  const StateIcon = stateInfo.icon

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">{t('proactive.title')}</h1>
            <p className="text-muted-foreground text-sm mt-1">
              {t('proactive.subtitle')}
            </p>
          </div>
          <button
            onClick={loadData}
            disabled={isLoading}
            className="p-2 rounded-lg hover:bg-muted/60 transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="flex items-center gap-2 p-4 rounded-xl bg-destructive/10 text-destructive">
            <AlertCircle className="w-5 h-5" />
            <span className="text-sm">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-sm hover:underline">
              {t('proactive.dismiss')}
            </button>
          </div>
        )}

        {/* Agent Status Card */}
        <div className="p-6 rounded-xl glass-card">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-xl ${stateInfo.color}`}>
                <StateIcon className={`w-6 h-6 ${agentState === 'waking_up' || agentState === 'working' ? 'animate-spin' : ''}`} />
              </div>
              <div>
                <h2 className="text-lg font-semibold">{t(stateInfo.labelKey as any)}</h2>
                <p className="text-sm text-muted-foreground">
                  {status?.agent?.tasks_completed_today || 0} {t('proactive.tasksCompletedToday')}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              {agentState === 'sleeping' ? (
                <button
                  onClick={handleWake}
                  disabled={isActionLoading}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sun className="w-4 h-4" />}
                  {t('proactive.wakeUp')}
                </button>
              ) : (
                <button
                  onClick={handleSleep}
                  disabled={isActionLoading || agentState === 'working'}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-muted hover:bg-muted/80 disabled:opacity-50 transition-colors"
                >
                  {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Moon className="w-4 h-4" />}
                  {t('proactive.sleep')}
                </button>
              )}
              {!status && (
                <button
                  onClick={handleStartAgent}
                  disabled={isActionLoading}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  {t('proactive.startAgent')}
                </button>
              )}
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
              <p className="text-2xl font-bold text-primary">{status?.scheduler?.tasks_in_queue || 0}</p>
              <p className="text-xs text-muted-foreground">{t('proactive.tasksInQueue')}</p>
            </div>
            <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
              <p className="text-2xl font-bold text-primary">{profileFiles?.total_files || 0}</p>
              <p className="text-xs text-muted-foreground">{t('proactive.profileFiles')}</p>
            </div>
            <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
              <p className="text-2xl font-bold text-primary">{status?.wakeup?.enabled_triggers || 0}</p>
              <p className="text-xs text-muted-foreground">{t('proactive.activeTriggers')}</p>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 p-1 rounded-xl bg-muted/30">
          {[
            { id: 'status', labelKey: 'proactive.statusTab', icon: Zap },
            { id: 'tasks', labelKey: 'proactive.tasksTab', icon: ListTodo },
            { id: 'profile', labelKey: 'proactive.profileTab', icon: User }
          ].map((tab) => {
            const TabIcon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg transition-colors ${
                  activeTab === tab.id
                    ? 'bg-background shadow-sm text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <TabIcon className="w-4 h-4" />
                {t(tab.labelKey as any)}
              </button>
            )
          })}
        </div>

        {/* Tab Content */}
        {activeTab === 'status' && (
          <div className="space-y-6">
            {/* Next Actions */}
            <div className="p-5 rounded-xl glass-card">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
                {t('proactive.nextScheduledActions')}
              </h3>
              <div className="space-y-3">
                {status?.wakeup?.next_trigger && (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                    <div className="flex items-center gap-3">
                      <Clock className="w-4 h-4 text-primary" />
                      <div>
                        <p className="text-sm font-medium">{status.wakeup.next_trigger.name}</p>
                        <p className="text-xs text-muted-foreground">{status.wakeup.next_trigger.type}</p>
                      </div>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {status.wakeup.next_trigger.time_until || t('proactive.soon')}
                    </span>
                  </div>
                )}
                {status?.scheduler?.next_task && (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                    <div className="flex items-center gap-3">
                      <ListTodo className="w-4 h-4 text-purple-500" />
                      <div>
                        <p className="text-sm font-medium">{status.scheduler.next_task.title}</p>
                        <p className="text-xs text-muted-foreground">{status.scheduler.next_task.type}</p>
                      </div>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {t('proactive.priority')}: {status.scheduler.next_task.priority}
                    </span>
                  </div>
                )}
                {!status?.wakeup?.next_trigger && !status?.scheduler?.next_task && (
                  <p className="text-sm text-muted-foreground text-center py-4">{t('proactive.noScheduledActions')}</p>
                )}
              </div>
            </div>

            {/* Recent Transitions */}
            {status?.agent?.recent_transitions && status.agent.recent_transitions.length > 0 && (
              <div className="p-5 rounded-xl glass-card">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
                  {t('proactive.recentActivity')}
                </h3>
                <div className="space-y-2">
                  {status.agent.recent_transitions.slice(-5).reverse().map((t, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      <span className="text-muted-foreground">{t.from}</span>
                      <span>→</span>
                      <span className="font-medium">{t.to}</span>
                      <span className="text-xs text-muted-foreground ml-auto">{t.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Quick Actions */}
            <div className="p-5 rounded-xl glass-card">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
                {t('proactive.quickActions')}
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleRunTask('self_reflection')}
                  disabled={isActionLoading || agentState === 'sleeping'}
                  className="flex items-center gap-2 p-3 rounded-lg bg-primary/10 dark:bg-primary/20 hover:bg-primary/20 dark:hover:bg-primary/30 disabled:opacity-50 transition-colors border border-primary/20 dark:border-primary/40"
                >
                  <User className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-foreground">{t('proactive.selfReflection')}</span>
                </button>
                <button
                  onClick={() => handleRunTask('learn_from_history')}
                  disabled={isActionLoading || agentState === 'sleeping'}
                  className="flex items-center gap-2 p-3 rounded-lg bg-muted/50 dark:bg-muted/30 hover:bg-muted/70 dark:hover:bg-muted/50 disabled:opacity-50 transition-colors border border-border/50"
                >
                  <Zap className="w-4 h-4 text-primary" />
                  <span className="text-sm text-foreground">{t('proactive.learnFromHistory')}</span>
                </button>
                <button
                  onClick={() => handleRunTask('summarize_period')}
                  disabled={isActionLoading || agentState === 'sleeping'}
                  className="flex items-center gap-2 p-3 rounded-lg bg-muted/50 dark:bg-muted/30 hover:bg-muted/70 dark:hover:bg-muted/50 disabled:opacity-50 transition-colors border border-border/50"
                >
                  <FileText className="w-4 h-4 text-primary" />
                  <span className="text-sm text-foreground">{t('proactive.summarizeToday')}</span>
                </button>
                <button
                  onClick={() => handleRunTask('discover_patterns')}
                  disabled={isActionLoading || agentState === 'sleeping'}
                  className="flex items-center gap-2 p-3 rounded-lg bg-muted/50 dark:bg-muted/30 hover:bg-muted/70 dark:hover:bg-muted/50 disabled:opacity-50 transition-colors border border-border/50"
                >
                  <ListTodo className="w-4 h-4 text-primary" />
                  <span className="text-sm text-foreground">{t('proactive.discoverPatterns')}</span>
                </button>
                <button
                  onClick={() => handleRunTask('health_check')}
                  disabled={isActionLoading || agentState === 'sleeping'}
                  className="flex items-center gap-2 p-3 rounded-lg bg-muted/50 dark:bg-muted/30 hover:bg-muted/70 dark:hover:bg-muted/50 disabled:opacity-50 transition-colors border border-border/50"
                >
                  <CheckCircle2 className="w-4 h-4 text-primary" />
                  <span className="text-sm text-foreground">{t('proactive.healthCheck')}</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className="space-y-6">
            {/* Active Tasks */}
            <div className="p-5 rounded-xl glass-card">
              <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
                {t('proactive.taskQueue')} ({tasks.length})
              </h3>
              {sortedTasks.length > 0 ? (
                <div className="space-y-3">
                  {sortedTasks.map((task, index) => {
                    const statusInfo = taskStatusConfig[task.status] || taskStatusConfig.pending
                    const StatusIcon = statusInfo.icon
                    return (
                      <div key={`queue-${task.id}-${index}`} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                        <div className="flex items-center gap-3">
                          <StatusIcon className={`w-4 h-4 ${statusInfo.color} ${task.status === 'in_progress' ? 'animate-spin' : ''}`} />
                          <div>
                            <p className="text-sm font-medium">{task.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {task.type} • {t('proactive.priority')}: {task.priority}
                              {task.scheduled_time && (
                                <span className="ml-2 text-primary">
                                  @ {new Date(task.scheduled_time).toLocaleString('zh-CN', {
                                    month: 'numeric',
                                    day: 'numeric',
                                    hour: '2-digit',
                                    minute: '2-digit'
                                  })}
                                </span>
                              )}
                            </p>
                          </div>
                        </div>
                        <span className={`text-xs ${statusInfo.color}`}>{t(statusInfo.labelKey as any)}</span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">{t('proactive.noTasksInQueue')}</p>
              )}
            </div>

            {/* Task History */}
            <div className="p-5 rounded-xl glass-card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                  {t('proactive.recentHistory')} ({taskHistory.length})
                </h3>
                {totalHistoryPages > 1 && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setHistoryPage(p => Math.max(0, p - 1))}
                      disabled={historyPage === 0}
                      className="p-1 rounded hover:bg-muted/50 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-xs text-muted-foreground">
                      {historyPage + 1} / {totalHistoryPages}
                    </span>
                    <button
                      onClick={() => setHistoryPage(p => Math.min(totalHistoryPages - 1, p + 1))}
                      disabled={historyPage >= totalHistoryPages - 1}
                      className="p-1 rounded hover:bg-muted/50 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
              {paginatedHistory.length > 0 ? (
                <div className="space-y-3">
                  {paginatedHistory.map((task, index) => {
                    const statusInfo = taskStatusConfig[task.status] || taskStatusConfig.completed
                    const StatusIcon = statusInfo.icon
                    return (
                      <div
                        key={`history-${task.id}-${index}`}
                        className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 cursor-pointer transition-colors group"
                        onClick={() => setSelectedTask(task)}
                      >
                        <div className="flex items-center gap-3">
                          <StatusIcon className={`w-4 h-4 ${statusInfo.color}`} />
                          <div>
                            <p className="text-sm font-medium">{task.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {task.execution_time_ms ? `${task.execution_time_ms}ms` : 'N/A'}
                              {task.completed_at && ` • ${new Date(task.completed_at).toLocaleString()}`}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs ${statusInfo.color}`}>{t(statusInfo.labelKey as any)}</span>
                          <Eye className="w-4 h-4 text-muted-foreground" />
                          <button
                            onClick={(e) => handleDeleteHistory(task.id, e)}
                            className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-red-500 transition-opacity"
                            title={t('proactive.deleteHistory')}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">{t('proactive.noTaskHistory')}</p>
              )}
            </div>
          </div>
        )}

        {activeTab === 'profile' && (
          <div className="space-y-6">
            {/* Profile Summary */}
            {profileSummary && (
              <div className="p-5 rounded-xl glass-card">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                    {t('proactive.profileSummary')}
                  </h3>
                  <button
                    onClick={handleInitializeProfile}
                    disabled={isActionLoading}
                    className="text-xs text-primary hover:underline"
                  >
                    {t('proactive.initializeProfile')}
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
                    <p className="text-2xl font-bold text-primary">{profileSummary.total_files}</p>
                    <p className="text-xs text-muted-foreground">{t('proactive.totalFiles')}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
                    <p className="text-2xl font-bold text-primary">
                      {Object.keys(profileSummary.categories).length}
                    </p>
                    <p className="text-xs text-muted-foreground">{t('proactive.categories')}</p>
                  </div>
                </div>
                {profileSummary.key_facts && profileSummary.key_facts.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-2">{t('proactive.keyFacts')}</p>
                    <ul className="space-y-1">
                      {profileSummary.key_facts.slice(0, 5).map((fact, i) => (
                        <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                          <span className="text-primary mt-1">•</span>
                          <span>{fact}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Profile Files by Layer */}
            {profileFiles && Object.entries(profileFiles.files_by_layer).length > 0 && (
              <div className="p-5 rounded-xl glass-card">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
                  {t('proactive.profileFilesByLayer')}
                </h3>
                <div className="space-y-4">
                  {Object.entries(profileFiles.files_by_layer).map(([layer, files]) => (
                    <div key={layer}>
                      <p className="text-sm font-medium mb-2">{layer} ({files.length})</p>
                      <div className="space-y-2 pl-4">
                        {files.slice(0, 5).map((file) => (
                          <div
                            key={file.relative_path}
                            className="flex items-center justify-between p-2 rounded-lg bg-muted/20 hover:bg-muted/30 transition-colors cursor-pointer"
                            onClick={() => handleViewFile(file.relative_path)}
                          >
                            <div className="flex items-center gap-2">
                              <FileText className="w-4 h-4 text-muted-foreground" />
                              <div>
                                <p className="text-sm font-medium">{file.title}</p>
                                <p className="text-xs text-muted-foreground truncate max-w-[300px]">
                                  {file.summary}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                {Math.round(file.confidence * 100)}%
                              </span>
                              <Eye className="w-4 h-4 text-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                          </div>
                        ))}
                        {files.length > 5 && (
                          <p className="text-xs text-muted-foreground pl-6">
                            +{files.length - 5} {t('proactive.moreFiles')}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty State */}
            {(!profileFiles || Object.entries(profileFiles.files_by_layer).length === 0) && (
              <div className="p-8 rounded-xl glass-card text-center">
                <User className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-semibold mb-2">{t('proactive.noProfileFilesYet')}</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {t('proactive.noProfileFilesDesc')}
                </p>
                <button
                  onClick={handleInitializeProfile}
                  disabled={isActionLoading}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  {t('proactive.initializeProfile')}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* File Content Modal */}
      {(selectedFile || isFileLoading) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-background rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div>
                <h3 className="font-semibold">
                  {selectedFile?.metadata?.title || selectedFile?.filename || 'Loading...'}
                </h3>
                {selectedFile?.metadata && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Layer: {selectedFile.metadata.layer} • Confidence: {Math.round((selectedFile.metadata.confidence || 0) * 100)}%
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {/* View Mode Toggle */}
                <div className="flex rounded-lg bg-muted/50 p-1">
                  <button
                    onClick={() => setViewMode('preview')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                      viewMode === 'preview'
                        ? 'bg-background shadow-sm text-foreground'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <BookOpen className="w-4 h-4" />
                    {t('proactive.preview')}
                  </button>
                  <button
                    onClick={() => setViewMode('code')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                      viewMode === 'code'
                        ? 'bg-background shadow-sm text-foreground'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <Code className="w-4 h-4" />
                    {t('proactive.code')}
                  </button>
                </div>
                <button
                  onClick={closeFileViewer}
                  className="p-2 rounded-lg hover:bg-muted/60 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-auto p-6">
              {isFileLoading ? (
                <div className="flex items-center justify-center h-48">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                </div>
              ) : selectedFile?.content ? (
                viewMode === 'preview' ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ className, children, ...props }) {
                          const match = /language-(\w+)/.exec(className || '')
                          const isInline = !match
                          return isInline ? (
                            <code className="px-1.5 py-0.5 rounded bg-muted text-sm" {...props}>
                              {children}
                            </code>
                          ) : (
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              className="rounded-lg !mt-2 !mb-4"
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          )
                        },
                        h1: ({ children }) => (
                          <h1 className="text-2xl font-bold mt-6 mb-4 text-foreground">{children}</h1>
                        ),
                        h2: ({ children }) => (
                          <h2 className="text-xl font-semibold mt-5 mb-3 text-foreground border-b border-border pb-2">{children}</h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="text-lg font-medium mt-4 mb-2 text-foreground">{children}</h3>
                        ),
                        p: ({ children }) => (
                          <p className="text-foreground/90 leading-relaxed mb-3">{children}</p>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc list-inside space-y-1 mb-3 text-foreground/90">{children}</ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal list-inside space-y-1 mb-3 text-foreground/90">{children}</ol>
                        ),
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-4 border-primary/50 pl-4 italic text-muted-foreground my-4">{children}</blockquote>
                        ),
                        table: ({ children }) => (
                          <div className="overflow-x-auto my-4">
                            <table className="min-w-full border border-border rounded-lg">{children}</table>
                          </div>
                        ),
                        th: ({ children }) => (
                          <th className="px-4 py-2 bg-muted/50 border-b border-border text-left font-semibold">{children}</th>
                        ),
                        td: ({ children }) => (
                          <td className="px-4 py-2 border-b border-border/50">{children}</td>
                        ),
                        hr: () => <hr className="my-6 border-border" />,
                        a: ({ href, children }) => (
                          <a href={href} className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">{children}</a>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-foreground">{children}</strong>
                        )
                      }}
                    >
                      {stripFrontMatter(selectedFile.content)}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <SyntaxHighlighter
                    language="markdown"
                    style={oneDark}
                    customStyle={{
                      margin: 0,
                      borderRadius: '0.5rem',
                      fontSize: '0.875rem'
                    }}
                    showLineNumbers
                  >
                    {selectedFile.content}
                  </SyntaxHighlighter>
                )
              ) : (
                <p className="text-muted-foreground text-center py-8">No content available</p>
              )}
            </div>

            {/* Modal Footer */}
            {selectedFile?.metadata && selectedFile.metadata.keywords?.length > 0 && (
              <div className="p-4 border-t border-border bg-muted/30">
                <div className="flex flex-wrap gap-2">
                  {selectedFile.metadata.keywords.map((keyword: string, i: number) => (
                    <span key={i} className="px-2 py-1 text-xs rounded-full bg-primary/10 text-primary">
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Task Detail Modal */}
      {selectedTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-background rounded-xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center gap-3">
                {(() => {
                  const statusInfo = taskStatusConfig[selectedTask.status] || taskStatusConfig.completed
                  const StatusIcon = statusInfo.icon
                  return (
                    <>
                      <div className={`p-2 rounded-lg ${statusInfo.color} bg-current/10`}>
                        <StatusIcon className={`w-5 h-5 ${statusInfo.color}`} />
                      </div>
                      <div>
                        <h3 className="font-semibold">{selectedTask.title}</h3>
                        <p className="text-xs text-muted-foreground">
                          {selectedTask.type} • {t(statusInfo.labelKey as any)}
                        </p>
                      </div>
                    </>
                  )
                })()}
              </div>
              <button
                onClick={closeTaskViewer}
                className="p-2 rounded-lg hover:bg-muted/60 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-auto p-4 space-y-4">
              {/* Task Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded-lg bg-muted/30">
                  <p className="text-xs text-muted-foreground mb-1">{t('proactive.priority')}</p>
                  <p className="text-sm font-medium">{selectedTask.priority}</p>
                </div>
                <div className="p-3 rounded-lg bg-muted/30">
                  <p className="text-xs text-muted-foreground mb-1">{t('proactive.executionTime')}</p>
                  <p className="text-sm font-medium">
                    {selectedTask.execution_time_ms ? `${selectedTask.execution_time_ms}ms` : 'N/A'}
                  </p>
                </div>
                {selectedTask.created_at && (
                  <div className="p-3 rounded-lg bg-muted/30">
                    <p className="text-xs text-muted-foreground mb-1">{t('proactive.created')}</p>
                    <p className="text-sm font-medium">
                      {new Date(selectedTask.created_at).toLocaleString()}
                    </p>
                  </div>
                )}
                {selectedTask.completed_at && (
                  <div className="p-3 rounded-lg bg-muted/30">
                    <p className="text-xs text-muted-foreground mb-1">{t('proactive.completed')}</p>
                    <p className="text-sm font-medium">
                      {new Date(selectedTask.completed_at).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>

              {/* Description */}
              {selectedTask.description && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">{t('proactive.description')}</p>
                  <p className="text-sm text-foreground/90 p-3 rounded-lg bg-muted/30">
                    {selectedTask.description}
                  </p>
                </div>
              )}

              {/* Result */}
              {selectedTask.result && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">{t('proactive.result')}</p>
                  <div className="p-4 rounded-lg bg-green-500/10 dark:bg-green-500/5 border border-green-500/20">
                    <div className="max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: ({ children }) => (
                            <h1 className="text-lg font-bold mt-4 mb-2 text-foreground">{children}</h1>
                          ),
                          h2: ({ children }) => (
                            <h2 className="text-base font-semibold mt-3 mb-2 text-foreground">{children}</h2>
                          ),
                          h3: ({ children }) => (
                            <h3 className="text-sm font-medium mt-2 mb-1 text-foreground">{children}</h3>
                          ),
                          p: ({ children }) => (
                            <p className="text-sm text-foreground leading-relaxed mb-2">{children}</p>
                          ),
                          ul: ({ children }) => (
                            <ul className="list-disc list-inside space-y-1 mb-2 text-sm text-foreground">{children}</ul>
                          ),
                          ol: ({ children }) => (
                            <ol className="list-decimal list-inside space-y-1 mb-2 text-sm text-foreground">{children}</ol>
                          ),
                          li: ({ children }) => (
                            <li className="text-sm text-foreground">{children}</li>
                          ),
                          strong: ({ children }) => (
                            <strong className="font-bold text-foreground">{children}</strong>
                          ),
                          code({ className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || '')
                            const isInline = !match
                            return isInline ? (
                              <code className="px-1 py-0.5 rounded bg-muted/50 text-xs font-mono" {...props}>
                                {children}
                              </code>
                            ) : (
                              <SyntaxHighlighter
                                style={oneDark}
                                language={match[1]}
                                PreTag="div"
                                className="rounded-lg !mt-2 !mb-3 text-xs"
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            )
                          }
                        }}
                      >
                        {selectedTask.result}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}

              {/* Error */}
              {selectedTask.error && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">{t('proactive.error')}</p>
                  <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                    <pre className="text-sm text-red-500 whitespace-pre-wrap font-mono">
                      {selectedTask.error}
                    </pre>
                  </div>
                </div>
              )}

              {/* Target File */}
              {selectedTask.target_file && (
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">{t('proactive.targetFile')}</p>
                  <p className="text-sm text-foreground/90 p-3 rounded-lg bg-muted/30 font-mono">
                    {selectedTask.target_file}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
