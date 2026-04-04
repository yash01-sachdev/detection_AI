/* eslint-disable react-refresh/only-export-components */
import {
  Navigate,
  Outlet,
  createBrowserRouter,
} from 'react-router-dom'

import { AppShell } from '../components/layout/AppShell'
import { AlertsPage } from '../features/alerts/AlertsPage'
import { CamerasPage } from '../features/cameras/CamerasPage'
import { DashboardPage } from '../features/dashboard/DashboardPage'
import { LoginPage } from '../features/auth/LoginPage'
import { ModesPage } from '../features/modes/ModesPage'
import { ProtectedRoute } from '../features/auth/ProtectedRoute'
import { RulesPage } from '../features/rules/RulesPage'
import { SitesPage } from '../features/sites/SitesPage'
import { ZonesPage } from '../features/zones/ZonesPage'

const ProtectedLayout = () => (
  <ProtectedRoute>
    <AppShell>
      <Outlet />
    </AppShell>
  </ProtectedRoute>
)

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'modes', element: <ModesPage /> },
      { path: 'sites', element: <SitesPage /> },
      { path: 'cameras', element: <CamerasPage /> },
      { path: 'zones', element: <ZonesPage /> },
      { path: 'rules', element: <RulesPage /> },
      { path: 'alerts', element: <AlertsPage /> },
    ],
  },
])
