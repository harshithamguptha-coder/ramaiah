/** Display and formatting helpers shared across pages. */

export function formatNumber(value, fallback = '—') {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback
  return Number(value).toLocaleString('en-US')
}

export function formatPercent(value, digits = 1, fallback = '—') {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback
  // Accept both 0-1 ratios and 0-100 values.
  const number = value <= 1 ? value * 100 : value
  return `${number.toFixed(digits)}%`
}

export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—'
  let size = bytes
  const units = ['B', 'KB', 'MB', 'GB']
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${index === 0 ? size : size.toFixed(1)} ${units[index]}`
}

export function formatSeconds(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (value < 1) return `${Math.round(value * 1000)} ms`
  if (value < 60) return `${value.toFixed(1)} sec`
  return `${(value / 60).toFixed(1)} min`
}

export function formatDateTime(iso) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function relativeTime(iso) {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const seconds = Math.round((Date.now() - then) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hr ago`
  return `${Math.round(hours / 24)} d ago`
}

/** Clamp a 0-100 score into range before it reaches a bar width or gauge. */
export function clampScore(value) {
  const number = Number(value)
  if (Number.isNaN(number)) return 0
  return Math.max(0, Math.min(100, number))
}

export function truncate(text, length = 120) {
  if (!text) return ''
  return text.length > length ? `${text.slice(0, length).trimEnd()}…` : text
}

export const APPROACH_TONE = {
  classical: 'classical',
  quantum: 'quantum',
  hybrid: 'hybrid',
}
