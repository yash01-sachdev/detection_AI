import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'

import { DemoModeBanner } from './DemoModeBanner'
import { Header } from './Header'
import { Sidebar } from './Sidebar'

export function AppShell({ children }: { children?: ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-shell__content">
        <Header />
        <DemoModeBanner />
        <main className="app-shell__main">{children ?? <Outlet />}</main>
      </div>
    </div>
  )
}
