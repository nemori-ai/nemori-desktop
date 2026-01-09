import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, Plus, Trash2, Loader2, Bot, MessageCircle, ChevronDown, ChevronRight, Sparkles, Search, Clock } from 'lucide-react'
import MarkdownIt from 'markdown-it'
import { api, Message, Conversation, AgentStreamEvent, AgentToolCall } from '../services/api'

// Initialize markdown parser - same approach as MineContext
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
})

// Markdown rendering component using dangerouslySetInnerHTML
function MarkdownContent({ content }: { content: string }): JSX.Element {
  const htmlContent = useMemo(() => {
    return md.render(content || '')
  }, [content])

  return (
    <div
      className="markdown-content select-text"
      dangerouslySetInnerHTML={{ __html: htmlContent }}
    />
  )
}

// Helper function to format relative dates
function formatRelativeDate(timestamp: number): string {
  const now = Date.now()
  const diff = now - timestamp
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days === 0) {
    if (hours === 0) {
      if (minutes < 1) return 'Just now'
      return `${minutes}m ago`
    }
    return `${hours}h ago`
  }
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`

  return new Date(timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

// Tool call icon mapping
const toolIcons: Record<string, JSX.Element> = {
  search_episodic_memory: <Search className="w-3.5 h-3.5" />,
  search_semantic_memory: <Sparkles className="w-3.5 h-3.5" />,
  keyword_search: <Search className="w-3.5 h-3.5" />,
  time_filter: <Clock className="w-3.5 h-3.5" />,
  get_user_profile: <Bot className="w-3.5 h-3.5" />,
  get_recent_activity: <Clock className="w-3.5 h-3.5" />
}

// Tool call display component
function ToolCallDisplay({
  toolCall,
  isExpanded,
  onToggle
}: {
  toolCall: AgentToolCall
  isExpanded: boolean
  onToggle: () => void
}): JSX.Element {
  const statusColors = {
    pending: 'text-muted-foreground',
    running: 'text-primary',
    completed: 'text-primary',
    error: 'text-destructive'
  }

  const formatToolName = (name: string) => {
    return name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
  }

  // Parse result if it's a string
  let parsedResult = toolCall.result
  if (typeof parsedResult === 'string') {
    try {
      parsedResult = JSON.parse(parsedResult)
    } catch {
      // Keep as string
    }
  }

  return (
    <div className="rounded-lg overflow-hidden glass-card my-2 max-w-full">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-muted/40 transition-all duration-200 text-left"
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        )}
        <span className={`${statusColors[toolCall.status]}`}>
          {toolIcons[toolCall.tool_name] || <Bot className="w-3.5 h-3.5" />}
        </span>
        <span className="text-sm font-medium flex-1 truncate">
          {formatToolName(toolCall.tool_name)}
        </span>
        {toolCall.status === 'running' && (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
        )}
        {toolCall.duration_ms && (
          <span className="text-xs text-muted-foreground">
            {toolCall.duration_ms}ms
          </span>
        )}
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-2 text-xs overflow-hidden">
          {/* Arguments */}
          <div className="overflow-hidden">
            <span className="text-muted-foreground">Arguments:</span>
            <pre className="mt-1 p-2 bg-background rounded text-xs overflow-x-auto max-w-full whitespace-pre-wrap break-all">
              {JSON.stringify(toolCall.tool_args, null, 2)}
            </pre>
          </div>

          {/* Result */}
          {toolCall.result && (
            <div className="overflow-hidden">
              <span className="text-muted-foreground">Result:</span>
              <pre className="mt-1 p-2 bg-background rounded text-xs overflow-x-auto max-h-48 overflow-y-auto max-w-full whitespace-pre-wrap break-all">
                {typeof parsedResult === 'object'
                  ? JSON.stringify(parsedResult, null, 2)
                  : String(parsedResult)}
              </pre>
            </div>
          )}

          {/* Error */}
          {toolCall.error && (
            <div className="overflow-hidden">
              <span className="text-red-500">Error:</span>
              <pre className="mt-1 p-2 bg-red-500/10 rounded text-xs text-red-500 max-w-full whitespace-pre-wrap break-all">
                {toolCall.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Agent thinking indicator
function ThinkingIndicator({ step }: { step: number }): JSX.Element {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
      <div className="flex items-center gap-1">
        <span className="w-2 h-2 bg-primary rounded-full animate-pulse" />
        <span className="w-2 h-2 bg-primary rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
        <span className="w-2 h-2 bg-primary rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
      </div>
      <span>Thinking (Step {step})...</span>
    </div>
  )
}

// Agent message component with tool calls
function AgentMessageBubble({
  content,
  toolCalls,
  isThinking,
  thinkingStep,
  isStreaming
}: {
  content: string
  toolCalls: AgentToolCall[]
  isThinking: boolean
  thinkingStep: number
  isStreaming: boolean
}): JSX.Element {
  const [expandedTools, setExpandedTools] = useState<Set<string>>(new Set())

  const toggleTool = (id: string) => {
    setExpandedTools((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  return (
    <div className="flex justify-start message-enter">
      <div className="max-w-[85%]">
        {/* Thinking indicator */}
        {isThinking && <ThinkingIndicator step={thinkingStep} />}

        {/* Tool calls */}
        {toolCalls.length > 0 && (
          <div className="mb-2">
            {toolCalls.map((tc) => (
              <ToolCallDisplay
                key={tc.id}
                toolCall={tc}
                isExpanded={expandedTools.has(tc.id)}
                onToggle={() => toggleTool(tc.id)}
              />
            ))}
          </div>
        )}

        {/* Response content - Claude style without bubble */}
        {(content || isStreaming) && (
          <div className="prose prose-sm max-w-none text-foreground">
            {content ? (
              <>
                <MarkdownContent content={content} />
                {isStreaming && (
                  <span className="inline-block w-2 h-4 bg-primary/70 animate-pulse ml-0.5 align-middle" />
                )}
              </>
            ) : (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatPage(): JSX.Element {
  const { conversationId } = useParams()
  const navigate = useNavigate()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversation, setCurrentConversation] = useState<string | null>(conversationId || null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')

  // Agent mode state
  const [isAgentMode, setIsAgentMode] = useState(false)
  const [isThinking, setIsThinking] = useState(false)
  const [thinkingStep, setThinkingStep] = useState(0)
  const [currentToolCalls, setCurrentToolCalls] = useState<AgentToolCall[]>([])

  // Refs to track latest values (to avoid stale closures)
  const streamingContentRef = useRef('')
  const toolCallsRef = useRef<AgentToolCall[]>([])
  const currentConversationRef = useRef<string | null>(conversationId || null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Load conversations
  useEffect(() => {
    loadConversations()
  }, [])

  // Load messages when conversation changes
  useEffect(() => {
    if (conversationId) {
      setCurrentConversation(conversationId)
      currentConversationRef.current = conversationId
      loadMessages(conversationId)
    }
  }, [conversationId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, currentToolCalls])

  const loadConversations = async (): Promise<void> => {
    try {
      const { conversations } = await api.getConversations()
      setConversations(conversations)
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  }

  const loadMessages = async (convId: string): Promise<void> => {
    try {
      const { messages } = await api.getMessages(convId)

      // For agent messages, fetch their tool calls
      const messagesWithToolCalls = await Promise.all(
        messages.map(async (msg) => {
          if (msg.metadata?.is_agent && msg.metadata?.session_id) {
            try {
              const sessionDetails = await api.getAgentSessionDetails(msg.metadata.session_id)
              return {
                ...msg,
                metadata: {
                  ...msg.metadata,
                  tool_calls: sessionDetails.tool_calls || []
                }
              }
            } catch {
              return msg
            }
          }
          return msg
        })
      )

      setMessages(messagesWithToolCalls)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const handleNewConversation = (): void => {
    currentConversationRef.current = null
    setCurrentConversation(null)
    setMessages([])
    navigate('/chat')
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent): Promise<void> => {
    e.stopPropagation()
    try {
      await api.deleteConversation(id)
      await loadConversations()
      if (currentConversation === id) {
        currentConversationRef.current = null
        setCurrentConversation(null)
        setMessages([])
        navigate('/chat')
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    }
  }

  const handleAgentEvent = useCallback((event: AgentStreamEvent) => {
    switch (event.type) {
      case 'session_start':
        setCurrentToolCalls([])
        toolCallsRef.current = []
        break

      case 'thinking_start':
        setIsThinking(true)
        setThinkingStep(event.step || 1)
        break

      case 'thinking_end':
        setIsThinking(false)
        break

      case 'tool_call_start': {
        const newToolCall: AgentToolCall = {
          id: event.data.tool_call_id || event.tool_call_id || '',
          session_id: event.session_id,
          step: event.step || 0,
          tool_name: event.data.tool_name || '',
          tool_args: {},
          status: 'running'
        }
        setCurrentToolCalls((prev) => {
          const updated = [...prev, newToolCall]
          toolCallsRef.current = updated
          return updated
        })
        break
      }

      case 'tool_call_args':
        setCurrentToolCalls((prev) => {
          const updated = prev.map((tc) =>
            tc.id === (event.data.tool_call_id || event.tool_call_id)
              ? { ...tc, tool_args: event.data.args || {} }
              : tc
          )
          toolCallsRef.current = updated
          return updated
        })
        break

      case 'tool_call_result':
        setCurrentToolCalls((prev) => {
          const updated = prev.map((tc) =>
            tc.id === (event.data.tool_call_id || event.tool_call_id)
              ? {
                  ...tc,
                  status: 'completed' as const,
                  result: event.data.result,
                  duration_ms: event.data.duration_ms
                }
              : tc
          )
          toolCallsRef.current = updated
          return updated
        })
        break

      case 'tool_call_error':
        setCurrentToolCalls((prev) => {
          const updated = prev.map((tc) =>
            tc.id === (event.data.tool_call_id || event.tool_call_id)
              ? { ...tc, status: 'error' as const, error: event.data.error }
              : tc
          )
          toolCallsRef.current = updated
          return updated
        })
        break

      case 'response_chunk':
        setStreamingContent((prev) => {
          const updated = prev + (event.data.content || '')
          streamingContentRef.current = updated
          return updated
        })
        break

      case 'response_end':
        streamingContentRef.current = event.data.content || ''
        setStreamingContent(event.data.content || '')
        break

      case 'error':
        console.error('Agent error:', event.data)
        break
    }
  }, [])

  const handleSend = async (): Promise<void> => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setIsLoading(true)

    // Add user message to UI immediately
    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: userMessage,
      timestamp: Date.now(),
      conversation_id: currentConversation || ''
    }
    setMessages((prev) => [...prev, tempUserMessage])

    try {
      setIsStreaming(true)
      setStreamingContent('')

      if (isAgentMode) {
        // Agent mode - use streaming agent API
        setCurrentToolCalls([])
        toolCallsRef.current = []
        streamingContentRef.current = ''
        setIsThinking(false)

        // Use ref to get the latest conversation ID (state might be stale)
        const currentConvId = currentConversationRef.current
        console.log('[Agent] Sending with conversationId:', currentConvId)

        const { conversationId: newConvId, sessionId } = await api.streamAgentChat(
          userMessage,
          currentConvId || undefined,
          10,
          handleAgentEvent
        )
        console.log('[Agent] Received newConvId:', newConvId, 'sessionId:', sessionId)

        // Use refs to get the latest values (avoid stale closures)
        const finalContent = streamingContentRef.current
        const finalToolCalls = [...toolCallsRef.current]

        // Add assistant message with tool calls and session_id for later retrieval
        const assistantMessage: Message = {
          id: `response-${Date.now()}`,
          role: 'assistant',
          content: finalContent,
          timestamp: Date.now(),
          conversation_id: newConvId,
          metadata: { tool_calls: finalToolCalls, is_agent: true, session_id: sessionId }
        }

        setMessages((prev) => [...prev, assistantMessage])
        setStreamingContent('')
        setCurrentToolCalls([])
        streamingContentRef.current = ''
        toolCallsRef.current = []

        // Always update conversation state and ref with the returned ID
        // This ensures we track the correct conversation even if state hasn't updated yet
        if (newConvId) {
          currentConversationRef.current = newConvId
          setCurrentConversation(newConvId)
          // Only navigate if URL doesn't match
          if (conversationId !== newConvId) {
            navigate(`/chat/${newConvId}`, { replace: true })
          }
        }

        // Refresh conversations
        await loadConversations()
      } else {
        // Normal chat mode
        // Use ref to get the latest conversation ID (state might be stale)
        const currentConvId = currentConversationRef.current
        console.log('[Chat] Sending with conversationId:', currentConvId)

        const { content: fullResponse, conversationId: newConvId } = await api.streamMessage(
          userMessage,
          currentConvId || undefined,
          undefined,
          true,
          (chunk) => {
            setStreamingContent((prev) => prev + chunk)
          }
        )

        // Add assistant message
        const assistantMessage: Message = {
          id: `response-${Date.now()}`,
          role: 'assistant',
          content: fullResponse,
          timestamp: Date.now(),
          conversation_id: newConvId
        }

        setMessages((prev) => [...prev, assistantMessage])
        setStreamingContent('')

        // Always update conversation state and ref with the returned ID
        if (newConvId) {
          console.log('[Chat] Updating ref to:', newConvId)
          currentConversationRef.current = newConvId
          setCurrentConversation(newConvId)
          if (conversationId !== newConvId) {
            navigate(`/chat/${newConvId}`, { replace: true })
          }
        }

        await loadConversations()
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMessage.id))
    } finally {
      setIsLoading(false)
      setIsStreaming(false)
      setIsThinking(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex h-full">
      {/* Conversations sidebar with glass effect */}
      <div className="w-64 flex flex-col glass-sidebar">
        <div className="p-4 border-b border-border/50">
          <button
            onClick={handleNewConversation}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-all duration-200 shadow-warm-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => navigate(`/chat/${conv.id}`)}
              className={`group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200 ${
                currentConversation === conv.id
                  ? 'bg-primary/12 text-primary shadow-warm-sm'
                  : 'hover:bg-muted/60 text-foreground'
              }`}
            >
              <div className="flex-1 min-w-0 mr-2">
                <span className="text-sm truncate block">{conv.title}</span>
                <span className="text-[10px] text-muted-foreground">
                  {formatRelativeDate(conv.updated_at)}
                </span>
              </div>
              <button
                onClick={(e) => handleDeleteConversation(conv.id, e)}
                className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-destructive/15 hover:text-destructive transition-all duration-200 flex-shrink-0"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Mode toggle header */}
        <div className="border-b border-border/50 px-5 py-3 flex items-center justify-between bg-background/50 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Mode:</span>
            <div className="flex items-center bg-muted/60 rounded-lg p-1 shadow-warm-sm">
              <button
                onClick={() => setIsAgentMode(false)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-all duration-200 ${
                  !isAgentMode
                    ? 'bg-background text-foreground shadow-warm-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <MessageCircle className="w-4 h-4" />
                Chat
              </button>
              <button
                onClick={() => setIsAgentMode(true)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-all duration-200 ${
                  isAgentMode
                    ? 'bg-background text-foreground shadow-warm-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Bot className="w-4 h-4" />
                Agent
              </button>
            </div>
          </div>
          {isAgentMode && (
            <span className="text-xs text-muted-foreground">
              Deep memory search with tools
            </span>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && !isStreaming ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              {isAgentMode ? (
                <>
                  <Bot className="w-16 h-16 mb-4 opacity-50" />
                  <h2 className="text-xl font-semibold mb-2">Agent Mode</h2>
                  <p className="text-sm text-center max-w-md">
                    I can search through your memories using various tools to find the best answers.
                    Try asking about past events, preferences, or activities!
                  </p>
                </>
              ) : (
                <>
                  <MessageIcon className="w-16 h-16 mb-4 opacity-50" />
                  <h2 className="text-xl font-semibold mb-2">Welcome to Nemori</h2>
                  <p className="text-sm">Start a conversation or ask me anything!</p>
                </>
              )}
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <div key={message.id}>
                  {message.role === 'user' ? (
                    <UserMessageBubble message={message} />
                  ) : message.metadata?.is_agent ? (
                    <AgentMessageBubble
                      content={message.content}
                      toolCalls={message.metadata?.tool_calls || []}
                      isThinking={false}
                      thinkingStep={0}
                      isStreaming={false}
                    />
                  ) : (
                    <AssistantMessageBubble message={message} />
                  )}
                </div>
              ))}

              {/* Streaming content */}
              {isStreaming && (
                isAgentMode ? (
                  <AgentMessageBubble
                    content={streamingContent}
                    toolCalls={currentToolCalls}
                    isThinking={isThinking}
                    thinkingStep={thinkingStep}
                    isStreaming={true}
                  />
                ) : (
                  <AssistantMessageBubble
                    message={{
                      id: 'streaming',
                      role: 'assistant',
                      content: streamingContent,
                      timestamp: Date.now(),
                      conversation_id: ''
                    }}
                    isStreaming={true}
                  />
                )
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-border/50 p-5 bg-background/80 backdrop-blur-sm">
          <div className="flex items-end gap-3 max-w-4xl mx-auto">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isAgentMode ? "Ask me to search your memories..." : "Type a message..."}
              rows={1}
              className="flex-1 resize-none rounded-lg border border-input/50 bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50 shadow-warm-sm transition-all duration-200"
              disabled={isLoading}
              style={{ maxHeight: '150px', minHeight: '48px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="flex items-center justify-center w-12 h-12 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-warm hover:shadow-warm-lg"
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// User message bubble - with background
function UserMessageBubble({ message }: { message: Message }): JSX.Element {
  return (
    <div className="flex justify-end message-enter">
      <div className="max-w-[80%]">
        <div className="rounded-2xl px-4 py-3 bg-primary text-primary-foreground">
          <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </div>
    </div>
  )
}

// Assistant message bubble - Claude style without background
function AssistantMessageBubble({
  message,
  isStreaming = false
}: {
  message: Message
  isStreaming?: boolean
}): JSX.Element {
  return (
    <div className="flex justify-start message-enter">
      <div className="max-w-[85%] prose prose-sm max-w-none text-foreground">
        {isStreaming && !message.content ? (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 bg-current rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </span>
        ) : (
          <>
            <MarkdownContent content={message.content} />
            {isStreaming && (
              <span className="inline-block w-2 h-4 bg-primary/70 animate-pulse ml-0.5 align-middle" />
            )}
          </>
        )}
      </div>
    </div>
  )
}

function MessageIcon({ className }: { className?: string }): JSX.Element {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
      />
    </svg>
  )
}
