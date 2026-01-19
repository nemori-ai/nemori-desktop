import { useState, useEffect } from 'react'
import {
  Search, Brain, Calendar, RefreshCw, X, Clock, Link, Image, Loader2,
  Briefcase, DollarSign, HeartPulse, Home, Users, GraduationCap, Gamepad2, Sparkles,
  ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight,
  FileText, FolderOpen, Edit3, Eye, Save, ChevronDown, ChevronUp, Code, BookOpen,
  Zap, Library
} from 'lucide-react'
import { NemoriBot } from '../components/NemoriBot'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { api, EpisodicMemory, SemanticMemory, Memory, SemanticCategory, ProfileFileInfo } from '../services/api'
import { useLanguage } from '../contexts/LanguageContext'

type TabType = 'episodic' | 'semantic' | 'profile' | 'search'

// Pagination config
const PAGE_SIZE = 10

// 8 life categories configuration with bilingual labels
const CATEGORY_CONFIG: Record<SemanticCategory, { labelEn: string; labelZh: string; icon: React.ReactNode; color: string }> = {
  career: { labelEn: 'Career', labelZh: '事业/工作', icon: <Briefcase className="w-4 h-4" />, color: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' },
  finance: { labelEn: 'Finance', labelZh: '财务/金钱', icon: <DollarSign className="w-4 h-4" />, color: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400' },
  health: { labelEn: 'Health', labelZh: '健康/身体', icon: <HeartPulse className="w-4 h-4" />, color: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' },
  family: { labelEn: 'Family', labelZh: '家庭/亲密关系', icon: <Home className="w-4 h-4" />, color: 'bg-pink-100 text-pink-600 dark:bg-pink-900/30 dark:text-pink-400' },
  social: { labelEn: 'Social', labelZh: '社交/朋友', icon: <Users className="w-4 h-4" />, color: 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400' },
  growth: { labelEn: 'Growth', labelZh: '学习/成长', icon: <GraduationCap className="w-4 h-4" />, color: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400' },
  leisure: { labelEn: 'Leisure', labelZh: '娱乐/休闲', icon: <Gamepad2 className="w-4 h-4" />, color: 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400' },
  spirit: { labelEn: 'Spirit', labelZh: '心灵/精神', icon: <Sparkles className="w-4 h-4" />, color: 'bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400' }
}

// Profile layer names
const LAYER_NAMES: Record<number, { en: string; zh: string }> = {
  0: { en: 'Basic Info', zh: '基础档案' },
  1: { en: 'Inner Traits', zh: '内在特质' },
  2: { en: 'Skills & Growth', zh: '能力与发展' },
  3: { en: 'Lifestyle', zh: '生活方式' },
  4: { en: 'Social', zh: '社会关系' },
  5: { en: 'Memories & Insights', zh: '记忆与洞察' },
  6: { en: 'Topics', zh: '专题深入' },
}

export default function MemoriesPage(): JSX.Element {
  const { t, language } = useLanguage()
  const [activeTab, setActiveTab] = useState<TabType>('profile')
  const [episodicMemories, setEpisodicMemories] = useState<EpisodicMemory[]>([])
  const [semanticMemories, setSemanticMemories] = useState<SemanticMemory[]>([])
  const [searchResults, setSearchResults] = useState<Memory[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [semanticFilter, setSemanticFilter] = useState<'all' | SemanticCategory>('all')
  const [selectedMemory, setSelectedMemory] = useState<EpisodicMemory | null>(null)
  const [isTriggering, setIsTriggering] = useState(false)

  // Total counts from backend
  const [totalEpisodicCount, setTotalEpisodicCount] = useState(0)
  const [totalSemanticCount, setTotalSemanticCount] = useState(0)

  // Pagination state
  const [episodicPage, setEpisodicPage] = useState(1)
  const [semanticPage, setSemanticPage] = useState(1)

  // Profile files state
  const [profileFiles, setProfileFiles] = useState<ProfileFileInfo[]>([])
  const [profileFilesCount, setProfileFilesCount] = useState(0)
  const [selectedProfileFile, setSelectedProfileFile] = useState<ProfileFileInfo | null>(null)
  const [profileFileContent, setProfileFileContent] = useState<string>('')
  const [isEditingProfile, setIsEditingProfile] = useState(false)
  const [editedContent, setEditedContent] = useState<string>('')
  const [expandedLayers, setExpandedLayers] = useState<Set<number>>(new Set([0, 1, 2]))

  // Initial load - get stats and profile files (since profile is default tab)
  useEffect(() => {
    loadStats()
    loadProfileFiles()
  }, [])

  // Load profile files when tab changes to profile
  useEffect(() => {
    if (activeTab === 'profile' && profileFiles.length === 0) {
      loadProfileFiles()
    }
  }, [activeTab])

  // Load only profile count (for tab display)
  const loadProfileFilesCount = async (): Promise<void> => {
    try {
      const { total_files } = await api.getProfileFiles()
      setProfileFilesCount(total_files)
    } catch (error) {
      console.error('Failed to load profile count:', error)
    }
  }

  // Load memories when page changes
  useEffect(() => {
    loadEpisodicMemories(episodicPage)
  }, [episodicPage])

  useEffect(() => {
    loadSemanticMemories(semanticPage)
  }, [semanticPage])

  const loadStats = async (): Promise<void> => {
    try {
      const stats = await api.getMemoryStats()
      setTotalEpisodicCount(stats.episodic_memories_count)
      setTotalSemanticCount(stats.semantic_memories_count)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  const loadEpisodicMemories = async (page: number): Promise<void> => {
    setIsLoading(true)
    try {
      const offset = (page - 1) * PAGE_SIZE
      const { memories } = await api.getEpisodicMemories(PAGE_SIZE, offset)
      setEpisodicMemories(memories)
    } catch (error) {
      console.error('Failed to load episodic memories:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadSemanticMemories = async (page: number): Promise<void> => {
    setIsLoading(true)
    try {
      // Note: semantic API might need offset support in backend
      const { memories } = await api.getSemanticMemories(
        semanticFilter === 'all' ? undefined : semanticFilter,
        PAGE_SIZE * page // Load up to current page
      )
      // Get only the current page's memories
      const startIdx = (page - 1) * PAGE_SIZE
      setSemanticMemories(memories.slice(startIdx, startIdx + PAGE_SIZE))
    } catch (error) {
      console.error('Failed to load semantic memories:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadProfileFiles = async (): Promise<void> => {
    setIsLoading(true)
    try {
      const { files } = await api.getProfileFiles()
      setProfileFiles(files)
      setProfileFilesCount(files.length)
    } catch (error) {
      console.error('Failed to load profile files:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const loadProfileFileContent = async (filename: string): Promise<void> => {
    try {
      const { content } = await api.getProfileFile(filename)
      setProfileFileContent(content)
      setEditedContent(content)
    } catch (error) {
      console.error('Failed to load profile file content:', error)
    }
  }

  const handleSaveProfileFile = async (): Promise<void> => {
    if (!selectedProfileFile) return
    try {
      await api.updateProfileFile(
        selectedProfileFile.relative_path,
        editedContent,
        'User manual edit'
      )
      setProfileFileContent(editedContent)
      setIsEditingProfile(false)
      await loadProfileFiles() // Refresh list
    } catch (error) {
      console.error('Failed to save profile file:', error)
    }
  }

  const toggleLayer = (layer: number): void => {
    const newExpanded = new Set(expandedLayers)
    if (newExpanded.has(layer)) {
      newExpanded.delete(layer)
    } else {
      newExpanded.add(layer)
    }
    setExpandedLayers(newExpanded)
  }

  const handleRefresh = async (): Promise<void> => {
    await loadStats()
    if (activeTab === 'episodic') {
      setEpisodicPage(1)
      await loadEpisodicMemories(1)
    } else if (activeTab === 'semantic') {
      setSemanticPage(1)
      await loadSemanticMemories(1)
    } else if (activeTab === 'profile') {
      await loadProfileFiles()
    }
  }

  const handleTriggerMaintenance = async (): Promise<void> => {
    if (isTriggering) return
    setIsTriggering(true)
    try {
      const result = await api.triggerProfileMaintenance()
      if (result.success) {
        // Refresh profile files after maintenance
        await loadProfileFiles()
      }
    } catch (error) {
      console.error('Failed to trigger profile maintenance:', error)
    } finally {
      setIsTriggering(false)
    }
  }

  const handleSearch = async (): Promise<void> => {
    if (!searchQuery.trim()) return

    setIsLoading(true)
    setActiveTab('search')
    try {
      const { results } = await api.searchMemories(searchQuery, 50)
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

  const handleSemanticFilterChange = (filter: 'all' | SemanticCategory): void => {
    setSemanticFilter(filter)
    setSemanticPage(1)
  }

  // Reset semantic page when filter changes
  useEffect(() => {
    if (activeTab === 'semantic') {
      loadSemanticMemories(1)
      setSemanticPage(1)
    }
  }, [semanticFilter])

  const formatDate = (timestamp: number): string => {
    return new Date(timestamp).toLocaleDateString('zh-CN', {
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

  // Calculate total pages
  const episodicTotalPages = Math.ceil(totalEpisodicCount / PAGE_SIZE)
  const semanticTotalPages = Math.ceil(totalSemanticCount / PAGE_SIZE)

  const isZh = language === 'zh'

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header with Nemori branding */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12">
            <NemoriBot showStatus={false} size="lg" interactive={false} />
          </div>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Library className="w-6 h-6 text-primary" />
              {isZh ? '我的记忆库' : 'My Memory Library'}
            </h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              {isZh ? '我帮你记住的所有事情' : 'Everything I remember for you'}
            </p>
          </div>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-muted/60 hover:bg-muted transition-all duration-200 disabled:opacity-50 shadow-warm-sm"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>{isZh ? '刷新' : 'Refresh'}</span>
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
          placeholder={isZh ? '搜索记忆...' : 'Search memories...'}
          className="w-full pl-11 pr-4 py-3 rounded-lg border border-input/50 bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 shadow-warm-sm transition-all duration-200"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-border/50 pb-3">
        <TabButton
          active={activeTab === 'profile'}
          onClick={() => setActiveTab('profile')}
          icon={<FileText className="w-4 h-4" />}
          label={`${language === 'zh' ? '档案' : 'Profile'} (${profileFilesCount})`}
        />
        <TabButton
          active={activeTab === 'episodic'}
          onClick={() => setActiveTab('episodic')}
          icon={<Calendar className="w-4 h-4" />}
          label={`${language === 'zh' ? '情景' : 'Episodic'} (${totalEpisodicCount})`}
        />
        <TabButton
          active={activeTab === 'semantic'}
          onClick={() => setActiveTab('semantic')}
          icon={<Brain className="w-4 h-4" />}
          label={`${language === 'zh' ? '语义' : 'Semantic'} (${totalSemanticCount})`}
        />
        {searchResults.length > 0 && (
          <TabButton
            active={activeTab === 'search'}
            onClick={() => setActiveTab('search')}
            icon={<Search className="w-4 h-4" />}
            label={`${language === 'zh' ? '搜索' : 'Search'} (${searchResults.length})`}
          />
        )}

        {/* Profile maintenance trigger button */}
        {activeTab === 'profile' && (
          <button
            onClick={handleTriggerMaintenance}
            disabled={isTriggering}
            className="ml-auto flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-all duration-200 disabled:opacity-50"
          >
            <Zap className={`w-4 h-4 ${isTriggering ? 'animate-pulse' : ''}`} />
            <span className="text-sm font-medium">
              {isTriggering
                ? (language === 'zh' ? '更新中...' : 'Updating...')
                : (language === 'zh' ? '智能更新' : 'Smart Update')}
            </span>
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'episodic' && (
          <div className="flex flex-col h-full">
            <div className="flex-1 grid gap-4 content-start">
              {isLoading ? (
                <LoadingState />
              ) : episodicMemories.length === 0 ? (
                <EmptyState
                  icon={<Calendar className="w-12 h-12" />}
                  title={t('memories.noEpisodic')}
                  description={t('memories.noEpisodicDesc')}
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
            {/* Pagination */}
            {episodicTotalPages > 1 && (
              <Pagination
                currentPage={episodicPage}
                totalPages={episodicTotalPages}
                onPageChange={setEpisodicPage}
              />
            )}
          </div>
        )}

        {activeTab === 'semantic' && (
          <div className="flex flex-col h-full">
            {/* Semantic filter - 8 life categories */}
            <div className="flex flex-wrap gap-2 mb-4">
              <FilterButton
                active={semanticFilter === 'all'}
                onClick={() => handleSemanticFilterChange('all')}
                label="全部"
              />
              {(Object.keys(CATEGORY_CONFIG) as SemanticCategory[]).map((cat) => (
                <FilterButton
                  key={cat}
                  active={semanticFilter === cat}
                  onClick={() => handleSemanticFilterChange(cat)}
                  label={language === 'zh' ? CATEGORY_CONFIG[cat].labelZh : CATEGORY_CONFIG[cat].labelEn}
                  icon={CATEGORY_CONFIG[cat].icon}
                />
              ))}
            </div>

            <div className="flex-1 grid gap-3 content-start">
              {isLoading ? (
                <LoadingState />
              ) : filteredSemanticMemories.length === 0 ? (
                <EmptyState
                  icon={<Brain className="w-12 h-12" />}
                  title={t('memories.noSemantic')}
                  description={t('memories.noSemanticDesc')}
                />
              ) : (
                filteredSemanticMemories.map((memory) => (
                  <SemanticMemoryCard key={memory.id} memory={memory} formatDate={formatDate} />
                ))
              )}
            </div>
            {/* Pagination */}
            {semanticTotalPages > 1 && (
              <Pagination
                currentPage={semanticPage}
                totalPages={semanticTotalPages}
                onPageChange={setSemanticPage}
              />
            )}
          </div>
        )}

        {activeTab === 'profile' && (
          <div className="flex flex-col h-full">
            {isLoading ? (
              <LoadingState />
            ) : profileFiles.length === 0 ? (
              <EmptyState
                icon={<FolderOpen className="w-12 h-12" />}
                title={language === 'zh' ? '暂无档案文件' : 'No profile files yet'}
                description={language === 'zh' ? '档案文件将由智能体自动创建和维护' : 'Profile files will be created and maintained by the agent'}
              />
            ) : (
              <div className="space-y-4">
                {/* Group files by layer */}
                {Object.entries(
                  profileFiles.reduce((acc, file) => {
                    const layer = file.layer >= 0 ? file.layer : -1
                    if (!acc[layer]) acc[layer] = []
                    acc[layer].push(file)
                    return acc
                  }, {} as Record<number, ProfileFileInfo[]>)
                )
                  .sort(([a], [b]) => parseInt(a) - parseInt(b))
                  .map(([layerStr, files]) => {
                    const layer = parseInt(layerStr)
                    if (layer < 0) return null // Skip system files
                    const layerName = LAYER_NAMES[layer] || { en: `Layer ${layer}`, zh: `层级 ${layer}` }
                    const isExpanded = expandedLayers.has(layer)

                    return (
                      <div key={layer} className="border border-border/50 rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleLayer(layer)}
                          className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <FolderOpen className="w-4 h-4 text-primary" />
                            <span className="font-medium">
                              {language === 'zh' ? layerName.zh : layerName.en}
                            </span>
                            <span className="text-xs text-muted-foreground">({files.length})</span>
                          </div>
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>
                        {isExpanded && (
                          <div className="divide-y divide-border/30">
                            {files.map((file) => (
                              <div
                                key={file.relative_path}
                                onClick={() => {
                                  setSelectedProfileFile(file)
                                  loadProfileFileContent(file.relative_path)
                                }}
                                className="flex items-start gap-3 p-4 hover:bg-muted/30 cursor-pointer transition-colors"
                              >
                                <FileText className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium text-sm">{file.title || file.name}</span>
                                    <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                                      {Math.round(file.confidence * 100)}%
                                    </span>
                                  </div>
                                  {file.summary && (
                                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                      {file.summary}
                                    </p>
                                  )}
                                  {file.keywords && file.keywords.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-2">
                                      {file.keywords.slice(0, 4).map((kw, i) => (
                                        <span
                                          key={i}
                                          className="text-xs px-1.5 py-0.5 rounded-full bg-primary/10 text-primary"
                                        >
                                          {kw}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
              </div>
            )}
          </div>
        )}

        {activeTab === 'search' && (
          <div className="grid gap-3">
            {searchResults.length === 0 ? (
              <EmptyState
                icon={<Search className="w-12 h-12" />}
                title={t('memories.noResults')}
                description={t('memories.noResultsDesc')}
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

      {/* Profile file modal */}
      {selectedProfileFile && (
        <ProfileFileModal
          file={selectedProfileFile}
          content={profileFileContent}
          isEditing={isEditingProfile}
          editedContent={editedContent}
          onClose={() => {
            setSelectedProfileFile(null)
            setIsEditingProfile(false)
          }}
          onEdit={() => setIsEditingProfile(true)}
          onSave={handleSaveProfileFile}
          onContentChange={setEditedContent}
          language={language}
        />
      )}
    </div>
  )
}

function Pagination({
  currentPage,
  totalPages,
  onPageChange
}: {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
}): JSX.Element {
  const getVisiblePages = (): (number | string)[] => {
    const pages: (number | string)[] = []
    const maxVisible = 5

    if (totalPages <= maxVisible + 2) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      // Always show first page
      pages.push(1)

      if (currentPage > 3) {
        pages.push('...')
      }

      // Show pages around current
      const start = Math.max(2, currentPage - 1)
      const end = Math.min(totalPages - 1, currentPage + 1)

      for (let i = start; i <= end; i++) {
        if (!pages.includes(i)) {
          pages.push(i)
        }
      }

      if (currentPage < totalPages - 2) {
        pages.push('...')
      }

      // Always show last page
      if (!pages.includes(totalPages)) {
        pages.push(totalPages)
      }
    }

    return pages
  }

  return (
    <div className="flex items-center justify-center gap-1 py-4 mt-4 border-t border-border/50">
      {/* First page */}
      <button
        onClick={() => onPageChange(1)}
        disabled={currentPage === 1}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="First page"
      >
        <ChevronsLeft className="w-4 h-4" />
      </button>

      {/* Previous page */}
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="Previous page"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      {/* Page numbers */}
      <div className="flex items-center gap-1 mx-2">
        {getVisiblePages().map((page, idx) =>
          typeof page === 'number' ? (
            <button
              key={idx}
              onClick={() => onPageChange(page)}
              className={`min-w-[36px] h-9 px-3 rounded-lg text-sm font-medium transition-all ${
                currentPage === page
                  ? 'bg-primary text-primary-foreground shadow-warm-sm'
                  : 'hover:bg-muted/60'
              }`}
            >
              {page}
            </button>
          ) : (
            <span key={idx} className="px-2 text-muted-foreground">
              {page}
            </span>
          )
        )}
      </div>

      {/* Next page */}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="Next page"
      >
        <ChevronRight className="w-4 h-4" />
      </button>

      {/* Last page */}
      <button
        onClick={() => onPageChange(totalPages)}
        disabled={currentPage === totalPages}
        className="p-2 rounded-lg hover:bg-muted/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
        title="Last page"
      >
        <ChevronsRight className="w-4 h-4" />
      </button>

      {/* Page info */}
      <span className="ml-4 text-sm text-muted-foreground">
        Page {currentPage} of {totalPages}
      </span>
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

function LoadingState(): JSX.Element {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
      <p className="text-sm text-muted-foreground">Loading memories...</p>
    </div>
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
  const { language } = useLanguage()
  const categoryConfig = CATEGORY_CONFIG[memory.type]
  const label = categoryConfig
    ? (language === 'zh' ? categoryConfig.labelZh : categoryConfig.labelEn)
    : memory.type
  const icon = categoryConfig?.icon || <Brain className="w-4 h-4" />
  const color = categoryConfig?.color || 'bg-muted text-muted-foreground'

  return (
    <div className="flex items-start gap-3 p-4 rounded-lg glass-card hover:shadow-warm-sm transition-all duration-200">
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${color}`}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium text-muted-foreground">{label}</span>
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

// Helper function to strip frontmatter from markdown content
function stripFrontMatter(content: string): string {
  if (content.startsWith('---')) {
    const endIndex = content.indexOf('---', 3)
    if (endIndex !== -1) {
      return content.slice(endIndex + 3).trim()
    }
  }
  return content
}

function ProfileFileModal({
  file,
  content,
  isEditing,
  editedContent,
  onClose,
  onEdit,
  onSave,
  onContentChange,
  language
}: {
  file: ProfileFileInfo
  content: string
  isEditing: boolean
  editedContent: string
  onClose: () => void
  onEdit: () => void
  onSave: () => void
  onContentChange: (content: string) => void
  language: string
}): JSX.Element {
  const [viewMode, setViewMode] = useState<'preview' | 'code'>('preview')

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-card/95 backdrop-blur-md rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col shadow-warm-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-border/50">
          <div className="flex-1 pr-4">
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-6 h-6 text-primary" />
              <h2 className="text-xl font-bold">{file.title || file.name}</h2>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              <span>{file.relative_path}</span>
              <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground">
                {language === 'zh' ? '置信度' : 'Confidence'}: {Math.round(file.confidence * 100)}%
              </span>
              {file.updated_at && (
                <span>{language === 'zh' ? '更新于' : 'Updated'}: {new Date(file.updated_at).toLocaleDateString()}</span>
              )}
            </div>
            {file.summary && (
              <p className="text-sm text-muted-foreground mt-2">{file.summary}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {/* View Mode Toggle - only show when not editing */}
            {!isEditing && (
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
                  {language === 'zh' ? '预览' : 'Preview'}
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
                  {language === 'zh' ? '代码' : 'Code'}
                </button>
              </div>
            )}
            {!isEditing ? (
              <button
                onClick={onEdit}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
              >
                <Edit3 className="w-4 h-4" />
                <span>{language === 'zh' ? '编辑' : 'Edit'}</span>
              </button>
            ) : (
              <button
                onClick={onSave}
                className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Save className="w-4 h-4" />
                <span>{language === 'zh' ? '保存' : 'Save'}</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-muted/60 transition-all duration-200"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isEditing ? (
            <textarea
              value={editedContent}
              onChange={(e) => onContentChange(e.target.value)}
              className="w-full h-full min-h-[400px] p-4 rounded-lg border border-input bg-background font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30"
              placeholder={language === 'zh' ? '在此编辑档案内容...' : 'Edit profile content here...'}
            />
          ) : content ? (
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
                  {stripFrontMatter(content)}
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
                {content}
              </SyntaxHighlighter>
            )
          ) : (
            <p className="text-muted-foreground text-center py-8">
              {language === 'zh' ? '加载中...' : 'Loading...'}
            </p>
          )}
        </div>

        {/* Footer - Keywords */}
        {file.keywords && file.keywords.length > 0 && (
          <div className="p-4 border-t border-border/50 bg-muted/30">
            <div className="flex flex-wrap gap-2">
              {file.keywords.map((kw, i) => (
                <span
                  key={i}
                  className="text-xs px-2 py-1 rounded-full bg-primary/10 text-primary"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
