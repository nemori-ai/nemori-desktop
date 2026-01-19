import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence, TargetAndTransition } from 'framer-motion'
import { useAgent } from '../contexts/AgentContext'
import { useLanguage } from '../contexts/LanguageContext'

// Import SVGs
import SproutSvg from '../assets/nemori/style_sprout.svg'
import NekoSvg from '../assets/nemori/style_neko.svg'
import BobbleSvg from '../assets/nemori/style_bobble.svg'

interface NemoriBotProps {
  className?: string
  onClick?: () => void
  showStatus?: boolean
  size?: 'sm' | 'md' | 'lg' | 'xl'
  interactive?: boolean
}

export const NemoriBot: React.FC<NemoriBotProps> = ({
  className,
  onClick,
  showStatus = true,
  size = 'md',
  interactive = true
}) => {
  const { style, mood, isThinking, isRecording, cycleStyle } = useAgent()
  const { language, t } = useLanguage()
  const [isHovered, setIsHovered] = useState(false)
  const [blinkState, setBlinkState] = useState(false)
  const [eyePosition, setEyePosition] = useState({ x: 0, y: 0 })

  const isZh = language === 'zh'

  // Simulate blinking
  useEffect(() => {
    const blinkInterval = setInterval(() => {
      if (Math.random() > 0.7 && !isThinking) {
        setBlinkState(true)
        setTimeout(() => setBlinkState(false), 150)
      }
    }, 3000)

    return () => clearInterval(blinkInterval)
  }, [isThinking])

  // Eye tracking effect on hover
  useEffect(() => {
    if (!isHovered) {
      setEyePosition({ x: 0, y: 0 })
      return
    }

    const handleMouseMove = (e: MouseEvent) => {
      const x = Math.min(Math.max((e.clientX / window.innerWidth - 0.5) * 4, -2), 2)
      const y = Math.min(Math.max((e.clientY / window.innerHeight - 0.5) * 4, -2), 2)
      setEyePosition({ x, y })
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [isHovered])

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (interactive) {
      cycleStyle()
    }
    onClick?.()
  }

  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-16 h-16',
    xl: 'w-24 h-24'
  }

  // Determine animation variant based on state
  const getAnimation = (): TargetAndTransition => {
    if (isThinking) {
      return {
        y: [0, -3, 0, -3, 0],
        rotate: [-2, 2, -2, 2, 0],
        transition: {
          repeat: Infinity,
          duration: 0.6,
          ease: "linear"
        }
      }
    }

    if (isRecording) {
      return {
        x: [-2, 2, -2],
        y: [0, -1, 0],
        transition: {
          repeat: Infinity,
          duration: 3,
          ease: "easeInOut"
        }
      }
    }

    if (mood === 'happy') {
      return {
        y: [0, -12, 0],
        scale: [1, 1.08, 1],
        rotate: [0, -3, 3, 0],
        transition: {
          repeat: Infinity,
          duration: 0.7,
          ease: "easeOut"
        }
      }
    }

    if (mood === 'sleeping') {
      return {
        y: [0, 2, 0],
        rotate: [-5, -5, -5],
        transition: {
          repeat: Infinity,
          duration: 4,
          ease: "easeInOut"
        }
      }
    }

    // Default Idle - gentle floating
    return {
      y: [0, -5, 0],
      transition: {
        repeat: Infinity,
        duration: 2.5,
        ease: "easeInOut"
      }
    }
  }

  // Get status message - bilingual
  const getStatusMessage = () => {
    if (isThinking) return isZh ? "让我想想..." : "Hmm, let me think..."
    if (isRecording) return isZh ? "正在记录~" : "Taking notes~"
    if (mood === 'happy') return isZh ? "发现有趣的!" : "Found something!"
    if (mood === 'sleeping') return "Zzz..."

    // Style-specific idle messages
    switch (style) {
      case 'sprout': return isZh ? "记忆生长中~" : "Growing memories~"
      case 'neko': return "Nyaa~"
      case 'bobble': return isZh ? "在看着呢~" : "Watching~"
      default: return isZh ? "你好!" : "Hello!"
    }
  }

  // Get style-specific SVG
  const getSvg = () => {
    switch (style) {
      case 'sprout': return SproutSvg
      case 'neko': return NekoSvg
      case 'bobble': return BobbleSvg
      default: return SproutSvg
    }
  }

  return (
    <div
      className={`relative select-none ${interactive ? 'cursor-pointer' : ''} group ${className}`}
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      title={interactive ? t('pet.clickToChangeOutfit') : undefined}
      draggable={false}
      onDragStart={(e) => e.preventDefault()}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={style}
          initial={{ opacity: 0, scale: 0.8, y: 10, rotate: -10 }}
          animate={{
            opacity: 1,
            scale: 1,
            y: 0,
            rotate: 0,
            transition: { type: "spring", stiffness: 300, damping: 20 }
          }}
          exit={{ opacity: 0, scale: 0.8, y: -10, rotate: 10, transition: { duration: 0.15 } }}
          className={`${sizeClasses[size]} drop-shadow-md relative`}
        >
          {/* Status Indicator Light - green for recording (friendlier) */}
          {(isThinking || isRecording) && (
            <motion.div
              className={`absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-white/50 z-10 ${
                isThinking ? 'bg-blue-400' : 'bg-green-500'
              }`}
              animate={{
                opacity: [0.4, 1, 0.4],
                scale: [0.9, 1.1, 0.9]
              }}
              transition={{ repeat: Infinity, duration: isThinking ? 0.8 : 1.2 }}
            />
          )}

          {/* Sleeping ZZZ */}
          {mood === 'sleeping' && (
            <motion.div
              className="absolute -top-2 -right-2 text-xs font-bold text-blue-400/80"
              animate={{
                y: [0, -4, 0],
                opacity: [0.5, 1, 0.5]
              }}
              transition={{ repeat: Infinity, duration: 2 }}
            >
              💤
            </motion.div>
          )}

          {/* Happy sparkles */}
          {mood === 'happy' && (
            <>
              {[...Array(3)].map((_, i) => (
                <motion.div
                  key={i}
                  className="absolute text-yellow-400"
                  style={{
                    top: `${10 + i * 20}%`,
                    left: `${80 + (i % 2) * 10}%`,
                    fontSize: '8px'
                  }}
                  animate={{
                    y: [0, -8, 0],
                    opacity: [0, 1, 0],
                    scale: [0.5, 1, 0.5]
                  }}
                  transition={{
                    repeat: Infinity,
                    duration: 1,
                    delay: i * 0.3
                  }}
                >
                  ✦
                </motion.div>
              ))}
            </>
          )}

          {/* Floating Animation Container */}
          <motion.div
            animate={getAnimation()}
            className="w-full h-full flex items-center justify-center"
          >
            {/* Eye tracking overlay */}
            <motion.div
              className="absolute inset-0 z-20 pointer-events-none"
              animate={{
                x: eyePosition.x,
                y: eyePosition.y
              }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            />

            {/* Blink overlay */}
            <AnimatePresence>
              {blinkState && (
                <motion.div
                  initial={{ scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  exit={{ scaleY: 0 }}
                  className="absolute inset-[30%] bg-current rounded-full z-10 pointer-events-none opacity-80"
                  style={{ originY: 0.5 }}
                />
              )}
            </AnimatePresence>

            <img
              src={getSvg()}
              alt="Nemori"
              className="w-full h-full object-contain"
              draggable={false}
              onDragStart={(e) => e.preventDefault()}
              style={{
                imageRendering: 'pixelated',
                filter: isThinking
                  ? 'brightness(1.1) drop-shadow(0 0 6px rgba(59, 130, 246, 0.6))'
                  : isRecording
                  ? 'drop-shadow(0 0 4px rgba(34, 197, 94, 0.4))' // Green glow for recording
                  : mood === 'happy'
                  ? 'brightness(1.05) drop-shadow(0 0 4px rgba(250, 204, 21, 0.4))'
                  : 'none'
              }}
            />
          </motion.div>
        </motion.div>
      </AnimatePresence>

      {/* Speech Bubble - very high z-index to avoid being blocked */}
      {showStatus && (
        <motion.div
          initial={{ opacity: 0, y: 8, scale: 0.8 }}
          animate={{
            opacity: isHovered || isThinking || isRecording ? 1 : 0,
            y: isHovered || isThinking || isRecording ? 0 : 8,
            scale: isHovered || isThinking || isRecording ? 1 : 0.8
          }}
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 bg-background/95 backdrop-blur-sm border border-border rounded-xl shadow-lg whitespace-nowrap pointer-events-none"
          style={{ zIndex: 9999 }}
        >
          <p className="text-xs font-medium text-foreground">
            {getStatusMessage()}
          </p>
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-border" />
        </motion.div>
      )}
    </div>
  )
}
