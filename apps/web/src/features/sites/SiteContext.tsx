/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { apiRequest } from '../../lib/api/client'
import type { Site } from '../../types/models'
import { useAuth } from '../auth/AuthContext'

type SiteContextValue = {
  sites: Site[]
  selectedSiteId: string
  selectedSite: Site | null
  isLoading: boolean
  setSelectedSiteId: (siteId: string) => void
  refreshSites: (preferredSiteId?: string) => Promise<void>
}

const STORAGE_KEY = 'detection-ai-selected-site'
const SiteContext = createContext<SiteContextValue | undefined>(undefined)

export function SiteProvider({ children }: { children: ReactNode }) {
  const { isDemoMode, token, isLoading: isAuthLoading } = useAuth()
  const [sites, setSites] = useState<Site[]>([])
  const [selectedSiteId, setSelectedSiteIdState] = useState<string>(() => window.localStorage.getItem(STORAGE_KEY) ?? '')
  const [isLoading, setIsLoading] = useState(false)

  async function refreshSites(preferredSiteId?: string) {
    if (isAuthLoading) {
      return
    }

    setIsLoading(true)
    try {
      const loadedSites = await apiRequest<Site[]>('/sites')
      setSites(loadedSites)
      setSelectedSiteIdState((current) => {
        const candidate = preferredSiteId || current || window.localStorage.getItem(STORAGE_KEY) || loadedSites[0]?.id || ''
        return loadedSites.some((site) => site.id === candidate) ? candidate : (loadedSites[0]?.id ?? '')
      })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isAuthLoading) {
      return
    }

    void refreshSites().catch(() => undefined)
  }, [isAuthLoading, isDemoMode, token])

  useEffect(() => {
    if (selectedSiteId) {
      window.localStorage.setItem(STORAGE_KEY, selectedSiteId)
      return
    }
    window.localStorage.removeItem(STORAGE_KEY)
  }, [selectedSiteId])

  const value = useMemo<SiteContextValue>(
    () => ({
      sites,
      selectedSiteId,
      selectedSite: sites.find((site) => site.id === selectedSiteId) ?? null,
      isLoading,
      setSelectedSiteId: setSelectedSiteIdState,
      refreshSites,
    }),
    [isLoading, selectedSiteId, sites],
  )

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>
}

export function useSiteContext() {
  const context = useContext(SiteContext)
  if (!context) {
    throw new Error('useSiteContext must be used inside SiteProvider.')
  }
  return context
}
