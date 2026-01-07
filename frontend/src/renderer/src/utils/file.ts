/**
 * Convert a local file path to a file:// URL
 * Supports both Windows and macOS/Linux paths
 */
export function pathToFileURL(filePath: string): string {
  if (!filePath) return ''

  // Already a file:// URL
  if (filePath.startsWith('file://')) {
    return filePath
  }

  // Windows path (e.g., C:\Users\...)
  if (/^[A-Za-z]:/.test(filePath)) {
    // Convert backslashes to forward slashes and add file:///
    return 'file:///' + filePath.replace(/\\/g, '/')
  }

  // Unix path (e.g., /Users/...)
  if (filePath.startsWith('/')) {
    return 'file://' + filePath
  }

  // Fallback: return as-is
  return filePath
}

/**
 * Format a date string for display
 */
export function formatDateDisplay(dateStr: string): string {
  const date = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const isToday = dateStr === today.toISOString().split('T')[0]
  const isYesterday = dateStr === yesterday.toISOString().split('T')[0]

  if (isToday) return '今天'
  if (isYesterday) return '昨天'

  return date.toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short'
  })
}

/**
 * Get today's date string in YYYY-MM-DD format
 */
export function getTodayDateStr(): string {
  return new Date().toISOString().split('T')[0]
}
