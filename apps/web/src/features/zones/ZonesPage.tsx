import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { Site, Zone, ZonePoint } from '../../types/models'

const initialForm = {
  site_id: '',
  name: '',
  zone_type: 'restricted',
  color: '#148A72',
  is_restricted: true,
  pointsText: '0,0 | 100,0 | 100,100 | 0,100',
}

function parsePoints(pointsText: string): ZonePoint[] {
  return pointsText
    .split('|')
    .map((pair) => pair.trim())
    .filter(Boolean)
    .map((pair) => {
      const [x, y] = pair.split(',').map((value) => Number(value.trim()))
      return { x, y }
    })
}

export function ZonesPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([apiRequest<Site[]>('/sites'), apiRequest<Zone[]>('/zones')])
      .then(([loadedSites, loadedZones]) => {
        setSites(loadedSites)
        setZones(loadedZones)
        if (loadedSites.length) {
          setForm((current) => ({
            ...current,
            site_id: current.site_id || loadedSites[0].id,
          }))
        }
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load zones.')
      })
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    try {
      const createdZone = await apiRequest<Zone>('/zones', {
        method: 'POST',
        body: JSON.stringify({
          site_id: form.site_id,
          name: form.name,
          zone_type: form.zone_type,
          color: form.color,
          is_restricted: form.is_restricted,
          points: parsePoints(form.pointsText),
        }),
      })
      setZones((current) => [createdZone, ...current])
      setForm((current) => ({ ...initialForm, site_id: current.site_id || form.site_id }))
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : 'Unable to create zone.',
      )
    }
  }

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Create Zone"
        subtitle="Polygon coordinates are stored now so the worker can later use them for rule evaluation."
      >
        <form className="stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Site</span>
            <select
              value={form.site_id}
              onChange={(event) =>
                setForm((current) => ({ ...current, site_id: event.target.value }))
              }
            >
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Zone name</span>
            <input
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Zone type</span>
            <select
              value={form.zone_type}
              onChange={(event) =>
                setForm((current) => ({ ...current, zone_type: event.target.value }))
              }
            >
              <option value="entry">Entry</option>
              <option value="restricted">Restricted</option>
              <option value="desk">Desk</option>
              <option value="smoking_area">Smoking Area</option>
              <option value="work_area">Work Area</option>
              <option value="general">General</option>
            </select>
          </label>
          <label className="field">
            <span>Polygon points</span>
            <input
              value={form.pointsText}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  pointsText: event.target.value,
                }))
              }
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-button" disabled={!sites.length} type="submit">
            Create zone
          </button>
        </form>
      </Panel>

      <Panel title="Configured Zones" subtitle="Restricted and operational areas by site.">
        {zones.length ? (
          <div className="list">
            {zones.map((zone) => (
              <article key={zone.id} className="list-row">
                <div>
                  <strong>{zone.name}</strong>
                  <p>{zone.points.length} polygon points saved</p>
                </div>
                <div className="stack-sm align-end">
                  <span className="pill">{zone.zone_type}</span>
                  <small>{zone.is_restricted ? 'restricted' : 'open'}</small>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No zones yet. Add gate, desk, smoking area, or restricted zones here." />
        )}
      </Panel>
    </div>
  )
}
