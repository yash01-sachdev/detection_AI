export function withSiteId(path: string, siteId: string) {
  const [pathname, existingQuery = ''] = path.split('?')
  const searchParams = new URLSearchParams(existingQuery)

  if (siteId) {
    searchParams.set('site_id', siteId)
  }

  const query = searchParams.toString()
  return query ? `${pathname}?${query}` : pathname
}
