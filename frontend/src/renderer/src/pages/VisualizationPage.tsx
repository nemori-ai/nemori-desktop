import { useState, useEffect, useMemo } from 'react'
import {
  Calendar,
  Brain,
  TrendingUp,
  Activity,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Briefcase,
  DollarSign,
  HeartPulse,
  Home,
  Users,
  GraduationCap,
  Gamepad2,
  Sparkles
} from 'lucide-react'
import {
  api,
  TimelineData,
  HeatmapData,
  TopicData,
  VisualizationStats,
  TimelineEvent
} from '../services/api'
import { useLanguage } from '../contexts/LanguageContext'

type TabType = 'overview' | 'timeline' | 'heatmap'

// 8 life categories configuration
const CATEGORY_CONFIG: Record<string, {
  labelEn: string
  labelZh: string
  icon: React.ReactNode
  color: string
  bgColor: string
}> = {
  career: {
    labelEn: 'Career',
    labelZh: '事业',
    icon: <Briefcase className="w-4 h-4" />,
    color: '#3B82F6',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30'
  },
  finance: {
    labelEn: 'Finance',
    labelZh: '财务',
    icon: <DollarSign className="w-4 h-4" />,
    color: '#22C55E',
    bgColor: 'bg-green-100 dark:bg-green-900/30'
  },
  health: {
    labelEn: 'Health',
    labelZh: '健康',
    icon: <HeartPulse className="w-4 h-4" />,
    color: '#EF4444',
    bgColor: 'bg-red-100 dark:bg-red-900/30'
  },
  family: {
    labelEn: 'Family',
    labelZh: '家庭',
    icon: <Home className="w-4 h-4" />,
    color: '#EC4899',
    bgColor: 'bg-pink-100 dark:bg-pink-900/30'
  },
  social: {
    labelEn: 'Social',
    labelZh: '社交',
    icon: <Users className="w-4 h-4" />,
    color: '#F97316',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30'
  },
  growth: {
    labelEn: 'Growth',
    labelZh: '成长',
    icon: <GraduationCap className="w-4 h-4" />,
    color: '#8B5CF6',
    bgColor: 'bg-purple-100 dark:bg-purple-900/30'
  },
  leisure: {
    labelEn: 'Leisure',
    labelZh: '娱乐',
    icon: <Gamepad2 className="w-4 h-4" />,
    color: '#EAB308',
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/30'
  },
  spirit: {
    labelEn: 'Spirit',
    labelZh: '心灵',
    icon: <Sparkles className="w-4 h-4" />,
    color: '#6366F1',
    bgColor: 'bg-indigo-100 dark:bg-indigo-900/30'
  }
}

const CATEGORY_ORDER = ['career', 'finance', 'health', 'family', 'social', 'growth', 'leisure', 'spirit']

export default function VisualizationPage(): JSX.Element {
  const { t } = useLanguage()
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [stats, setStats] = useState<VisualizationStats | null>(null)
  const [timeline, setTimeline] = useState<TimelineData | null>(null)
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null)
  const [topics, setTopics] = useState<TopicData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [timelineDays, setTimelineDays] = useState(30)

  useEffect(() => {
    loadAllData()
  }, [])

  useEffect(() => {
    if (activeTab === 'timeline') {
      loadTimeline()
    }
  }, [timelineDays])

  const loadAllData = async (): Promise<void> => {
    setIsLoading(true)
    try {
      const [statsData, heatmapData, topicsData, timelineData] = await Promise.all([
        api.getVisualizationStats(),
        api.getActivityHeatmap(90),
        api.getTopicDistribution(),
        api.getTimeline(30, 'day')
      ])
      setStats(statsData)
      setHeatmap(heatmapData)
      setTopics(topicsData)
      setTimeline(timelineData)
    } catch (error) {
      console.error('Failed to load visualization data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadTimeline = async (): Promise<void> => {
    try {
      const data = await api.getTimeline(timelineDays, 'day')
      setTimeline(data)
    } catch (error) {
      console.error('Failed to load timeline:', error)
    }
  }

  return (
    <div className="h-full flex flex-col p-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t('insights.title')}</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {t('insights.subtitle')}
          </p>
        </div>
        <button
          onClick={loadAllData}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-muted/60 hover:bg-muted transition-all duration-200 disabled:opacity-50 shadow-warm-sm"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>{t('common.refresh')}</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border/50 pb-3">
        <TabButton
          active={activeTab === 'overview'}
          onClick={() => setActiveTab('overview')}
          icon={<Activity className="w-4 h-4" />}
          label={t('insights.overview')}
        />
        <TabButton
          active={activeTab === 'timeline'}
          onClick={() => setActiveTab('timeline')}
          icon={<Clock className="w-4 h-4" />}
          label={t('insights.timeline')}
        />
        <TabButton
          active={activeTab === 'heatmap'}
          onClick={() => setActiveTab('heatmap')}
          icon={<Calendar className="w-4 h-4" />}
          label={t('insights.activity')}
        />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'overview' && (
          <OverviewTab stats={stats} heatmap={heatmap} topics={topics} isLoading={isLoading} />
        )}
        {activeTab === 'timeline' && (
          <TimelineTab
            timeline={timeline}
            days={timelineDays}
            setDays={setTimelineDays}
            isLoading={isLoading}
          />
        )}
        {activeTab === 'heatmap' && <HeatmapTab heatmap={heatmap} isLoading={isLoading} />}
      </div>
    </div>
  )
}

function TabButton({
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
      className={`flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all duration-200 ${
        active
          ? 'bg-primary text-primary-foreground shadow-warm-sm'
          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
      }`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
  )
}

// Donut Chart Component
function DonutChart({
  data,
  size = 200,
  strokeWidth = 32
}: {
  data: Record<string, number>
  size?: number
  strokeWidth?: number
}): JSX.Element {
  const { language } = useLanguage()
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null)

  const total = useMemo(() => {
    return Object.values(data).reduce((sum, count) => sum + count, 0)
  }, [data])

  const segments = useMemo(() => {
    if (total === 0) return []

    const radius = (size - strokeWidth) / 2
    const circumference = 2 * Math.PI * radius
    let currentAngle = -90 // Start from top

    return CATEGORY_ORDER.map((category) => {
      const count = data[category] || 0
      const percentage = count / total
      const angle = percentage * 360
      const startAngle = currentAngle
      currentAngle += angle

      // Calculate arc path
      const startRad = (startAngle * Math.PI) / 180
      const endRad = ((startAngle + angle) * Math.PI) / 180
      const largeArc = angle > 180 ? 1 : 0

      const x1 = size / 2 + radius * Math.cos(startRad)
      const y1 = size / 2 + radius * Math.sin(startRad)
      const x2 = size / 2 + radius * Math.cos(endRad)
      const y2 = size / 2 + radius * Math.sin(endRad)

      return {
        category,
        count,
        percentage,
        color: CATEGORY_CONFIG[category].color,
        path: percentage > 0
          ? `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`
          : ''
      }
    }).filter(s => s.percentage > 0)
  }, [data, total, size, strokeWidth])

  if (total === 0) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={(size - strokeWidth) / 2}
            fill="none"
            stroke="var(--muted)"
            strokeWidth={strokeWidth}
          />
        </svg>
        <p className="text-sm text-muted-foreground mt-2">
          {language === 'zh' ? '暂无数据' : 'No data'}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={(size - strokeWidth) / 2}
            fill="none"
            stroke="var(--muted)"
            strokeWidth={strokeWidth}
            opacity={0.3}
          />
          {/* Segments */}
          {segments.map((segment, i) => (
            <path
              key={segment.category}
              d={segment.path}
              fill="none"
              stroke={segment.color}
              strokeWidth={hoveredCategory === segment.category ? strokeWidth + 4 : strokeWidth}
              strokeLinecap="round"
              className="transition-all duration-200 cursor-pointer"
              style={{
                filter: hoveredCategory === segment.category ? 'brightness(1.1)' : 'none'
              }}
              onMouseEnter={() => setHoveredCategory(segment.category)}
              onMouseLeave={() => setHoveredCategory(null)}
            />
          ))}
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {hoveredCategory ? (
            <>
              <span className="text-2xl font-bold">{data[hoveredCategory] || 0}</span>
              <span className="text-xs text-muted-foreground">
                {language === 'zh'
                  ? CATEGORY_CONFIG[hoveredCategory].labelZh
                  : CATEGORY_CONFIG[hoveredCategory].labelEn}
              </span>
            </>
          ) : (
            <>
              <span className="text-2xl font-bold">{total}</span>
              <span className="text-xs text-muted-foreground">
                {language === 'zh' ? '总记忆' : 'Total'}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// Category Legend Component
function CategoryLegend({
  data
}: {
  data: Record<string, number>
}): JSX.Element {
  const { language } = useLanguage()
  const total = Object.values(data).reduce((sum, count) => sum + count, 0)

  return (
    <div className="grid grid-cols-2 gap-2">
      {CATEGORY_ORDER.map((category) => {
        const config = CATEGORY_CONFIG[category]
        const count = data[category] || 0
        const percentage = total > 0 ? Math.round((count / total) * 100) : 0

        return (
          <div
            key={category}
            className="flex items-center gap-2 p-2 rounded-lg hover:bg-muted/40 transition-colors"
          >
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: config.color }}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium truncate">
                  {language === 'zh' ? config.labelZh : config.labelEn}
                </span>
                <span className="text-xs text-muted-foreground ml-1">
                  {count}
                </span>
              </div>
              <div className="h-1.5 bg-muted/50 rounded-full mt-1 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${percentage}%`,
                    backgroundColor: config.color
                  }}
                />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function OverviewTab({
  stats,
  heatmap,
  topics,
  isLoading
}: {
  stats: VisualizationStats | null
  heatmap: HeatmapData | null
  topics: TopicData | null
  isLoading: boolean
}): JSX.Element {
  const { t, language } = useLanguage()

  // Get category data from topics or stats
  const categoryData = useMemo(() => {
    // First try category_distribution, then type_distribution (both should have 8 categories)
    if (topics?.category_distribution) {
      return topics.category_distribution
    }
    if (topics?.type_distribution) {
      // Check if it has the 8 life categories
      const dist = topics.type_distribution
      const hasCategories = CATEGORY_ORDER.some(cat => cat in dist)
      if (hasCategories) {
        return dist
      }
    }
    if ((stats?.semantic as any)?.categories) {
      return (stats.semantic as any).categories
    }
    // Fallback empty data
    return CATEGORY_ORDER.reduce((acc, cat) => ({ ...acc, [cat]: 0 }), {})
  }, [topics, stats])

  if (isLoading && !stats) {
    return <LoadingState />
  }

  return (
    <div className="space-y-6">
      {/* Top Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Calendar className="w-5 h-5 text-purple-500" />}
          title={t('insights.episodicMemories')}
          value={stats?.episodic.total ?? 0}
          subtext={`+${stats?.episodic.this_week ?? 0} ${t('insights.thisWeek')}`}
          bgColor="bg-purple-50 dark:bg-purple-900/20"
        />
        <StatCard
          icon={<Brain className="w-5 h-5 text-blue-500" />}
          title={t('insights.semanticMemories')}
          value={stats?.semantic.total ?? 0}
          subtext={`+${stats?.semantic.this_week ?? 0} ${t('insights.thisWeek')}`}
          bgColor="bg-blue-50 dark:bg-blue-900/20"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-green-500" />}
          title={t('insights.activeDays')}
          value={heatmap?.stats.active_days ?? 0}
          subtext={`${t('insights.avg')} ${heatmap?.stats.average_daily ?? 0} ${t('insights.memoriesPerDay')}`}
          bgColor="bg-green-50 dark:bg-green-900/20"
        />
        <StatCard
          icon={<Activity className="w-5 h-5 text-orange-500" />}
          title={t('insights.confidence')}
          value={`${Math.round((stats?.semantic.avg_confidence ?? 0) * 100)}%`}
          subtext={t('insights.avgMemoryConfidence')}
          bgColor="bg-orange-50 dark:bg-orange-900/20"
        />
      </div>

      {/* Category Distribution - Main Feature */}
      <div className="p-6 rounded-xl glass-card">
        <h3 className="text-lg font-semibold mb-4">
          {language === 'zh' ? '人生领域分布' : 'Life Categories Distribution'}
        </h3>
        <div className="flex flex-col lg:flex-row items-center gap-8">
          <DonutChart data={categoryData} size={220} strokeWidth={28} />
          <div className="flex-1 w-full">
            <CategoryLegend data={categoryData} />
          </div>
        </div>
      </div>

      {/* Mini Heatmap */}
      {heatmap && (
        <div className="p-5 rounded-lg glass-card">
          <h3 className="text-sm font-medium mb-3">{t('insights.activityLast90Days')}</h3>
          <MiniHeatmap data={heatmap.heatmap.slice(-63)} />
        </div>
      )}

      {/* Top Keywords */}
      {topics && topics.top_keywords.length > 0 && (
        <div className="p-5 rounded-lg glass-card">
          <h3 className="text-sm font-medium mb-3">{t('insights.topKeywords')}</h3>
          <div className="flex flex-wrap gap-2">
            {topics.top_keywords.slice(0, 15).map((kw, i) => (
              <span
                key={i}
                className="px-3 py-1.5 rounded-full text-sm bg-muted/60 hover:bg-muted transition-colors"
                style={{ opacity: 0.5 + (0.5 * (15 - i)) / 15 }}
              >
                {kw.word}
                <span className="ml-1 text-xs text-muted-foreground">({kw.count})</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TimelineTab({
  timeline,
  days,
  setDays,
  isLoading
}: {
  timeline: TimelineData | null
  days: number
  setDays: (d: number) => void
  isLoading: boolean
}): JSX.Element {
  const { t } = useLanguage()
  const [expandedDays, setExpandedDays] = useState<Set<string>>(new Set())
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null)

  const toggleDay = (date: string) => {
    setExpandedDays((prev) => {
      const next = new Set(prev)
      if (next.has(date)) {
        next.delete(date)
      } else {
        next.add(date)
      }
      return next
    })
  }

  if (isLoading && !timeline) {
    return <LoadingState />
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted-foreground">{t('insights.showLast')}</span>
        {[7, 14, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-full text-sm transition-all duration-200 ${
              days === d
                ? 'bg-primary text-primary-foreground shadow-warm-sm'
                : 'bg-muted/60 text-muted-foreground hover:bg-muted'
            }`}
          >
            {d} {t('insights.days')}
          </button>
        ))}
      </div>

      {/* Timeline */}
      {timeline?.timeline.length === 0 ? (
        <EmptyState
          icon={<Clock className="w-12 h-12" />}
          title={t('insights.noTimelineData')}
          description={t('insights.noTimelineDesc')}
        />
      ) : (
        <div className="space-y-2">
          {timeline?.timeline.map(({ date, events }) => (
            <TimelineDay
              key={date}
              date={date}
              events={events}
              expanded={expandedDays.has(date)}
              onToggle={() => toggleDay(date)}
              onEventClick={setSelectedEvent}
            />
          ))}
        </div>
      )}

      {/* Event detail modal */}
      {selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </div>
  )
}

function TimelineDay({
  date,
  events,
  expanded,
  onToggle,
  onEventClick
}: {
  date: string
  events: TimelineEvent[]
  expanded: boolean
  onToggle: () => void
  onEventClick: (event: TimelineEvent) => void
}): JSX.Element {
  const { t, language } = useLanguage()

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr)
    return d.toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className="rounded-lg glass-card overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-muted/40 transition-all duration-200"
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          )}
          <span className="font-medium">{formatDate(date)}</span>
          <span className="text-sm text-muted-foreground px-2 py-0.5 bg-muted/50 rounded-full">
            {events.length} {t('insights.events')}
          </span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-2">
          {events.map((event) => (
            <div
              key={event.id}
              className="pl-7 py-3 border-l-2 border-primary/30 ml-2 cursor-pointer hover:bg-muted/30 rounded-r-lg transition-colors"
              onClick={() => onEventClick(event)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0 pr-2">
                  <p className="font-medium text-sm">{event.title}</p>
                  <p className="text-sm text-muted-foreground line-clamp-2 mt-1">{event.content}</p>
                </div>
                <span className="text-xs text-muted-foreground whitespace-nowrap bg-muted/50 px-2 py-1 rounded">
                  {new Date(event.start_time).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
              </div>
              {event.screenshot_count > 0 && (
                <span className="inline-block mt-2 text-xs px-2 py-0.5 rounded bg-primary/10 text-primary">
                  {event.screenshot_count} {t('nav.screenshots').toLowerCase()}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Event detail modal
function EventDetailModal({
  event,
  onClose
}: {
  event: TimelineEvent
  onClose: () => void
}): JSX.Element {
  const { t, language } = useLanguage()

  const formatDateTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-card/95 backdrop-blur-md rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto shadow-warm-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <h2 className="text-xl font-bold break-words pr-4">{event.title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-muted/60 transition-all duration-200 flex-shrink-0"
          >
            <ChevronRight className="w-5 h-5 rotate-45" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Time range */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="w-4 h-4" />
            <span>{formatDateTime(event.start_time)}</span>
            {event.end_time !== event.start_time && (
              <>
                <span>-</span>
                <span>{formatDateTime(event.end_time)}</span>
              </>
            )}
          </div>

          {/* Content */}
          <div className="p-4 bg-muted/30 rounded-lg">
            <p className="text-sm whitespace-pre-wrap">{event.content}</p>
          </div>

          {/* URLs */}
          {event.urls && event.urls.length > 0 && (
            <div>
              <h3 className="text-sm font-medium mb-2">{t('insights.relatedUrls')}</h3>
              <div className="space-y-1">
                {event.urls.map((url, i) => (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-sm text-primary hover:underline truncate"
                  >
                    {url}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Screenshot count */}
          {event.screenshot_count > 0 && (
            <div className="text-sm text-muted-foreground">
              {event.screenshot_count} {t('insights.screenshotsAssociated')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function HeatmapTab({
  heatmap,
  isLoading
}: {
  heatmap: HeatmapData | null
  isLoading: boolean
}): JSX.Element {
  const { t } = useLanguage()

  if (isLoading && !heatmap) {
    return <LoadingState />
  }

  if (!heatmap) {
    return (
      <EmptyState
        icon={<Calendar className="w-12 h-12" />}
        title={t('insights.noActivityData')}
        description={t('insights.noActivityDesc')}
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-lg glass-card">
          <p className="text-sm text-muted-foreground">{t('insights.totalMemories')}</p>
          <p className="text-2xl font-bold">{heatmap.stats.total_memories}</p>
        </div>
        <div className="p-4 rounded-lg glass-card">
          <p className="text-sm text-muted-foreground">{t('insights.activeDays')}</p>
          <p className="text-2xl font-bold">{heatmap.stats.active_days}</p>
        </div>
        <div className="p-4 rounded-lg glass-card">
          <p className="text-sm text-muted-foreground">{t('insights.maxDaily')}</p>
          <p className="text-2xl font-bold">{heatmap.stats.max_daily}</p>
        </div>
        <div className="p-4 rounded-lg glass-card">
          <p className="text-sm text-muted-foreground">{t('insights.dailyAverage')}</p>
          <p className="text-2xl font-bold">{heatmap.stats.average_daily}</p>
        </div>
      </div>

      {/* Full Heatmap */}
      <div className="p-5 rounded-lg glass-card">
        <h3 className="text-sm font-medium mb-4">{t('insights.activityHeatmap')}</h3>
        <FullHeatmap data={heatmap.heatmap} maxCount={heatmap.stats.max_daily} />
      </div>
    </div>
  )
}

function MiniHeatmap({ data }: { data: HeatmapData['heatmap'] }): JSX.Element {
  const maxCount = Math.max(...data.map((d) => d.count), 1)

  // Group by week
  const weeks: HeatmapData['heatmap'][] = []
  let currentWeek: HeatmapData['heatmap'] = []

  data.forEach((day, i) => {
    currentWeek.push(day)
    if (day.weekday === 6 || i === data.length - 1) {
      weeks.push(currentWeek)
      currentWeek = []
    }
  })

  // GitHub-style color scale: empty days are light gray, active days are green
  const getColor = (count: number) => {
    if (count === 0) return 'rgba(128, 128, 128, 0.1)' // Light gray for empty days
    const intensity = 0.3 + (count / maxCount) * 0.7
    return `rgba(45, 90, 69, ${intensity})`
  }

  return (
    <div className="flex gap-1 overflow-x-auto pb-2">
      {weeks.map((week, wi) => (
        <div key={wi} className="flex flex-col gap-1">
          {week.map((day, di) => (
            <div
              key={di}
              className="w-3 h-3 rounded-sm transition-colors border border-border/20"
              style={{ backgroundColor: getColor(day.count) }}
              title={`${day.date}: ${day.count} memories`}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

function FullHeatmap({
  data,
  maxCount
}: {
  data: HeatmapData['heatmap']
  maxCount: number
}): JSX.Element {
  const { t, language } = useLanguage()

  // Group by week
  const weeks: HeatmapData['heatmap'][] = []
  let currentWeek: HeatmapData['heatmap'] = []

  // Pad the beginning if first day is not Sunday
  if (data.length > 0 && data[0].weekday > 0) {
    for (let i = 0; i < data[0].weekday; i++) {
      currentWeek.push({ date: '', count: -1, weekday: i })
    }
  }

  data.forEach((day, i) => {
    currentWeek.push(day)
    if (day.weekday === 6 || i === data.length - 1) {
      // Pad the end
      while (currentWeek.length < 7) {
        currentWeek.push({ date: '', count: -1, weekday: currentWeek.length })
      }
      weeks.push(currentWeek)
      currentWeek = []
    }
  })

  const dayLabels = language === 'zh'
    ? ['日', '一', '二', '三', '四', '五', '六']
    : ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  // Get month labels
  const monthLabels = useMemo(() => {
    const labels: { week: number; month: string }[] = []
    let lastMonth = ''

    weeks.forEach((week, wi) => {
      const firstDay = week.find((d) => d.date)
      if (firstDay?.date) {
        const month = new Date(firstDay.date).toLocaleDateString('en-US', { month: 'short' })
        if (month !== lastMonth) {
          labels.push({ week: wi, month })
          lastMonth = month
        }
      }
    })

    return labels
  }, [weeks])

  // GitHub-style color scale
  const getColor = (count: number) => {
    if (count === -1) return 'transparent' // Padding cells
    if (count === 0) return 'rgba(128, 128, 128, 0.1)' // Light gray for empty days
    const intensity = 0.3 + (count / Math.max(maxCount, 1)) * 0.7
    return `rgba(45, 90, 69, ${intensity})`
  }

  return (
    <div className="overflow-x-auto">
      {/* Month labels */}
      <div className="flex mb-1 ml-8">
        {monthLabels.map(({ week, month }, i) => (
          <span
            key={i}
            className="text-xs text-muted-foreground"
            style={{ marginLeft: `${week * 16 - (i > 0 ? monthLabels[i - 1].week * 16 : 0)}px` }}
          >
            {month}
          </span>
        ))}
      </div>

      <div className="flex">
        {/* Day labels */}
        <div className="flex flex-col gap-1 pr-2">
          {dayLabels.map((day, i) => (
            <span key={i} className="text-xs text-muted-foreground h-4 leading-4">
              {i % 2 === 1 ? day : ''}
            </span>
          ))}
        </div>

        {/* Heatmap grid */}
        <div className="flex gap-1">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-1">
              {week.map((day, di) => (
                <div
                  key={di}
                  className={`w-4 h-4 rounded-sm transition-colors ${day.count === -1 ? '' : 'border border-border/20'}`}
                  style={{ backgroundColor: getColor(day.count) }}
                  title={day.date ? `${day.date}: ${day.count} memories` : ''}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 mt-4 text-xs text-muted-foreground">
        <span>{t('insights.less')}</span>
        {[0, 0.3, 0.5, 0.7, 1].map((level, i) => (
          <div
            key={i}
            className="w-4 h-4 rounded-sm border border-border/20"
            style={{
              backgroundColor:
                level === 0 ? 'rgba(128, 128, 128, 0.1)' : `rgba(45, 90, 69, ${0.3 + level * 0.7})`
            }}
          />
        ))}
        <span>{t('insights.more')}</span>
      </div>
    </div>
  )
}

function StatCard({
  icon,
  title,
  value,
  subtext,
  bgColor
}: {
  icon: React.ReactNode
  title: string
  value: number | string
  subtext: string
  bgColor: string
}): JSX.Element {
  return (
    <div className={`p-4 rounded-xl ${bgColor} transition-all duration-200 hover:shadow-warm-sm`}>
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground mt-1">{subtext}</p>
    </div>
  )
}

function LoadingState(): JSX.Element {
  return (
    <div className="flex items-center justify-center py-16">
      <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
    </div>
  )
}

function EmptyState({
  icon,
  title,
  description
}: {
  icon: React.ReactNode
  title: string
  description: string
}): JSX.Element {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <div className="opacity-50 mb-4">{icon}</div>
      <h3 className="text-lg font-medium mb-1">{title}</h3>
      <p className="text-sm">{description}</p>
    </div>
  )
}
