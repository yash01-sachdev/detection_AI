import { useEffect, useMemo, useState } from 'react'

import { Panel } from '../../components/shared/Panel'
import { EmptyState } from '../../components/shared/EmptyState'
import { apiRequest } from '../../lib/api/client'
import { withSiteId } from '../../lib/api/siteScope'
import { resolveMediaUrl } from '../../lib/media'
import type { Camera, LiveMonitorStatus, WorkerAssignment, Zone } from '../../types/models'
import { useSiteContext } from '../sites/SiteContext'

const DEFAULT_WORKER_NAME = 'detection-ai-worker'

function formatTimestamp(value: string | null) {
  if (!value) {
    return 'No frame captured yet'
  }

  return new Date(value).toLocaleString()
}

export function LivePage() {
  const [status, setStatus] = useState<LiveMonitorStatus | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [assignments, setAssignments] = useState<WorkerAssignment[]>([])
  const [zones, setZones] = useState<Zone[]>([])
  const [activeCameraId, setActiveCameraId] = useState('')
  const [error, setError] = useState('')
  const [saveMessage, setSaveMessage] = useState('')
  const { selectedSite, selectedSiteId } = useSiteContext()

  useEffect(() => {
    if (!selectedSiteId) {
      setStatus(null)
      return
    }

    let isMounted = true

    async function loadStatus() {
      try {
        const nextStatus = await apiRequest<LiveMonitorStatus>(withSiteId('/live/status', selectedSiteId))
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
  }, [selectedSiteId])

  useEffect(() => {
    if (!selectedSiteId) {
      setCameras([])
      setAssignments([])
      setZones([])
      setActiveCameraId('')
      setSaveMessage('')
      return
    }

    Promise.all([
      apiRequest<Camera[]>(withSiteId('/cameras', selectedSiteId)),
      apiRequest<Zone[]>(withSiteId('/zones', selectedSiteId)),
      apiRequest<WorkerAssignment[]>('/worker-assignments'),
    ])
      .then(([loadedCameras, loadedZones, loadedAssignments]) => {
        setCameras(loadedCameras)
        setZones(loadedZones)
        setAssignments(loadedAssignments)
        const activeAssignment =
          loadedAssignments.find((assignment) => assignment.worker_name === DEFAULT_WORKER_NAME) ??
          loadedAssignments[0]
        const nextCameraId =
          activeAssignment?.site_id === selectedSiteId && activeAssignment.camera_id
            ? activeAssignment.camera_id
            : (loadedCameras[0]?.id ?? '')
        setActiveCameraId(nextCameraId)
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load worker assignment details.')
      })
  }, [selectedSiteId])

  const frameUrl = useMemo(() => {
    if (!status?.frame_url) {
      return ''
    }

    return resolveMediaUrl(status.frame_url, status.frame_updated_at ?? 'latest')
  }, [status])

  const activeWorkerName = useMemo(() => {
    if (status?.worker_name) {
      return status.worker_name
    }
    return assignments.find((assignment) => assignment.worker_name === DEFAULT_WORKER_NAME)?.worker_name
      ?? DEFAULT_WORKER_NAME
  }, [assignments, status])

  const zoneHint = useMemo(() => {
    if (!selectedSite) {
      return ''
    }
    if (!zones.length) {
      return 'No zones configured yet. Detections can appear in Live without creating alerts until you add zones.'
    }
    if (selectedSite.site_type === 'home' && !zones.some((zone) => zone.zone_type === 'entry')) {
      return 'Home alerts only fire inside an entry zone. Add a gate/entry polygon to trigger Unknown Person At Gate.'
    }
    return ''
  }, [selectedSite, zones])

  async function handleAssignWorker() {
    if (!selectedSiteId || !activeCameraId) {
      setError('Choose a site and camera first.')
      return
    }

    setError('')
    setSaveMessage('')

    try {
      const updatedAssignment = await apiRequest<WorkerAssignment>(`/worker-assignments/${activeWorkerName}`, {
        method: 'PUT',
        body: JSON.stringify({
          site_id: selectedSiteId,
          camera_id: activeCameraId,
          is_active: true,
        }),
      })
      setAssignments((current) => {
        const remaining = current.filter((assignment) => assignment.worker_name !== updatedAssignment.worker_name)
        return [updatedAssignment, ...remaining]
      })
      setSaveMessage(`Worker ${updatedAssignment.worker_name} is now assigned to ${selectedSite?.name || 'the selected site'}.`)
      const nextStatus = await apiRequest<LiveMonitorStatus>(withSiteId('/live/status', selectedSiteId))
      setStatus(nextStatus)
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to assign worker.')
    }
  }

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Live Camera Monitor"
        subtitle={
          selectedSite
            ? `This is the easiest testing surface for ${selectedSite.name}: make the camera show you or your room, then watch this preview refresh about once a second.`
            : 'Pick a site in the header to load the live camera monitor.'
        }
      >
        {error ? <p className="form-error">{error}</p> : null}
        {frameUrl ? (
          <div className="live-preview stack">
            <img className="live-preview__image" src={frameUrl} alt="Live worker preview" />
            <p className="eyebrow">Last frame: {formatTimestamp(status?.frame_updated_at ?? null)}</p>
          </div>
        ) : (
          <EmptyState message={selectedSite ? 'No preview frame yet. Start the worker and point it at the assigned source.' : 'Select a site to load the live preview.'} />
        )}
      </Panel>

      <Panel
        title="Live Status"
        subtitle="Use this to confirm the worker source before worrying about rules or alerts."
      >
        <article className="list-row list-row--top">
          <div>
            <strong>Worker Assignment</strong>
            <p>
              {selectedSite
                ? `Point ${activeWorkerName} at one camera from ${selectedSite.name}.`
                : 'Choose a site first, then assign the worker to one of its cameras.'}
            </p>
            <small>
              Current assignment: {status?.site_name || 'none'} / {status?.camera_name || 'no camera selected'}
            </small>
          </div>
          <div className="stack-sm align-end">
            <select value={activeCameraId} onChange={(event) => setActiveCameraId(event.target.value)} disabled={!cameras.length}>
              <option value="">{cameras.length ? 'Select camera' : 'No cameras for this site'}</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name} ({camera.source_type})
                </option>
              ))}
            </select>
            <button className="ghost-button" type="button" onClick={handleAssignWorker} disabled={!selectedSiteId || !activeCameraId}>
              Assign worker
            </button>
          </div>
        </article>

        {saveMessage ? <p className="form-success">{saveMessage}</p> : null}
        {zoneHint ? <p className="form-error">{zoneHint}</p> : null}

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
          <article className="info-tile">
            <small>Heartbeat</small>
            <strong>{formatTimestamp(status?.last_heartbeat_at ?? null)}</strong>
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
          <li>Choose the site you want to monitor from the header.</li>
          <li>Pick one camera for that site and press Assign worker.</li>
          <li>Point the camera at yourself or the scene until the preview looks normal.</li>
          <li>Then open Alerts to confirm the selected site's rules react correctly.</li>
        </ol>
      </Panel>
    </div>
  )
}
