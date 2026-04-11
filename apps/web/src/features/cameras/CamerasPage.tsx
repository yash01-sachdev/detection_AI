import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { EmptyState } from '../../components/shared/EmptyState'
import { Panel } from '../../components/shared/Panel'
import { apiRequest } from '../../lib/api/client'
import { withSiteId } from '../../lib/api/siteScope'
import type { Camera } from '../../types/models'
import { useSiteContext } from '../sites/SiteContext'

const initialForm = {
  site_id: '',
  name: '',
  source_type: 'webcam',
  source_value: '0',
  is_enabled: true,
}

export function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState('')
  const { selectedSite, selectedSiteId } = useSiteContext()

  useEffect(() => {
    if (!selectedSiteId) {
      setCameras([])
      setForm((current) => ({ ...current, site_id: '' }))
      return
    }

    apiRequest<Camera[]>(withSiteId('/cameras', selectedSiteId))
      .then((loadedCameras) => {
        setCameras(loadedCameras)
        setForm((current) => ({
          ...current,
          site_id: selectedSiteId,
        }))
      })
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : 'Unable to load cameras.')
      })
  }, [selectedSiteId])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')

    if (!selectedSiteId) {
      setError('Choose a site in the header first.')
      return
    }

    try {
      const createdCamera = await apiRequest<Camera>('/cameras', {
        method: 'POST',
        body: JSON.stringify({ ...form, site_id: selectedSiteId }),
      })
      setCameras((current) => [createdCamera, ...current])
      setForm((current) => ({ ...initialForm, site_id: current.site_id || selectedSiteId }))
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
        subtitle={
          selectedSite
            ? `Register a camera for ${selectedSite.name}. Use \`0\` for a laptop webcam or paste a stream URL for network sources.`
            : 'Choose a site in the header before registering a camera.'
        }
      >
        <form className="stack" onSubmit={handleSubmit}>
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
          <button className="primary-button" disabled={!selectedSiteId} type="submit">
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
          <EmptyState message={selectedSite ? 'No cameras yet for this site. Add one here first.' : 'Select a site to load its cameras.'} />
        )}
      </Panel>
    </div>
  )
}
