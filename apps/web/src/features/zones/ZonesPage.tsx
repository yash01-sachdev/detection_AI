import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { API_BASE_URL, apiRequest } from '../../lib/api/client'
import type { LiveMonitorStatus, Site, Zone, ZonePoint } from '../../types/models'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

const initialForm = {
  site_id: '',
  name: '',
  zone_type: 'restricted',
  color: '#148A72',
  is_restricted: true,
  pointsText: '',
}

type ParsedPointsResult = {
  points: ZonePoint[]
  error: string
}

function serializePoints(points: ZonePoint[]) {
  return points.map((point) => `${Math.round(point.x)},${Math.round(point.y)}`).join(' | ')
}

function parsePoints(pointsText: string): ParsedPointsResult {
  if (!pointsText.trim()) {
    return { points: [], error: '' }
  }

  const parsedPoints: ZonePoint[] = []
  const pairs = pointsText
    .split('|')
    .map((value) => value.trim())
    .filter(Boolean)

  for (const pair of pairs) {
    const values = pair.split(',').map((value) => value.trim())
    if (values.length !== 2) {
      return { points: [], error: `Point "${pair}" must use "x,y" format.` }
    }

    const [xValue, yValue] = values.map(Number)
    if (!Number.isFinite(xValue) || !Number.isFinite(yValue)) {
      return { points: [], error: `Point "${pair}" must contain numbers only.` }
    }
    if (xValue < 0 || yValue < 0) {
      return { points: [], error: 'Point coordinates cannot be negative.' }
    }

    parsedPoints.push({ x: xValue, y: yValue })
  }

  return { points: parsedPoints, error: '' }
}

function buildFrameUrl(status: LiveMonitorStatus | null) {
  if (!status?.frame_url) {
    return ''
  }

  const cacheKey = encodeURIComponent(status.frame_updated_at ?? 'latest')
  return `${API_ROOT}${status.frame_url}?t=${cacheKey}`
}

function suggestRestriction(zoneType: string) {
  return zoneType === 'restricted' || zoneType === 'smoking_area'
}

export function ZonesPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [form, setForm] = useState(initialForm)
  const [status, setStatus] = useState<LiveMonitorStatus | null>(null)
  const [error, setError] = useState('')
  const [saveMessage, setSaveMessage] = useState('')
  const [deletingZoneId, setDeletingZoneId] = useState('')
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 })
  const imageRef = useRef<HTMLImageElement | null>(null)

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

  useEffect(() => {
    let isMounted = true

    async function loadStatus() {
      try {
        const nextStatus = await apiRequest<LiveMonitorStatus>('/live/status')
        if (!isMounted) {
          return
        }
        setStatus(nextStatus)
      } catch {
        if (!isMounted) {
          return
        }
        setStatus(null)
      }
    }

    loadStatus()
    const intervalId = window.setInterval(loadStatus, 2500)

    return () => {
      isMounted = false
      window.clearInterval(intervalId)
    }
  }, [])

  const frameUrl = useMemo(() => buildFrameUrl(status), [status])
  const parsedDraft = useMemo(() => parsePoints(form.pointsText), [form.pointsText])
  const currentSiteZones = useMemo(
    () => zones.filter((zone) => zone.site_id === form.site_id),
    [form.site_id, zones],
  )

  function updatePoints(points: ZonePoint[]) {
    setForm((current) => ({
      ...current,
      pointsText: serializePoints(points),
    }))
  }

  function handleZoneTypeChange(zoneType: string) {
    setForm((current) => ({
      ...current,
      zone_type: zoneType,
      is_restricted: suggestRestriction(zoneType),
    }))
  }

  function handlePreviewClick(event: MouseEvent<HTMLDivElement>) {
    if (!imageRef.current || !imageSize.width || !imageSize.height) {
      setError('Start the worker first so the latest frame is available for accurate zone drawing.')
      return
    }

    const rect = imageRef.current.getBoundingClientRect()
    if (!rect.width || !rect.height) {
      return
    }

    const x = Math.round((event.clientX - rect.left) * (imageSize.width / rect.width))
    const y = Math.round((event.clientY - rect.top) * (imageSize.height / rect.height))

    if (x < 0 || y < 0 || x > imageSize.width || y > imageSize.height) {
      return
    }

    const nextPoints = [...parsedDraft.points, { x, y }]
    updatePoints(nextPoints)
    setError('')
    setSaveMessage('')
  }

  function handleUndoPoint() {
    updatePoints(parsedDraft.points.slice(0, -1))
    setSaveMessage('')
  }

  function handleClearPoints() {
    updatePoints([])
    setSaveMessage('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSaveMessage('')

    if (parsedDraft.error) {
      setError(parsedDraft.error)
      return
    }

    if (parsedDraft.points.length < 3) {
      setError('A zone needs at least 3 points.')
      return
    }

    try {
      const createdZone = await apiRequest<Zone>('/zones', {
        method: 'POST',
        body: JSON.stringify({
          site_id: form.site_id,
          name: form.name,
          zone_type: form.zone_type,
          color: form.color,
          is_restricted: form.is_restricted,
          points: parsedDraft.points,
        }),
      })
      setZones((current) => [createdZone, ...current])
      setForm((current) => ({
        ...initialForm,
        site_id: current.site_id || form.site_id,
        zone_type: current.zone_type,
        color: current.color,
        is_restricted: current.is_restricted,
      }))
      setSaveMessage('Zone saved successfully.')
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to create zone.')
    }
  }

  async function handleDeleteZone(zone: Zone) {
    const confirmed = window.confirm(`Delete zone "${zone.name}"?`)
    if (!confirmed) {
      return
    }

    setError('')
    setSaveMessage('')
    setDeletingZoneId(zone.id)

    try {
      await apiRequest(`/zones/${zone.id}`, { method: 'DELETE' })
      setZones((current) => current.filter((item) => item.id !== zone.id))
      setSaveMessage(`Deleted zone "${zone.name}".`)
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Unable to delete zone.')
    } finally {
      setDeletingZoneId('')
    }
  }

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Create Zone"
        subtitle="Choose the site, then click the live frame to draw the zone exactly where the worker sees it."
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
              placeholder="Server room, gate, smoking area"
            />
          </label>

          <div className="zone-form-grid">
            <label className="field">
              <span>Zone type</span>
              <select
                value={form.zone_type}
                onChange={(event) => handleZoneTypeChange(event.target.value)}
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
              <span>Color</span>
              <input
                type="color"
                value={form.color}
                onChange={(event) =>
                  setForm((current) => ({ ...current, color: event.target.value }))
                }
              />
            </label>
          </div>

          <label className="field field--inline">
            <span>Restricted</span>
            <input
              type="checkbox"
              checked={form.is_restricted}
              onChange={(event) =>
                setForm((current) => ({ ...current, is_restricted: event.target.checked }))
              }
            />
          </label>

          <div className="zone-editor">
            <div className="zone-editor__toolbar">
              <p className="zone-editor__hint">
                Click the preview to place points in order. Use at least 3 points for a polygon.
              </p>
              <div className="zone-editor__actions">
                <button
                  className="ghost-button"
                  type="button"
                  onClick={handleUndoPoint}
                  disabled={!parsedDraft.points.length}
                >
                  Undo
                </button>
                <button
                  className="ghost-button"
                  type="button"
                  onClick={handleClearPoints}
                  disabled={!parsedDraft.points.length}
                >
                  Clear
                </button>
              </div>
            </div>

            <div
              className={`zone-editor__stage${frameUrl ? ' zone-editor__stage--interactive' : ''}`}
              onClick={handlePreviewClick}
              role="presentation"
            >
              {frameUrl ? (
                <>
                  <img
                    ref={imageRef}
                    className="zone-editor__image"
                    src={frameUrl}
                    alt="Latest live frame for zone drawing"
                    onLoad={(event) =>
                      setImageSize({
                        width: event.currentTarget.naturalWidth,
                        height: event.currentTarget.naturalHeight,
                      })
                    }
                  />
                  {imageSize.width && imageSize.height ? (
                    <svg
                      className="zone-editor__overlay"
                      viewBox={`0 0 ${imageSize.width} ${imageSize.height}`}
                      preserveAspectRatio="none"
                    >
                      {currentSiteZones.map((zone) => (
                        <polygon
                          key={zone.id}
                          points={zone.points.map((point) => `${point.x},${point.y}`).join(' ')}
                          fill={`${zone.color}22`}
                          stroke={zone.color}
                          strokeWidth="3"
                        />
                      ))}

                      {parsedDraft.points.length >= 2 ? (
                        <polyline
                          points={parsedDraft.points.map((point) => `${point.x},${point.y}`).join(' ')}
                          fill="none"
                          stroke="#e3a34d"
                          strokeWidth="3"
                          strokeDasharray="10 8"
                        />
                      ) : null}

                      {parsedDraft.points.length >= 3 ? (
                        <polygon
                          points={parsedDraft.points.map((point) => `${point.x},${point.y}`).join(' ')}
                          fill="rgba(227, 163, 77, 0.18)"
                          stroke="#e3a34d"
                          strokeWidth="3"
                        />
                      ) : null}

                      {parsedDraft.points.map((point, index) => (
                        <g key={`${point.x}-${point.y}-${index}`}>
                          <circle cx={point.x} cy={point.y} r="7" fill="#f4efe6" />
                          <circle cx={point.x} cy={point.y} r="4" fill="#1aa484" />
                        </g>
                      ))}
                    </svg>
                  ) : null}
                </>
              ) : (
                <div className="zone-editor__empty">
                  <strong>No live frame yet</strong>
                  <p>Start the worker and open the camera feed so you can draw zones on the actual scene.</p>
                </div>
              )}
            </div>

            <div className="zone-editor__meta">
              <small>
                Frame size: {imageSize.width && imageSize.height ? `${imageSize.width} x ${imageSize.height}` : 'not loaded'}
              </small>
              <small>{parsedDraft.points.length} draft point(s)</small>
            </div>
          </div>

          <label className="field">
            <span>Polygon points</span>
            <textarea
              rows={3}
              value={form.pointsText}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  pointsText: event.target.value,
                }))
              }
              placeholder="Click the preview or paste x,y pairs like 120,90 | 480,90 | 480,360"
            />
          </label>

          {parsedDraft.error ? <p className="form-error">{parsedDraft.error}</p> : null}
          {error ? <p className="form-error">{error}</p> : null}
          {saveMessage ? <p className="form-success">{saveMessage}</p> : null}

          <button className="primary-button" disabled={!sites.length} type="submit">
            Save zone
          </button>
        </form>
      </Panel>

      <Panel
        title="Configured Zones"
        subtitle="These polygons are already active for the selected site and are drawn over the same frame."
      >
        {currentSiteZones.length ? (
          <div className="list">
            {currentSiteZones.map((zone) => (
              <article key={zone.id} className="list-row list-row--top">
                <div>
                  <strong>{zone.name}</strong>
                  <p>{zone.points.length} point(s) saved for this polygon</p>
                  <small>{serializePoints(zone.points)}</small>
                </div>
                <div className="stack-sm align-end">
                  <span className="pill">{zone.zone_type}</span>
                  <small>{zone.is_restricted ? 'restricted' : 'open'}</small>
                  <button
                    className="ghost-button"
                    type="button"
                    onClick={() => handleDeleteZone(zone)}
                    disabled={deletingZoneId === zone.id}
                  >
                    {deletingZoneId === zone.id ? 'Deleting...' : 'Delete zone'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No zones yet for this site. Draw one directly on the live frame." />
        )}
      </Panel>
    </div>
  )
}
