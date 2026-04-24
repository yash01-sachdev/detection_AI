import type { ReactNode } from 'react'

import { useAuth } from './AuthContext'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading, logout } = useAuth()

  if (isLoading) {
    return <div className="screen-center">Loading workspace...</div>
  }

  if (user && user.role !== 'admin') {
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
