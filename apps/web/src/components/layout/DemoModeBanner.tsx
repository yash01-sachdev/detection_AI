import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../features/auth/AuthContext'
import { DEMO_NOTICE_EVENT } from '../../lib/api/client'

type DemoRestrictionEvent = CustomEvent<{ message?: string }>

export function DemoModeBanner() {
  const { isDemoMode } = useAuth()
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!isDemoMode) {
      setNotice('')
      return
    }

    function handleNotice(event: Event) {
      const customEvent = event as DemoRestrictionEvent
      setNotice(customEvent.detail?.message ?? 'Not allowed in demo mode.')
    }

    window.addEventListener(DEMO_NOTICE_EVENT, handleNotice)
    return () => {
      window.removeEventListener(DEMO_NOTICE_EVENT, handleNotice)
    }
  }, [isDemoMode])

  useEffect(() => {
    if (!notice) {
      return
    }

    const timeoutId = window.setTimeout(() => setNotice(''), 7000)
    return () => window.clearTimeout(timeoutId)
  }, [notice])

  if (!isDemoMode) {
    return null
  }

  return (
    <section className="demo-banner">
      <div className="demo-banner__header">
        <div>
          <p className="eyebrow">Demo Mode</p>
          <h2>Some actions are restricted</h2>
        </div>
        <Link className="ghost-button" to="/login">
          Admin sign in
        </Link>
      </div>

      <p className="demo-banner__copy">
        This demo stays read-only for security reasons. You can explore the UI, switch pages, inspect alerts, and understand the workflow end to end without changing live records.
      </p>

      <div className="demo-banner__grid">
        <article className="demo-banner__card">
          <strong>Restricted in demo mode</strong>
          <p>Create, delete, upload, and settings-changing actions stay blocked because they would modify real users, sites, cameras, rules, or stored face data.</p>
        </article>
        <article className="demo-banner__card">
          <strong>Why worker assignment is blocked here</strong>
          <p>The worker currently runs locally so it can reach webcam, DroidCam, and private RTSP feeds on the same machine or network without exposing private camera endpoints to the public cloud.</p>
        </article>
      </div>

      {notice ? <p className="demo-banner__notice">{notice}</p> : null}
    </section>
  )
}
