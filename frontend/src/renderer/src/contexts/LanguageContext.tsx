/**
 * Language Context for managing app-wide language settings
 */

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import {
  Language,
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  translations,
  TranslationKey,
  isLanguageSupported
} from '../i18n'

const LANGUAGE_STORAGE_KEY = 'nemori-language'

interface LanguageContextType {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: TranslationKey) => string
  supportedLanguages: typeof SUPPORTED_LANGUAGES
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

interface LanguageProviderProps {
  children: ReactNode
}

export function LanguageProvider({ children }: LanguageProviderProps): JSX.Element {
  const [language, setLanguageState] = useState<Language>(() => {
    // Try to get language from localStorage first
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY)
    if (stored && isLanguageSupported(stored)) {
      return stored
    }
    return DEFAULT_LANGUAGE
  })

  // Load language from backend on mount
  useEffect(() => {
    const loadLanguageFromBackend = async (): Promise<void> => {
      try {
        const backendUrl = await window.api?.backend?.getUrl?.() || 'http://localhost:21978'
        const response = await fetch(`${backendUrl}/api/settings/language`)
        if (response.ok) {
          const data = await response.json()
          if (data.language && isLanguageSupported(data.language)) {
            setLanguageState(data.language)
            localStorage.setItem(LANGUAGE_STORAGE_KEY, data.language)
          }
        }
      } catch (error) {
        console.log('Failed to load language from backend, using local setting')
      }
    }
    loadLanguageFromBackend()
  }, [])

  // Set language and persist
  const setLanguage = useCallback(async (newLanguage: Language): Promise<void> => {
    if (!isLanguageSupported(newLanguage)) {
      console.error(`Unsupported language: ${newLanguage}`)
      return
    }

    setLanguageState(newLanguage)
    localStorage.setItem(LANGUAGE_STORAGE_KEY, newLanguage)

    // Also save to backend for prompt injection
    try {
      const backendUrl = await window.api?.backend?.getUrl?.() || 'http://localhost:21978'
      await fetch(`${backendUrl}/api/settings/language`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ language: newLanguage })
      })
    } catch (error) {
      console.error('Failed to save language to backend:', error)
    }
  }, [])

  // Translation function
  const t = useCallback(
    (key: TranslationKey): string => {
      const lang = translations[language] || translations[DEFAULT_LANGUAGE]
      return lang[key] || translations[DEFAULT_LANGUAGE][key] || key
    },
    [language]
  )

  const value: LanguageContextType = {
    language,
    setLanguage,
    t,
    supportedLanguages: SUPPORTED_LANGUAGES
  }

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext)
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider')
  }
  return context
}
