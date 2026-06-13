const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api'
const AUTH_TOKEN_STORAGE_KEY = 'flowpilot_access_token'

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

type RequestOptions = {
  body?: unknown
}

type ApiErrorResponse = {
  code?: string
  message?: string
  details?: unknown[]
}

type ApiResponse<T> = {
  success: boolean
  message?: string
  data?: T
  error?: ApiErrorResponse
  detail?: unknown
}

class ApiRequestError extends Error {
  code?: string
  status: number
  data?: unknown

  constructor(message: string, status: number, code?: string, data?: unknown) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
    this.data = data
  }
}

function buildUrl(path: string) {
  const normalizedBaseUrl = API_BASE_URL.replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`

  return `${normalizedBaseUrl}${normalizedPath}`
}

async function parseJsonResponse(response: Response) {
  const text = await response.text()

  if (!text) {
    return null
  }

  try {
    return JSON.parse(text) as unknown
  } catch {
    throw new Error('API returned an invalid JSON response.')
  }
}

async function request<T>(
  method: HttpMethod,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const token = getStoredAccessToken()
  const headers: HeadersInit = {}

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(buildUrl(path), {
    method,
    headers,
    body:
      options.body instanceof FormData
        ? options.body
        : options.body
          ? JSON.stringify(options.body)
          : undefined,
  })

  const payload = (await parseJsonResponse(response)) as ApiResponse<T> | null

  if (!response.ok) {
    const detailMessage =
      typeof payload?.detail === 'string' ? payload.detail : undefined
    const message =
      payload?.error?.message ??
      payload?.message ??
      detailMessage ??
      `API request failed with status ${response.status}.`

    if (response.status === 401) {
      notifyAuthEvent('flowpilot:unauthorized', message)
    }
    if (response.status === 403) {
      notifyAuthEvent('flowpilot:forbidden', message)
    }

    throw new ApiRequestError(message, response.status, payload?.error?.code, payload?.data)
  }

  if (payload?.success === false) {
    throw new ApiRequestError(
      payload.error?.message ?? 'API request was not successful.',
      response.status,
      payload.error?.code,
      payload.data,
    )
  }

  return payload?.data as T
}

function get<T>(path: string) {
  return request<T>('GET', path)
}

function post<T>(path: string, body?: unknown) {
  return request<T>('POST', path, { body })
}

function patch<T>(path: string, body?: unknown) {
  return request<T>('PATCH', path, { body })
}

function put<T>(path: string, body?: unknown) {
  return request<T>('PUT', path, { body })
}

function remove<T>(path: string) {
  return request<T>('DELETE', path)
}

function getStoredAccessToken() {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
}

function setStoredAccessToken(token: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token)
}

function clearStoredAccessToken() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
}

function notifyAuthEvent(eventName: string, message: string) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(eventName, { detail: { message } }))
}

export {
  API_BASE_URL,
  AUTH_TOKEN_STORAGE_KEY,
  ApiRequestError,
  clearStoredAccessToken,
  get,
  getStoredAccessToken,
  patch,
  post,
  put,
  remove,
  setStoredAccessToken,
}
