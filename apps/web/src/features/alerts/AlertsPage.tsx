import { useEffect, useState } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import {
  formatAlertTimestamp,
  getAlertFirstSeen,
  getAlertLastSeen,
  getAlertRepeatCount,
  getAlertSubject,
  getAlertZoneName,
} from '../../lib/alertPresentation'
import { API_BASE_URL, apiRequest } from '../../lib/api/client'
import type { Alert } from '../../types/models'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    let isMounted = true

    async function loadAlerts() {
      try {
        const nextAlerts = await apiRequest<Alert[]>('/alerts')
        if (!isMounted) {
          return
        }
        setAlerts(nextAlerts)
        setError('')
      } catch (loadError) {
        if (!isMounted) {
          return
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load alerts.')
      }
    }

    loadAlerts()
    const intervalId = window.setInterval(loadAlerts, 4000)

    return () => {
      isMounted = false
      window.clearInterval(intervalId)
    }
  }, [])

  return (
    <Panel
      title="Alert History"
      subtitle="This feed shows the latest incidents, folds repeated sightings into one alert, and keeps the newest evidence on top."
    >
      {error ? <p className="form-error">{error}</p> : null}
      {alerts.length ? (
        <div className="list">
          {alerts.map((alert) => {
            const zoneName = getAlertZoneName(alert)
            const subject = getAlertSubject(alert)
            const repeatCount = getAlertRepeatCount(alert)
            const firstSeen = getAlertFirstSeen(alert)
            const lastSeen = getAlertLastSeen(alert)

            return (
              <article key={alert.id} className="list-row list-row--top">
                {alert.snapshot_path ? (
                  <img
                    className="alert-thumbnail"
                    src={`${API_ROOT}${alert.snapshot_path}`}
                    alt={alert.title}
                  />
                ) : null}
                <div className="alert-card__content">
                  <strong>{alert.title}</strong>
                  <p>{alert.description || 'No description provided.'}</p>
                  <div className="alert-meta">
                    {zoneName ? <span className="pill">{zoneName}</span> : null}
                    {subject ? <span className="pill">{subject}</span> : null}
                    {repeatCount > 1 ? <span className="pill pill--medium">Seen {repeatCount} times</span> : null}
                  </div>
                  <small>
                    Latest activity: {formatAlertTimestamp(lastSeen || alert.occurred_at)}
                    {firstSeen && firstSeen !== lastSeen
                      ? ` | First seen: ${formatAlertTimestamp(firstSeen)}`
                      : ''}
                  </small>
                </div>
                <div className="stack-sm align-end">
                  <span className={`pill pill--${alert.severity}`}>{alert.severity}</span>
                  <small>{alert.status}</small>
                </div>
              </article>
            )
          })}
        </div>
      ) : (
        <EmptyState message="No alerts recorded yet." />
      )}
    </Panel>
  )
}
