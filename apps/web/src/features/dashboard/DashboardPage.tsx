import { useEffect, useState } from 'react'

import { StatCard } from '../../components/dashboard/StatCard'
import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { DashboardOverview } from '../../types/models'

export function DashboardPage() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest<DashboardOverview>('/dashboard/overview')
      .then(setOverview)
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load overview.')
      })
  }, [])

  return (
    <div className="page-grid">
      <Panel
        title="Overview"
        subtitle="A quick view of the current V1 operating surface."
      >
        {error ? <p className="form-error">{error}</p> : null}
        <div className="stats-grid">
          {overview?.stats.map((stat) => (
            <StatCard key={stat.key} label={stat.label} value={stat.value} />
          ))}
        </div>
      </Panel>

      <Panel
        title="Recent Alerts"
        subtitle="Alerts created by rules or future worker ingest events."
      >
        {overview?.recent_alerts.length ? (
          <div className="list">
            {overview.recent_alerts.map((alert) => (
              <article key={alert.id} className="list-row">
                <div>
                  <strong>{alert.title}</strong>
                  <p>{alert.description || 'No description yet.'}</p>
                </div>
                <span className={`pill pill--${alert.severity}`}>{alert.severity}</span>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No alerts yet. Once the worker starts sending detections, alerts will appear here." />
        )}
      </Panel>
    </div>
  )
}

