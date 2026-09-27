// Relative by default: the Vite dev server proxies /api to the FastAPI backend
// (see vite.config.js). Set VITE_API_BASE_URL to call a backend directly.
import { readAnalysisKey } from './apiKey'

const DEFAULT_BASE_URL = '/api'

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL
).replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  // Everything a caller passes has to reach fetch. This used to destructure only
  // `signal` and rebuild the init object from scratch, which silently discarded
  // `method` and `body`: analyzeArticle asked for POST and the browser sent GET, and
  // the backend answered 405 for every analysis. Forward the whole init instead.
  const { signal, ...init } = options
  // Sent on every call rather than the four gated ones. The backend ignores it on the
  // read routes, and a single place that can attach it cannot drift out of sync with the
  // list of routes that need it. The caller may already have set the header, hence the
  // spread order.
  const analysisKey = readAnalysisKey()
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(analysisKey ? { 'X-Api-Key': analysisKey } : {}),
        ...init.headers,
      },
      signal,
    })
  } catch (cause) {
    if (cause.name === 'AbortError') throw cause
    throw new ApiError(
      'Could not reach the backend. Is it running on port 8000?',
      0,
    )
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // Non JSON error body, keep the generic message.
    }
    throw new ApiError(detail, response.status)
  }

  return response.json()
}

function query(params) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  }
  return search.toString()
}

export const searchArticles = (q, limit = 10, options) =>
  request(`/articles/search?${query({ q, limit })}`, options)

export const findArticle = (q, options) =>
  request(`/articles/find?${query({ q })}`, options)

export const getArticle = (title, options) =>
  request(`/article?${query({ title })}`, options)

export const getArticleLinks = (title, options) =>
  request(`/article/links?${query({ title })}`, options)

export const checkArticlesExist = (titles, options) =>
  request(
    `/articles/resolve?${titles
      .map((title) => `titles=${encodeURIComponent(title)}`)
      .join('&')}`,
    options,
  )

export const analyzeArticle = (title, options) =>
  request('/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ title }),
    ...options,
  })

export const getMissingConnections = (title, options) =>
  request(`/connections/missing?${query({ title })}`, options)

export const getOneWayConnections = (title, options) =>
  request(`/connections/one-way?${query({ title })}`, options)

export const getConnectionMap = (title, options) =>
  request(`/connections/map?${query({ title })}`, options)
