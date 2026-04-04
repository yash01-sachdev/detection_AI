import { useEffect, useState } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { Rule, Site } from '../../types/models'

export function RulesPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [rules, setRules] = useState<Rule[]>([])
  const [selectedSiteId, setSelectedSiteId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([apiRequest<Site[]>('/sites'), apiRequest<Rule[]>('/rules')])
      .then(([loadedSites, loadedRules]) => {
        setSites(loadedSites)
        setRules(loadedRules)
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load rules.')
      })
  }, [])

  const filteredRules = selectedSiteId
    ? rules.filter((rule) => rule.site_id === selectedSiteId)
    : rules

  return (
    <Panel
      title="Rules"
      subtitle="Default rules appear automatically when you create a site. Custom rules can be added through the API next."
    >
      <div className="toolbar">
        <label className="field field--inline">
          <span>Filter by site</span>
          <select
            value={selectedSiteId}
            onChange={(event) => setSelectedSiteId(event.target.value)}
          >
            <option value="">All sites</option>
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error ? <p className="form-error">{error}</p> : null}

      {filteredRules.length ? (
        <div className="list">
          {filteredRules.map((rule) => (
            <article key={rule.id} className="list-row">
              <div>
                <strong>{rule.name}</strong>
                <p>{rule.description || JSON.stringify(rule.conditions)}</p>
              </div>
              <div className="stack-sm align-end">
                <span className={`pill pill--${rule.severity}`}>{rule.severity}</span>
                <small>{rule.is_default ? 'default rule' : 'custom rule'}</small>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState message="No rules found yet. Creating a site should seed the default mode rules." />
      )}
    </Panel>
  )
}

