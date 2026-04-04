import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import type { Camera, Site } from '../../types/models'

const initialForm = {
  site_id: '',
  name: '',
  source_type: 'webcam',
  source_value: '0',
  is_enabled: true,
}

export function CamerasPage() {
  const [sites, setSites] = useState<Site[]>([])
  const [cameras, setCameras] = useState<Camera[]>([])
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([apiRequest<Site[]>('/sites'), apiRequest<Camera[]>('/cameras')])
      .then(([loadedSites, loadedCameras]) => {
        setSites(loadedSites)
        setCameras(loadedCameras)
        if (loadedSites.length) {
          setForm((current) => ({
            ...current,
            site_id: current.site_id || loadedSites[0].id,
          }))
        }
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load cameras.')
      })
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    try {
      const createdCamera = await apiRequest<Camera>('/cameras', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setCameras((current) => [createdCamera, ...current])
      setForm((current) => ({ ...initialForm, site_id: current.site_id || form.site_id }))
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : 'Unable to create camera.',
      )
    }
  }

  return (
    <div className="page-grid page-grid--two-up">
      <Panel
        title="Register Camera"
        subtitle="Use `0` for a laptop webcam or paste a DroidCam / RTSP URL for network streams."
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
            <span>Camera name</span>
            <input
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
            />
          </label>
          <label className="field">
            <span>Source type</span>
            <select
              value={form.source_type}
              onChange={(event) =>
                setForm((current) => ({ ...current, source_type: event.target.value }))
              }
            >
              <option value="webcam">Webcam</option>
              <option value="droidcam">DroidCam</option>
              <option value="rtsp">RTSP</option>
              <option value="uploaded_video">Uploaded Video</option>
            </select>
          </label>
          <label className="field">
            <span>Source value</span>
            <input
              value={form.source_value}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  source_value: event.target.value,
                }))
              }
            />
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button className="primary-button" disabled={!sites.length} type="submit">
            Add camera
          </button>
        </form>
      </Panel>

      <Panel
        title="Registered Cameras"
        subtitle="This is the control-plane list the worker will attach to later."
      >
        {cameras.length ? (
          <div className="list">
            {cameras.map((camera) => (
              <article key={camera.id} className="list-row">
                <div>
                  <strong>{camera.name}</strong>
                  <p>{camera.source_value}</p>
                </div>
                <div className="stack-sm align-end">
                  <span className="pill">{camera.source_type}</span>
                  <small>{camera.is_enabled ? 'enabled' : 'disabled'}</small>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState message="No cameras yet. Add your webcam or DroidCam source here first." />
        )}
      </Panel>
    </div>
  )
}
