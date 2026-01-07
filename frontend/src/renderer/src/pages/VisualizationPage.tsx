import { useState, useEffect, useMemo } from 'react'
import {
  Calendar,
  Brain,
  Lightbulb,
  Heart,
  TrendingUp,
  Activity,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronRight
} from 'lucide-react'
import {
  api,
  TimelineData,
  HeatmapData,
  TopicData,
  VisualizationStats,
  TimelineEvent
} from '../services/api'

type TabType = 'overview' | 'timeline' | 'heatmap'

export default function VisualizationPage(): JSX.Element {
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
          <h1 className="text-2xl font-bold">Insights</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Visualize your memory patterns and knowledge
          </p>
        </div>
        <button
          onClick={loadAllData}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-muted hover:bg-muted/80 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border pb-2">
        <TabButton
          active={activeTab === 'overview'}
          onClick={() => setActiveTab('overview')}
          icon={<Activity className="w-4 h-4" />}
          label="Overview"
        />
        <TabButton
          active={activeTab === 'timeline'}
          onClick={() => setActiveTab('timeline')}
          icon={<Clock className="w-4 h-4" />}
          label="Timeline"
        />
        <TabButton
          active={activeTab === 'heatmap'}
          onClick={() => setActiveTab('heatmap')}
          icon={<Calendar className="w-4 h-4" />}
          label="Activity"
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
      className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      }`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </button>
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
  if (isLoading && !stats) {
    return <LoadingState />
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Calendar className="w-5 h-5 text-purple-500" />}
          title="Episodic Memories"
          value={stats?.episodic.total ?? 0}
          subtext={`+${stats?.episodic.this_week ?? 0} this week`}
          bgColor="bg-purple-50 dark:bg-purple-900/20"
        />
        <StatCard
          icon={<Brain className="w-5 h-5 text-blue-500" />}
          title="Semantic Memories"
          value={stats?.semantic.total ?? 0}
          subtext={`${stats?.semantic.knowledge ?? 0} knowledge, ${stats?.semantic.preference ?? 0} preferences`}
          bgColor="bg-blue-50 dark:bg-blue-900/20"
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-green-500" />}
          title="Active Days"
          value={heatmap?.stats.active_days ?? 0}
          subtext={`Avg ${heatmap?.stats.average_daily ?? 0} memories/day`}
          bgColor="bg-green-50 dark:bg-green-900/20"
        />
        <StatCard
          icon={<Activity className="w-5 h-5 text-orange-500" />}
          title="Confidence"
          value={`${Math.round((stats?.semantic.avg_confidence ?? 0) * 100)}%`}
          subtext="Average memory confidence"
          bgColor="bg-orange-50 dark:bg-orange-900/20"
        />
      </div>

      {/* Mini Heatmap */}
      {heatmap && (
        <div className="p-4 rounded-lg border border-border bg-card">
          <h3 className="text-sm font-medium mb-3">Activity (Last 90 Days)</h3>
          <MiniHeatmap data={heatmap.heatmap.slice(-63)} />
        </div>
      )}

      {/* Topics & Keywords */}
      {topics && topics.top_keywords.length > 0 && (
        <div className="p-4 rounded-lg border border-border bg-card">
          <h3 className="text-sm font-medium mb-3">Top Keywords</h3>
          <div className="flex flex-wrap gap-2">
            {topics.top_keywords.slice(0, 15).map((kw, i) => (
              <span
                key={i}
                className="px-3 py-1 rounded-full text-sm bg-muted"
                style={{ opacity: 0.5 + (0.5 * (15 - i)) / 15 }}
              >
                {kw.word}
                <span className="ml-1 text-xs text-muted-foreground">({kw.count})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Type Distribution */}
      {topics && (
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-2">
              <Lightbulb className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-medium">Knowledge</span>
            </div>
            <p className="text-3xl font-bold">{topics.type_distribution.knowledge ?? 0}</p>
            <p className="text-xs text-muted-foreground mt-1">Facts and information</p>
          </div>
          <div className="p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-2">
              <Heart className="w-4 h-4 text-pink-500" />
              <span className="text-sm font-medium">Preferences</span>
            </div>
            <p className="text-3xl font-bold">{topics.type_distribution.preference ?? 0}</p>
            <p className="text-xs text-muted-foreground mt-1">Personal tastes and habits</p>
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
        <span className="text-sm text-muted-foreground">Show last:</span>
        {[7, 14, 30, 90].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-3 py-1 rounded-full text-sm transition-colors ${
              days === d
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            {d} days
          </button>
        ))}
      </div>

      {/* Timeline */}
      {timeline?.timeline.length === 0 ? (
        <EmptyState
          icon={<Clock className="w-12 h-12" />}
          title="No timeline data"
          description="Start capturing screenshots to see your activity timeline"
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
  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          )}
          <span className="font-medium">{formatDate(date)}</span>
          <span className="text-sm text-muted-foreground">({events.length} events)</span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-3 space-y-2">
          {events.map((event) => (
            <div
              key={event.id}
              className="pl-7 py-2 border-l-2 border-primary/20 ml-2 cursor-pointer hover:bg-muted/30 rounded-r transition-colors"
              onClick={() => onEventClick(event)}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-sm">{event.title}</p>
                  <p className="text-sm text-muted-foreground line-clamp-2">{event.content}</p>
                </div>
                <span className="text-xs text-muted-foreground whitespace-nowrap ml-2">
                  {new Date(event.start_time).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
              </div>
              {event.screenshot_count > 0 && (
                <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
                  {event.screenshot_count} screenshots
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
  const formatDateTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div
      className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <h2 className="text-xl font-bold">{event.title}</h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-muted transition-colors"
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
              <h3 className="text-sm font-medium mb-2">Related URLs</h3>
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
              {event.screenshot_count} screenshots associated with this memory
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
  if (isLoading && !heatmap) {
    return <LoadingState />
  }

  if (!heatmap) {
    return (
      <EmptyState
        icon={<Calendar className="w-12 h-12" />}
        title="No activity data"
        description="Start using Nemori to see your activity heatmap"
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-lg border border-border bg-card">
          <p className="text-sm text-muted-foreground">Total Memories</p>
          <p className="text-2xl font-bold">{heatmap.stats.total_memories}</p>
        </div>
        <div className="p-4 rounded-lg border border-border bg-card">
          <p className="text-sm text-muted-foreground">Active Days</p>
          <p className="text-2xl font-bold">{heatmap.stats.active_days}</p>
        </div>
        <div className="p-4 rounded-lg border border-border bg-card">
          <p className="text-sm text-muted-foreground">Max Daily</p>
          <p className="text-2xl font-bold">{heatmap.stats.max_daily}</p>
        </div>
        <div className="p-4 rounded-lg border border-border bg-card">
          <p className="text-sm text-muted-foreground">Daily Average</p>
          <p className="text-2xl font-bold">{heatmap.stats.average_daily}</p>
        </div>
      </div>

      {/* Full Heatmap */}
      <div className="p-4 rounded-lg border border-border bg-card">
        <h3 className="text-sm font-medium mb-4">Activity Heatmap (Last 90 Days)</h3>
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

  return (
    <div className="flex gap-1 overflow-x-auto pb-2">
      {weeks.map((week, wi) => (
        <div key={wi} className="flex flex-col gap-1">
          {week.map((day, di) => (
            <div
              key={di}
              className="w-3 h-3 rounded-sm"
              style={{
                backgroundColor:
                  day.count === 0
                    ? 'var(--muted)'
                    : `rgba(37, 99, 235, ${0.2 + (day.count / maxCount) * 0.8})`
              }}
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

  const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

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
                  className={`w-4 h-4 rounded-sm ${day.count === -1 ? 'opacity-0' : ''}`}
                  style={{
                    backgroundColor:
                      day.count <= 0
                        ? 'var(--muted)'
                        : `rgba(37, 99, 235, ${0.2 + (day.count / Math.max(maxCount, 1)) * 0.8})`
                  }}
                  title={day.date ? `${day.date}: ${day.count} memories` : ''}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 mt-4 text-xs text-muted-foreground">
        <span>Less</span>
        {[0, 0.25, 0.5, 0.75, 1].map((level, i) => (
          <div
            key={i}
            className="w-4 h-4 rounded-sm"
            style={{
              backgroundColor:
                level === 0 ? 'var(--muted)' : `rgba(37, 99, 235, ${0.2 + level * 0.8})`
            }}
          />
        ))}
        <span>More</span>
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
    <div className={`p-4 rounded-lg ${bgColor}`}>
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
