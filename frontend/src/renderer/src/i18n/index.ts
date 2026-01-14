/**
 * i18n configuration for Nemori
 *
 * Supports English (en) and Chinese (zh)
 */

import en from './locales/en'
import zh from './locales/zh'

export type Language = 'en' | 'zh'

export const SUPPORTED_LANGUAGES: Record<Language, string> = {
  en: 'English',
  zh: '中文'
}

export const DEFAULT_LANGUAGE: Language = 'en'

// All translations
export const translations = {
  en,
  zh
}

// Type for translation keys
export type TranslationKey = keyof typeof en

/**
 * Get a translation by key
 */
export function t(key: TranslationKey, language: Language = DEFAULT_LANGUAGE): string {
  const lang = translations[language] || translations[DEFAULT_LANGUAGE]
  return lang[key] || translations[DEFAULT_LANGUAGE][key] || key
}

/**
 * Check if a language is supported
 */
export function isLanguageSupported(language: string): language is Language {
  return language in SUPPORTED_LANGUAGES
}
