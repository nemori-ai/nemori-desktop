import { useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { NemoriBot } from '../components/NemoriBot'
import { useAgent } from '../contexts/AgentContext'
import { useLanguage } from '../contexts/LanguageContext'

export default function PetPage(): JSX.Element {
  const { isRecording, isThinking } = useAgent()
  const { language } = useLanguage()
  const [showTooltip, setShowTooltip] = useState(false)
  const [tooltipMessage, setTooltipMessage] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  const dragRef = useRef<{ startX: number; startY: number } | null>(null)

  const isZh = language === 'zh'

  // Bilingual messages
  const messages = {
    idle: {
      en: ["I'm here with you~", "Double-click to open Nemori!", "Right-click for options~"],
      zh: ["我在这里陪着你~", "双击打开 Nemori！", "右键查看更多~"]
    },
    recording: {
      en: ["Taking notes...", "Remembering..."],
      zh: ["正在做笔记...", "记录中..."]
    },
    thinking: {
      en: ["Let me think...", "Processing..."],
      zh: ["让我想想...", "处理中..."]
    }
  }

  // Apply transparent background styles
  useEffect(() => {
    document.body.style.background = 'transparent'
    document.documentElement.style.background = 'transparent'
    document.body.style.overflow = 'hidden'
    document.body.style.margin = '0'
    document.body.style.padding = '0'

    const root = document.getElementById('root')
    if (root) {
      root.style.background = 'transparent'
    }

    return () => {
      document.body.style.background = ''
      document.documentElement.style.background = ''
    }
  }, [])

  // Manual drag implementation for Electron transparent window
  // Use refs to avoid re-renders during drag
  const isDraggingRef = useRef(false)
  const hasMoved = useRef(false)
  const DRAG_THRESHOLD = 3 // pixels before considering it a drag

  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      // Only skip drag for the close button
      const target = e.target as HTMLElement
      if (target.closest('.no-drag') || target.closest('button')) {
        return
      }

      // Prevent default to stop native drag behavior
      e.preventDefault()
      isDraggingRef.current = true
      hasMoved.current = false
      dragRef.current = { startX: e.screenX, startY: e.screenY }
    }

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current || !dragRef.current) return

      const deltaX = e.screenX - dragRef.current.startX
      const deltaY = e.screenY - dragRef.current.startY

      // Only move if we've exceeded the threshold (actual drag, not just click)
      if (Math.abs(deltaX) > DRAG_THRESHOLD || Math.abs(deltaY) > DRAG_THRESHOLD || hasMoved.current) {
        hasMoved.current = true
        window.api.pet.move(deltaX, deltaY)
        dragRef.current = { startX: e.screenX, startY: e.screenY }

        // Only update state if not already dragging (for cursor change)
        if (!isDragging) {
          setIsDragging(true)
        }
      }
    }

    const handleMouseUp = () => {
      isDraggingRef.current = false
      hasMoved.current = false
      dragRef.current = null
      setIsDragging(false)
    }

    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('mouseleave', handleMouseUp)

    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('mouseleave', handleMouseUp)
    }
  }, [isDragging])

  // Show random tooltip occasionally
  useEffect(() => {
    const showRandomMessage = () => {
      let msgList = messages.idle[isZh ? 'zh' : 'en']
      if (isRecording) msgList = messages.recording[isZh ? 'zh' : 'en']
      if (isThinking) msgList = messages.thinking[isZh ? 'zh' : 'en']

      const randomMessage = msgList[Math.floor(Math.random() * msgList.length)]
      setTooltipMessage(randomMessage)
      setShowTooltip(true)
      setTimeout(() => setShowTooltip(false), 3000)
    }

    if (isRecording || isThinking) {
      showRandomMessage()
    }

    const interval = setInterval(() => {
      if (Math.random() > 0.8) {
        showRandomMessage()
      }
    }, 20000) // Less frequent

    return () => clearInterval(interval)
  }, [isRecording, isThinking, isZh])

  // Prevent native drag behavior
  const preventDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }

  // Window is 140x160, pet should be centered
  return (
    <div
      className="select-none overflow-hidden"
      style={{
        width: '140px',
        height: '160px',
        background: 'transparent',
        cursor: isDragging ? 'grabbing' : 'grab',
        position: 'relative'
      }}
      draggable={false}
      onDragStart={preventDrag}
      onDrag={preventDrag}
      onDragOver={preventDrag}
    >
      {/* Close button - top right */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          window.api.pet.close()
        }}
        onMouseDown={(e) => e.stopPropagation()}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          width: '20px',
          height: '20px',
          borderRadius: '50%',
          background: 'rgba(0,0,0,0.3)',
          color: 'rgba(255,255,255,0.7)',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '12px',
          zIndex: 100
        }}
        className="no-drag hover:bg-red-500 hover:text-white transition-colors"
      >
        ✕
      </button>

      {/* Pet - centered in window */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '64px',
          height: '64px',
          cursor: isDragging ? 'grabbing' : 'grab'
        }}
        draggable={false}
        onDragStart={preventDrag}
      >
        {/* Glow effect behind pet */}
        {(isRecording || isThinking) && (
          <motion.div
            style={{
              position: 'absolute',
              top: '-8px',
              left: '-8px',
              right: '-8px',
              bottom: '-8px',
              borderRadius: '50%',
              background: isRecording ? 'rgba(74, 222, 128, 0.3)' : 'rgba(96, 165, 250, 0.3)',
              zIndex: -1
            }}
            animate={{ scale: [1, 1.1, 1], opacity: [0.5, 0.8, 0.5] }}
            transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
          />
        )}
        <NemoriBot showStatus={false} size="lg" interactive={false} />
      </div>

      {/* Status Badge - bottom center */}
      {(isRecording || isThinking) && (
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '3px 8px',
            borderRadius: '999px',
            fontSize: '10px',
            fontWeight: 500,
            background: isRecording ? '#22c55e' : '#3b82f6',
            color: 'white',
            whiteSpace: 'nowrap',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
            zIndex: 50
          }}
        >
          {isRecording ? (isZh ? '📝 记录中' : '📝 REC') : (isZh ? '💭 思考' : '💭')}
        </div>
      )}

      {/* Speech Bubble - top center */}
      <AnimatePresence>
        {showTooltip && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            style={{
              position: 'absolute',
              top: '8px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 100,
              pointerEvents: 'none'
            }}
          >
            <div style={{
              padding: '4px 10px',
              background: 'rgba(255,255,255,0.95)',
              borderRadius: '8px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              fontSize: '11px',
              fontWeight: 500,
              color: '#374151',
              whiteSpace: 'nowrap'
            }}>
              {tooltipMessage}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
