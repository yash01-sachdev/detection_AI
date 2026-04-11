import { useLocation } from 'react-router-dom'

import { useAuth } from '../../features/auth/AuthContext'
import { useSiteContext } from '../../features/sites/SiteContext'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Operations Overview',
  '/modes': 'Site Modes',
  '/sites': 'Sites',
  '/admins': 'Admins',
  '/cameras': 'Cameras',
  '/zones': 'Zones',
  '/rules': 'Rules',
  '/alerts': 'Alerts',
  '/employees': 'People',
}

export function Header() {
  const location = useLocation()
  const { user, logout } = useAuth()
  const { sites, selectedSiteId, setSelectedSiteId, isLoading } = useSiteContext()

  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">Detection AI</p>
        <h1>{PAGE_TITLES[location.pathname] ?? 'Workspace'}</h1>
      </div>
      <div className="page-header__actions">
        <label className="field field--inline">
          <span>Site</span>
          <select
            value={selectedSiteId}
            onChange={(event) => setSelectedSiteId(event.target.value)}
            disabled={isLoading || !sites.length}
          >
            {sites.length ? null : <option value="">{isLoading ? 'Loading sites...' : 'No sites yet'}</option>}
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name} ({site.site_type})
              </option>
            ))}
          </select>
        </label>
        <div className="user-chip">
          <span>{user?.full_name}</span>
          <small>{user?.role}</small>
        </div>
        <button className="ghost-button" onClick={logout} type="button">
          Log out
        </button>
      </div>
    </header>
  )
}
