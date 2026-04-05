export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

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

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  if (!headers.has('Content-Type') && options.body) {
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
