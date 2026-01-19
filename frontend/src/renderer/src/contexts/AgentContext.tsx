import { createContext, useContext, useState, ReactNode, useEffect } from 'react'
import { api } from '../services/api'

// PICO-8 Palette Colors for reference
export const PICO_COLORS = {
  BLACK: '#000000',
  DARK_BLUE: '#1D2B53',
  DARK_PURPLE: '#7E2553',
  DARK_GREEN: '#008751',
  BROWN: '#AB5236',
  DARK_GREY: '#5F574F',
  LIGHT_GREY: '#C2C3C7',
  WHITE: '#FFF1E8',
  RED: '#FF004D',
  ORANGE: '#FFA300',
  YELLOW: '#FFEC27',
  GREEN: '#00E436',
  BLUE: '#29ADFF',
  INDIGO: '#83769C',
  PINK: '#FF77A8',
  PEACH: '#FFCCAA'
}

export type AgentMood = 'idle' | 'happy' | 'thinking' | 'confused' | 'sleeping'
export type AgentStyle = 'sprout' | 'neko' | 'bobble'

interface AgentContextType {
  // State
  isThinking: boolean
  isRecording: boolean
  mood: AgentMood
  style: AgentStyle
  isPetMode: boolean
  
  // Actions
  setThinking: (thinking: boolean) => void
  setMood: (mood: AgentMood) => void
  setStyle: (style: AgentStyle) => void
  togglePetMode: () => Promise<void>
  
  // Helpers
  cycleStyle: () => void
}

const AgentContext = createContext<AgentContextType | undefined>(undefined)

const STYLE_STORAGE_KEY = 'nemori-agent-style'

export function AgentProvider({ children }: { children: ReactNode }): JSX.Element {
  // Persistent state
  const [style, setStyleState] = useState<AgentStyle>(() => {
    const stored = localStorage.getItem(STYLE_STORAGE_KEY)
    return (stored as AgentStyle) || 'sprout'
  })

  // Ephemeral state
  const [isThinking, setIsThinking] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [mood, setMood] = useState<AgentMood>('idle')
  const [isPetMode, setIsPetMode] = useState(false)

  // Persist style changes
  const setStyle = (newStyle: AgentStyle) => {
    setStyleState(newStyle)
    localStorage.setItem(STYLE_STORAGE_KEY, newStyle)
  }

  const cycleStyle = () => {
    const styles: AgentStyle[] = ['sprout', 'neko', 'bobble']
    const currentIndex = styles.indexOf(style)
    const nextStyle = styles[(currentIndex + 1) % styles.length]
    setStyle(nextStyle)
  }
  
  // Sync recording state with backend
  useEffect(() => {
    let intervalId: NodeJS.Timeout

    const checkStatus = async () => {
      try {
        const status = await api.getCaptureStatus()
        setIsRecording(status.is_capturing)
      } catch (e) {
        console.error('Failed to sync capture status:', e)
      }
    }

    // Check immediately and then every 5 seconds
    checkStatus()
    intervalId = setInterval(checkStatus, 5000)

    return () => clearInterval(intervalId)
  }, [])

  // Auto-update mood based on activity
  useEffect(() => {
    if (isThinking) {
      setMood('thinking')
    } else if (isRecording) {
      // Occasional scanning mood when recording
      const timer = setInterval(() => {
        setMood(prev => prev === 'idle' ? 'thinking' : 'idle')
      }, 8000)
      return () => clearInterval(timer)
    } else {
      setMood('idle')
    }
    return
  }, [isThinking, isRecording])

  const togglePetMode = async () => {
    // This will be implemented when we add Electron IPC for the pet window
    console.log('Toggle pet mode')
    setIsPetMode(!isPetMode)
  }

  return (
    <AgentContext.Provider
      value={{
        isThinking,
        isRecording,
        mood,
        style,
        isPetMode,
        setThinking: setIsThinking,
        setMood,
        setStyle,
        togglePetMode,
        cycleStyle
      }}
    >
      {children}
    </AgentContext.Provider>
  )
}

export function useAgent(): AgentContextType {
  const context = useContext(AgentContext)
  if (context === undefined) {
    throw new Error('useAgent must be used within an AgentProvider')
  }
  return context
}
