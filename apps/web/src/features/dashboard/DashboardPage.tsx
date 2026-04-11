import { useEffect, useState } from 'react'

import { StatCard } from '../../components/dashboard/StatCard'
import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import {
  formatAlertTimestamp,
  getAlertLastSeen,
  getAlertRepeatCount,
  getAlertSubject,
  getAlertZoneName,
} from '../../lib/alertPresentation'
import { apiRequest } from '../../lib/api/client'
import { withSiteId } from '../../lib/api/siteScope'
import type { DashboardOverview } from '../../types/models'
import { useSiteContext } from '../sites/SiteContext'

export function DashboardPage() {
  const [overview, setOverview] = useState<DashboardOverview | null>(null)
  const [error, setError] = useState('')
  const { selectedSite, selectedSiteId } = useSiteContext()

  useEffect(() => {
    if (!selectedSiteId) {
      setOverview(null)
      return
    }

    let isMounted = true

    async function loadOverview() {
      try {
        const nextOverview = await apiRequest<DashboardOverview>(withSiteId('/dashboard/overview', selectedSiteId))
        if (!isMounted) {
          return
        }
        setOverview(nextOverview)
        setError('')
      } catch (loadError) {
        if (!isMounted) {
          return
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load overview.')
      }
    }

    loadOverview()
    const intervalId = window.setInterval(loadOverview, 5000)

    return () => {
      isMounted = false
      window.clearInterval(intervalId)
    }
  }, [selectedSiteId])

  return (
    <div className="page-grid">
      <Panel
        title="Overview"
        subtitle={
          selectedSite
            ? `A quick view of the current V1 operating surface for ${selectedSite.name}.`
            : 'Pick a site in the header to view its operating surface.'
        }
      >
        {error ? <p className="form-error">{error}</p> : null}
        {overview ? (
          <div className="stats-grid">
            {overview.stats.map((stat) => (
              <StatCard key={stat.key} label={stat.label} value={stat.value} />
            ))}
          </div>
        ) : (
          <EmptyState message="Select a site to load the overview." />
        )}
      </Panel>

      <Panel
        title="Recent Alerts"
        subtitle="Recent incidents are grouped so repeated sightings stay readable instead of flooding the dashboard."
      >
        {overview?.recent_alerts.length ? (
          <div className="list">
            {overview.recent_alerts.map((alert) => {
              const zoneName = getAlertZoneName(alert)
              const subject = getAlertSubject(alert)
              const repeatCount = getAlertRepeatCount(alert)

              return (
                <article key={alert.id} className="list-row list-row--top">
                  <div className="alert-card__content">
                    <strong>{alert.title}</strong>
                    <p>{alert.description || 'No description yet.'}</p>
                    <div className="alert-meta">
                      {zoneName ? <span className="pill">{zoneName}</span> : null}
                      {subject ? <span className="pill">{subject}</span> : null}
                      {repeatCount > 1 ? <span className="pill pill--medium">Seen {repeatCount} times</span> : null}
                    </div>
                    <small>{formatAlertTimestamp(getAlertLastSeen(alert) || alert.occurred_at)}</small>
                  </div>
                  <span className={`pill pill--${alert.severity}`}>{alert.severity}</span>
                </article>
              )
            })}
          </div>
        ) : overview ? (
          <EmptyState message="No alerts yet for this site. Once the worker starts sending detections, alerts will appear here." />
        ) : (
          <EmptyState message="Select a site to load recent alerts." />
        )}
      </Panel>
    </div>
  )
}
