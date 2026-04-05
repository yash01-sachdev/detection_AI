import type { Alert } from '../types/models'

function getStringDetail(alert: Alert, key: string) {
  const value = alert.details[key]
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

function getNumberDetail(alert: Alert, key: string) {
  const value = alert.details[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

export function getAlertZoneName(alert: Alert) {
  return getStringDetail(alert, 'zone_name')
}

export function getAlertSubject(alert: Alert) {
  return (
    getStringDetail(alert, 'employee_code') ||
    getStringDetail(alert, 'identity') ||
    getStringDetail(alert, 'subject_label')
  )
}

export function getAlertRepeatCount(alert: Alert) {
  const repeatCount = getNumberDetail(alert, 'repeat_count')
  return repeatCount > 0 ? repeatCount : 1
}

export function getAlertFirstSeen(alert: Alert) {
  return getStringDetail(alert, 'first_seen_at')
}

export function getAlertLastSeen(alert: Alert) {
  return getStringDetail(alert, 'last_seen_at')
}

export function formatAlertTimestamp(value: string | null | undefined) {
  if (!value) {
    return ''
  }

  return new Date(value).toLocaleString()
}
