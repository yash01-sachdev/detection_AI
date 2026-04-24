export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const DEMO_NOTICE_EVENT = 'detection-ai:demo-restriction'

let authToken: string | null = null

export function setAuthToken(token: string | null) {
  authToken = token
}

type RequestOptions = RequestInit & {
  skipAuth?: boolean
}

async function extractError(response: Response) {
  try {
    const data = (await response.json()) as { detail?: string }
    return data.detail ?? 'Request failed.'
  } catch {
    return 'Request failed.'
  }
}

function announceDemoRestriction(message: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.dispatchEvent(
    new CustomEvent(DEMO_NOTICE_EVENT, {
      detail: { message },
    }),
  )
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()

  if (!authToken && !options.skipAuth) {
    const { getDemoApiResponse, getDemoRestrictionMessage } = await import('../demo')

    if (method === 'GET') {
      return getDemoApiResponse<T>(path)
    }

    const message = getDemoRestrictionMessage(path, method)
    announceDemoRestriction(message)
    throw new Error(message)
  }

  const headers = new Headers(options.headers)
  const isFormData = options.body instanceof FormData

  if (!headers.has('Content-Type') && options.body && !isFormData) {
    headers.set('Content-Type', 'application/json')
  }

  if (!options.skipAuth && authToken) {
    headers.set('Authorization', `Bearer ${authToken}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    throw new Error(await extractError(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
