import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Overview' },
  { to: '/live', label: 'Live' },
  { to: '/modes', label: 'Modes' },
  { to: '/sites', label: 'Sites' },
  { to: '/admins', label: 'Admins' },
  { to: '/employees', label: 'People' },
  { to: '/cameras', label: 'Cameras' },
  { to: '/zones', label: 'Zones' },
  { to: '/rules', label: 'Rules' },
  { to: '/alerts', label: 'Alerts' },
]

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__badge">DA</div>
        <div>
          <strong>Detection AI</strong>
          <p>V1 foundation</p>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              isActive ? 'sidebar__link sidebar__link--active' : 'sidebar__link'
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar__footer">
        <p>Camera sources</p>
        <small>Webcam, DroidCam, RTSP-ready</small>
      </div>
    </aside>
  )
}
