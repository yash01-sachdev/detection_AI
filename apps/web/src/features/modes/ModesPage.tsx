import { useEffect, useState } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { ModeTemplate } from '../../types/models'

export function ModesPage() {
  const [templates, setTemplates] = useState<ModeTemplate[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest<ModeTemplate[]>('/modes/templates')
      .then(setTemplates)
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load modes.')
      })
  }, [])

  return (
    <Panel
      title="Mode Templates"
      subtitle="The CV pipeline stays the same. Rules change based on the selected site mode."
    >
      {error ? <p className="form-error">{error}</p> : null}
      {templates.length ? (
        <div className="mode-grid">
          {templates.map((mode) => (
            <article key={mode.site_type} className="mode-card">
              <div className="mode-card__header">
                <h3>{mode.label}</h3>
                <span className="pill">{mode.site_type}</span>
              </div>
              <p>{mode.description}</p>
              <div className="stack-sm">
                {mode.rules.map((rule) => (
                  <div key={rule.template_key} className="rule-row">
                    <strong>{rule.name}</strong>
                    <small>{rule.description}</small>
                    <span className={`pill pill--${rule.severity}`}>{rule.severity}</span>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState message="Mode templates are not available yet." />
      )}
    </Panel>
  )
}

