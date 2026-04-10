import { useEffect, useMemo, useState } from 'react'

import { Panel } from '../../components/shared/Panel'
import { EmptyState } from '../../components/shared/EmptyState'
import { API_BASE_URL, apiRequest } from '../../lib/api/client'
import type { LiveMonitorStatus } from '../../types/models'

const API_ROOT = API_BASE_URL.replace(/\/api\/v1\/?$/, '')

function formatTimestamp(value: string | null) {
  if (!value) {
    return 'No frame captured yet'
  }

  return new Date(value).toLocaleString()
}

export function LivePage() {
  const [status, setStatus] = useState<LiveMonitorStatus | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let isMounted = true

    async function loadStatus() {
      try {
        const nextStatus = await apiRequest<LiveMonitorStatus>('/live/status')
        if (!isMounted) {
          return
        }
        setStatus(nextStatus)
        setError('')
      } catch (loadError) {
        if (!isMounted) {
          return
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load live monitor.')
      }
    }

    loadStatus()
    const intervalId = window.setInterval(loadStatus, 1000)

    return () => {
      isMounted = false
      window.clearInterval(intervalId)
    }
  }, [])

  const frameUrl = useMemo(() => {
    if (!status?.frame_url) {
      return ''
    }

    const cacheKey = encodeURIComponent(status.frame_updated_at ?? 'latest')
    return `${API_ROOT}${status.frame_url}?t=${cacheKey}`
  }, [status])

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Live Camera Monitor"
        subtitle="This is the easiest testing surface: make the camera show you or your room, then watch this preview refresh about once a second."
      >
        {error ? <p className="form-error">{error}</p> : null}
        {frameUrl ? (
          <div className="live-preview stack">
            <img className="live-preview__image" src={frameUrl} alt="Live worker preview" />
            <p className="eyebrow">Last frame: {formatTimestamp(status?.frame_updated_at ?? null)}</p>
          </div>
        ) : (
          <EmptyState message="No preview frame yet. Start the worker and point it at a webcam or DroidCam source." />
        )}
      </Panel>

      <Panel
        title="Live Status"
        subtitle="Use this to confirm the worker source before worrying about rules or alerts."
      >
        <div className="info-grid">
          <article className="info-tile">
            <small>Worker</small>
            <strong>{status?.worker_name || 'Not available'}</strong>
          </article>
          <article className="info-tile">
            <small>Source</small>
            <strong>
              {status ? `${status.camera_source_type} ${status.camera_source}` : 'Not available'}
            </strong>
          </article>
          <article className="info-tile">
            <small>Camera status</small>
            <strong>{status?.camera_connected ? 'Connected' : 'Disconnected'}</strong>
          </article>
          <article className="info-tile">
            <small>Last detection count</small>
            <strong>{status?.last_detection_count ?? 0}</strong>
          </article>
        </div>

        <div className="stack">
          <article className="list-row">
            <div>
              <strong>What the worker says</strong>
              <p>{status?.message || 'Waiting for worker status.'}</p>
            </div>
            <span className={status?.camera_connected ? 'pill pill--low' : 'pill pill--high'}>
              {status?.camera_connected ? 'ready' : 'needs camera'}
            </span>
          </article>

          <article className="list-row">
            <div>
              <strong>Latest labels</strong>
              <p>
                {status?.last_labels.length
                  ? status.last_labels.join(', ')
                  : 'No supported objects detected yet.'}
              </p>
            </div>
            <small>{status?.frame_count ?? 0} processed frames</small>
          </article>
        </div>

        <ol className="instruction-list">
          <li>Open DroidCam on your phone and make sure the phone camera is sending video to the laptop.</li>
          <li>Point the phone at yourself or a room entrance until the preview image here looks normal.</li>
          <li>Walk into frame and check whether the detection count rises above zero.</li>
          <li>Then open Alerts to see whether a saved alert was created.</li>
        </ol>
      </Panel>
    </div>
  )
}
