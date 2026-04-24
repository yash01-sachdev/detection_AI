import { API_BASE_URL } from './api/client'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')
const DIRECT_MEDIA_PATTERN = /^(data:|blob:|https?:\/\/)/i

export function resolveMediaUrl(
  path: string | null | undefined,
  cacheKey?: string | null,
) {
  if (!path) {
    return ''
  }

  if (DIRECT_MEDIA_PATTERN.test(path)) {
    return path
  }

  if (!cacheKey) {
    return `${API_ROOT}${path}`
  }

  const separator = path.includes('?') ? '&' : '?'
  return `${API_ROOT}${path}${separator}t=${encodeURIComponent(cacheKey)}`
}
