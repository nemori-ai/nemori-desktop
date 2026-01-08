import { useState, useEffect } from 'react'
import {
  Search, Brain, Calendar, RefreshCw, X, Clock, Link, Image,
  Briefcase, DollarSign, HeartPulse, Home, Users, GraduationCap, Gamepad2, Sparkles
} from 'lucide-react'
import { api, EpisodicMemory, SemanticMemory, Memory, SemanticCategory } from '../services/api'

type TabType = 'episodic' | 'semantic' | 'search'

// 8 life categories configuration
const CATEGORY_CONFIG: Record<SemanticCategory, { label: string; icon: React.ReactNode; color: string }> = {
  career: { label: '事业/工作', icon: <Briefcase className="w-4 h-4" />, color: 'bg-blue-100 text-blue-600' },
  finance: { label: '财务/金钱', icon: <DollarSign className="w-4 h-4" />, color: 'bg-green-100 text-green-600' },
  health: { label: '健康/身体', icon: <HeartPulse className="w-4 h-4" />, color: 'bg-red-100 text-red-600' },
  family: { label: '家庭/亲密关系', icon: <Home className="w-4 h-4" />, color: 'bg-pink-100 text-pink-600' },
  social: { label: '社交/朋友', icon: <Users className="w-4 h-4" />, color: 'bg-orange-100 text-orange-600' },
  growth: { label: '学习/成长', icon: <GraduationCap className="w-4 h-4" />, color: 'bg-purple-100 text-purple-600' },
  leisure: { label: '娱乐/休闲', icon: <Gamepad2 className="w-4 h-4" />, color: 'bg-yellow-100 text-yellow-600' },
  spirit: { label: '心灵/精神', icon: <Sparkles className="w-4 h-4" />, color: 'bg-indigo-100 text-indigo-600' }
}

export default function MemoriesPage(): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabType>('episodic')
  const [episodicMemories, setEpisodicMemories] = useState<EpisodicMemory[]>([])
  const [semanticMemories, setSemanticMemories] = useState<SemanticMemory[]>([])
  const [searchResults, setSearchResults] = useState<Memory[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [semanticFilter, setSemanticFilter] = useState<'all' | SemanticCategory>('all')
  const [selectedMemory, setSelectedMemory] = useState<EpisodicMemory | null>(null)

  useEffect(() => {
    loadMemories()
  }, [])

  const loadMemories = async (): Promise<void> => {
    setIsLoading(true)
    try {
      const [episodic, semantic] = await Promise.all([
        api.getEpisodicMemories(100),
        api.getSemanticMemories(undefined, 100)
      ])
      setEpisodicMemories(episodic.memories)
      setSemanticMemories(semantic.memories)
    } catch (error) {
      console.error('Failed to load memories:', error)
    } finally {
      setIsLoading(false)
    }
  }


  const handleSearch = async (): Promise<void> => {
    if (!searchQuery.trim()) return

    setIsLoading(true)
    setActiveTab('search')
    try {
      const { results } = await api.searchMemories(searchQuery, 20)
      setSearchResults(results)
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const formatDate = (timestamp: number): string => {
    return new Date(timestamp).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const filteredSemanticMemories =
    semanticFilter === 'all'
      ? semanticMemories
      : semanticMemories.filter((m) => m.type === semanticFilter)

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Memories</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Browse and search your personal knowledge base
          </p>
        </div>
        <button
          onClick={loadMemories}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-muted/60 hover:bg-muted transition-all duration-200 disabled:opacity-50 shadow-warm-sm"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Search bar */}
      <div className="relative mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search your memories..."
          className="w-full pl-11 pr-4 py-3 rounded-lg border border-input/50 bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 shadow-warm-sm transition-all duration-200"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border/50 pb-3">
        <TabButton
          active={activeTab === 'episodic'}
          onClick={() => setActiveTab('episodic')}
          icon={<Calendar className="w-4 h-4" />}
          label={`Episodic (${episodicMemories.length})`}
        />
        <TabButton
          active={activeTab === 'semantic'}
          onClick={() => setActiveTab('semantic')}
          icon={<Brain className="w-4 h-4" />}
          label={`Semantic (${semanticMemories.length})`}
        />
        {searchResults.length > 0 && (
          <TabButton
            active={activeTab === 'search'}
            onClick={() => setActiveTab('search')}
            icon={<Search className="w-4 h-4" />}
            label={`Search (${searchResults.length})`}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'episodic' && (
          <div className="grid gap-4">
            {episodicMemories.length === 0 ? (
              <EmptyState
                icon={<Calendar className="w-12 h-12" />}
                title="No episodic memories yet"
                description="Your memories from conversations and activities will appear here."
              />
            ) : (
              episodicMemories.map((memory) => (
                <EpisodicMemoryCard
                  key={memory.id}
                  memory={memory}
                  formatDate={formatDate}
                  onClick={() => setSelectedMemory(memory)}
                />
              ))
            )}
          </div>
        )}

        {activeTab === 'semantic' && (
          <>
            {/* Semantic filter - 8 life categories */}
            <div className="flex flex-wrap gap-2 mb-4">
              <FilterButton
                active={semanticFilter === 'all'}
                onClick={() => setSemanticFilter('all')}
                label="全部"
              />
              {(Object.keys(CATEGORY_CONFIG) as SemanticCategory[]).map((cat) => (
                <FilterButton
                  key={cat}
                  active={semanticFilter === cat}
                  onClick={() => setSemanticFilter(cat)}
                  label={CATEGORY_CONFIG[cat].label}
                  icon={CATEGORY_CONFIG[cat].icon}
                />
              ))}
            </div>

            <div className="grid gap-3">
              {filteredSemanticMemories.length === 0 ? (
                <EmptyState
                  icon={<Brain className="w-12 h-12" />}
                  title="No semantic memories yet"
                  description="Facts and preferences extracted from your conversations will appear here."
                />
              ) : (
                filteredSemanticMemories.map((memory) => (
                  <SemanticMemoryCard key={memory.id} memory={memory} formatDate={formatDate} />
                ))
              )}
            </div>
          </>
        )}

        {activeTab === 'search' && (
          <div className="grid gap-3">
            {searchResults.length === 0 ? (
              <EmptyState
                icon={<Search className="w-12 h-12" />}
                title="No results found"
                description="Try searching with different keywords."
              />
            ) : (
              searchResults.map((memory) => (
                <SearchResultCard key={memory.id} memory={memory} />
              ))
            )}
          </div>
        )}
      </div>

      {/* Memory detail modal */}
      {selectedMemory && (
        <EpisodicMemoryModal
          memory={selectedMemory}
          onClose={() => setSelectedMemory(null)}
          formatDate={formatDate}
        />
      )}
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

function FilterButton({
  active,
  onClick,
  label,
  icon
}: {
  active: boolean
  onClick: () => void
  label: string
  icon?: React.ReactNode
}): JSX.Element {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
        active
          ? 'bg-primary/12 text-primary border border-primary/20 shadow-warm-sm'
          : 'bg-muted/60 text-muted-foreground hover:bg-muted'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

function EpisodicMemoryCard({
  memory,
  formatDate,
  onClick
}: {
  memory: EpisodicMemory
  formatDate: (t: number) => string
  onClick: () => void
}): JSX.Element {
  return (
    <div
      onClick={onClick}
      className="p-5 rounded-lg glass-card hover:shadow-warm transition-all duration-200 cursor-pointer"
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-semibold text-foreground">{memory.title}</h3>
        <span className="text-xs text-muted-foreground">{formatDate(memory.start_time)}</span>
      </div>
      <p className="text-sm text-muted-foreground line-clamp-3">{memory.content}</p>
      <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
        {memory.screenshot_ids && memory.screenshot_ids.length > 0 && (
          <span className="flex items-center gap-1">
            <Image className="w-3 h-3" />
            {Array.isArray(memory.screenshot_ids) ? memory.screenshot_ids.length : 0} screenshots
          </span>
        )}
        {memory.urls && (
          <span className="flex items-center gap-1">
            <Link className="w-3 h-3" />
            {(() => {
              try {
                const urls = typeof memory.urls === 'string' ? JSON.parse(memory.urls) : memory.urls
                return Array.isArray(urls) ? urls.length : 0
              } catch {
                return 0
              }
            })()} URLs
          </span>
        )}
      </div>
    </div>
  )
}

function SemanticMemoryCard({
  memory,
  formatDate
}: {
  memory: SemanticMemory
  formatDate: (t: number) => string
}): JSX.Element {
  const config = CATEGORY_CONFIG[memory.type] || {
    label: memory.type,
    icon: <Brain className="w-4 h-4" />,
    color: 'bg-muted text-muted-foreground'
  }

  return (
    <div className="flex items-start gap-3 p-4 rounded-lg glass-card hover:shadow-warm-sm transition-all duration-200">
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${config.color}`}
      >
        {config.icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-muted-foreground">{config.label}</span>
        </div>
        <p className="text-sm text-foreground">{memory.content}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-muted-foreground">{formatDate(memory.created_at)}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {Math.round(memory.confidence * 100)}%
          </span>
        </div>
      </div>
    </div>
  )
}

function SearchResultCard({ memory }: { memory: Memory }): JSX.Element {
  const type = memory.metadata?.type || 'unknown'
  const distance = memory.distance ? (1 - memory.distance).toFixed(2) : null

  return (
    <div className="p-4 rounded-lg glass-card hover:shadow-warm-sm transition-all duration-200">
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            type === 'episodic'
              ? 'bg-primary/10 text-primary'
              : type === 'semantic'
                ? 'bg-accent/20 text-accent-foreground'
                : 'bg-muted text-muted-foreground'
          }`}
        >
          {type}
        </span>
        {distance && (
          <span className="text-xs text-muted-foreground">
            {Math.round(parseFloat(distance) * 100)}% match
          </span>
        )}
      </div>
      <p className="text-sm text-foreground">{memory.content}</p>
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

function EpisodicMemoryModal({
  memory,
  onClose,
  formatDate
}: {
  memory: EpisodicMemory
  onClose: () => void
  formatDate: (t: number) => string
}): JSX.Element {
  const parseUrls = (urls: string[] | string | undefined): string[] => {
    if (!urls) return []
    try {
      if (typeof urls === 'string') return JSON.parse(urls)
      return urls
    } catch {
      return []
    }
  }

  const urls = parseUrls(memory.urls)
  const duration = memory.end_time - memory.start_time
  const durationMinutes = Math.round(duration / 60000)

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-card/95 backdrop-blur-md rounded-xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-warm-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-border/50">
          <div className="flex-1 pr-4">
            <h2 className="text-xl font-bold mb-2">{memory.title}</h2>
            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                {formatDate(memory.start_time)}
              </span>
              {durationMinutes > 0 && (
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />
                  {durationMinutes} min
                </span>
              )}
              {memory.screenshot_ids && memory.screenshot_ids.length > 0 && (
                <span className="flex items-center gap-1">
                  <Image className="w-4 h-4" />
                  {Array.isArray(memory.screenshot_ids) ? memory.screenshot_ids.length : 0} screenshots
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted/60 transition-all duration-200 flex-shrink-0"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <p className="whitespace-pre-wrap text-foreground leading-relaxed">
              {memory.content}
            </p>
          </div>

          {/* URLs */}
          {urls.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                <Link className="w-4 h-4" />
                Related URLs ({urls.length})
              </h3>
              <div className="space-y-2">
                {urls.map((url, i) => (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-sm text-primary hover:underline truncate transition-colors"
                  >
                    {url}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Participants */}
          {memory.participants && memory.participants.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold mb-3">Participants</h3>
              <div className="flex flex-wrap gap-2">
                {(Array.isArray(memory.participants) ? memory.participants : []).map((p, i) => (
                  <span
                    key={i}
                    className="px-3 py-1.5 rounded-full text-sm bg-muted/60"
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border/50 bg-muted/30">
          <p className="text-xs text-muted-foreground">
            Memory ID: {memory.id}
          </p>
        </div>
      </div>
    </div>
  )
}
