import { useEffect, useState } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { API_BASE_URL, apiRequest } from '../../lib/api/client'
import type { Alert } from '../../types/models'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest<Alert[]>('/alerts')
      .then(setAlerts)
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load alerts.')
      })
  }, [])

  return (
    <Panel
      title="Alert History"
      subtitle="This feed will become the main operator surface once the worker posts live events."
    >
      {error ? <p className="form-error">{error}</p> : null}
      {alerts.length ? (
        <div className="list">
          {alerts.map((alert) => (
            <article key={alert.id} className="list-row">
              {alert.snapshot_path ? (
                <img
                  className="alert-thumbnail"
                  src={`${API_ROOT}${alert.snapshot_path}`}
                  alt={alert.title}
                />
              ) : null}
              <div>
                <strong>{alert.title}</strong>
                <p>{alert.description || 'No description provided.'}</p>
                <small>{new Date(alert.occurred_at).toLocaleString()}</small>
              </div>
              <div className="stack-sm align-end">
                <span className={`pill pill--${alert.severity}`}>{alert.severity}</span>
                <small>{alert.status}</small>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState message="No alerts recorded yet." />
      )}
    </Panel>
  )
}
