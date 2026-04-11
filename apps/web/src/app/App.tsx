import { RouterProvider } from 'react-router-dom'

import { AuthProvider } from '../features/auth/AuthContext'
import { SiteProvider } from '../features/sites/SiteContext'
import { router } from './router'

function App() {
  return (
    <AuthProvider>
      <SiteProvider>
        <RouterProvider router={router} />
      </SiteProvider>
    </AuthProvider>
  )
}

export default App
