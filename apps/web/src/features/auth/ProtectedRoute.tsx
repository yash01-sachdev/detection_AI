import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from './AuthContext'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <div className="screen-center">Loading workspace...</div>
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (user.role !== 'admin') {
    return (
      <div className="screen-center stack">
        <strong>Administrator access is required.</strong>
        <button className="ghost-button" onClick={logout} type="button">
          Log out
        </button>
      </div>
    )
  }

  return <>{children}</>
}
