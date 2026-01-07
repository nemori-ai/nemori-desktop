import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Send, Plus, Trash2, Loader2 } from 'lucide-react'
import MarkdownIt from 'markdown-it'
import { api, Message, Conversation } from '../services/api'

// Initialize markdown parser - same approach as MineContext
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
})

// Markdown rendering component using dangerouslySetInnerHTML
// This approach handles streaming content much better than React-based markdown renderers
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
      loadMessages(conversationId)
    }
  }, [conversationId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

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
      setMessages(messages)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const handleNewConversation = (): void => {
    // Don't create conversation yet - just go to empty chat
    // Conversation will be created when first message is sent
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
        navigate('/chat')
        setMessages([])
        setCurrentConversation(null)
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    }
  }

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

      // Use streaming API
      const { content: fullResponse, conversationId: newConvId } = await api.streamMessage(
        userMessage,
        currentConversation || undefined,
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

      // Refresh conversations to get updated titles
      await loadConversations()

      // If this was a new conversation, update the URL and state
      if (!currentConversation && newConvId) {
        setCurrentConversation(newConvId)
        navigate(`/chat/${newConvId}`)
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      // Remove temp message on error
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMessage.id))
    } finally {
      setIsLoading(false)
      setIsStreaming(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    // Check if IME is composing (e.g., typing Chinese/Japanese)
    // nativeEvent.isComposing is true when user is selecting characters
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex h-full">
      {/* Conversations sidebar */}
      <div className="w-64 border-r border-border flex flex-col bg-muted/30">
        <div className="p-3 border-b border-border">
          <button
            onClick={handleNewConversation}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => navigate(`/chat/${conv.id}`)}
              className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                currentConversation === conv.id
                  ? 'bg-primary/10 text-primary'
                  : 'hover:bg-muted text-foreground'
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
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/20 hover:text-destructive transition-all flex-shrink-0"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !isStreaming ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <MessageIcon className="w-16 h-16 mb-4 opacity-50" />
              <h2 className="text-xl font-semibold mb-2">Welcome to Nemori</h2>
              <p className="text-sm">Start a conversation or ask me anything!</p>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {isStreaming && (
                <MessageBubble
                  message={{
                    id: 'streaming',
                    role: 'assistant',
                    content: streamingContent || '',
                    timestamp: Date.now(),
                    conversation_id: ''
                  }}
                  isStreaming
                />
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-border p-4">
          <div className="flex items-end gap-3 max-w-4xl mx-auto">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              rows={1}
              className="flex-1 resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50"
              disabled={isLoading}
              style={{ maxHeight: '150px', minHeight: '48px' }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="flex items-center justify-center w-12 h-12 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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

function MessageBubble({
  message,
  isStreaming = false
}: {
  message: Message
  isStreaming?: boolean
}): JSX.Element {
  const isUser = message.role === 'user'

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} message-enter group`}
    >
      <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-[80%]`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-foreground'
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
          ) : (
            <div className="markdown-content text-sm">
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
          )}
        </div>
        <span className="text-[10px] text-muted-foreground mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {formatTime(message.timestamp)}
        </span>
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
