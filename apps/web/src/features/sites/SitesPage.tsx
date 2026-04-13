import { useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { Site } from '../../types/models'
import { useSiteContext } from './SiteContext'

const initialForm = {
  name: '',
  site_type: 'office',
  timezone: 'Asia/Calcutta',
  description: '',
}

export function SitesPage() {
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState('')
  const [saveMessage, setSaveMessage] = useState('')
  const { sites, refreshSites, setSelectedSiteId } = useSiteContext()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaveMessage('')

    try {
      const createdSite = await apiRequest<Site>('/sites', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      await refreshSites(createdSite.id)
      setSelectedSiteId(createdSite.id)
      setForm(initialForm)
      setSaveMessage(`Created site ${createdSite.name}.`)
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : 'Unable to create site.',
      )
    }
  }

  async function handleDeleteSite(site: Site) {
    const shouldDelete = window.confirm(
      `Delete ${site.name}? This will remove its cameras, zones, rules, alerts, events, and people.`,
    )
    if (!shouldDelete) {
      return
    }

    setError('')
    setSaveMessage('')

    try {
      await apiRequest<void>(`/sites/${site.id}`, { method: 'DELETE' })
      await refreshSites()
      setSaveMessage(`Deleted site ${site.name}.`)
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : 'Unable to delete site.',
      )
    }
  }

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Create Site"
        subtitle="Creating a site also applies its default rules automatically."
      >
        <form className="stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Name</span>
            <input
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Mode</span>
            <select
              value={form.site_type}
              onChange={(event) =>
                setForm((current) => ({ ...current, site_type: event.target.value }))
              }
            >
              <option value="home">Home</option>
              <option value="office">Office</option>
              <option value="restaurant">Restaurant</option>
            </select>
          </label>
          <label className="field">
            <span>Timezone</span>
            <input
              value={form.timezone}
              onChange={(event) =>
                setForm((current) => ({ ...current, timezone: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              rows={3}
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  description: event.target.value,
                }))
              }
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          {saveMessage ? <p className="form-success">{saveMessage}</p> : null}
          <button className="primary-button" type="submit">
            Create site
          </button>
        </form>
      </Panel>

      <Panel
        title="Current Sites"
        subtitle="Each site acts as its own rulebook and monitoring surface."
      >
        {sites.length ? (
          <div className="list">
            {sites.map((site) => (
              <article key={site.id} className="list-row">
                <div>
                  <strong>{site.name}</strong>
                  <p>{site.description || 'No description yet.'}</p>
                </div>
                <div className="stack-sm align-end">
                  <span className="pill">{site.site_type}</span>
                  <small>{site.timezone}</small>
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => void handleDeleteSite(site)}
                  >
                    Delete site
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No sites yet. Create your first home, office, or restaurant site here." />
        )}
      </Panel>
    </div>
  )
}
