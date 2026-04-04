/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react'
import type { ReactNode } from 'react'

import { apiRequest, setAuthToken } from '../../lib/api/client'
import type { User } from '../../types/models'

type AuthContextValue = {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)
const STORAGE_KEY = 'detection-ai-token'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    window.localStorage.getItem(STORAGE_KEY),
  )
  const [user, setUser] = useState<User | null>(null)
  const isLoading = Boolean(token) && user === null

  useEffect(() => {
    setAuthToken(token)

    if (!token) {
      return
    }

    let isMounted = true

    apiRequest<User>('/auth/me')
      .then((currentUser) => {
        if (isMounted) {
          setUser(currentUser)
        }
      })
      .catch(() => {
        if (isMounted) {
          window.localStorage.removeItem(STORAGE_KEY)
          setToken(null)
          setUser(null)
        }
      })

    return () => {
      isMounted = false
    }
  }, [token])

  async function login(email: string, password: string) {
    const response = await apiRequest<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      skipAuth: true,
    })

    window.localStorage.setItem(STORAGE_KEY, response.access_token)
    setToken(response.access_token)
  }

  function logout() {
    window.localStorage.removeItem(STORAGE_KEY)
    setToken(null)
    setUser(null)
  }

  const value = {
    user,
    token,
    isLoading,
    login,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider.')
  }
  return context
}
