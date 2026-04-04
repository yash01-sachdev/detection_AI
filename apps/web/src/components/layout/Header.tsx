import { useLocation } from 'react-router-dom'

import { useAuth } from '../../features/auth/AuthContext'

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Operations Overview',
  '/modes': 'Site Modes',
  '/sites': 'Sites',
  '/cameras': 'Cameras',
  '/zones': 'Zones',
  '/rules': 'Rules',
  '/alerts': 'Alerts',
}

export function Header() {
  const location = useLocation()
  const { user, logout } = useAuth()

  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">Detection AI</p>
        <h1>{PAGE_TITLES[location.pathname] ?? 'Workspace'}</h1>
      </div>
      <div className="page-header__actions">
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

