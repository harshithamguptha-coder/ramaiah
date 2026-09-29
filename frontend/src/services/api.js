/**
 * Q-Compass API client.
 *
 * The single place the frontend talks to the backend. Every page goes through
 * this module — no component calls `fetch` directly — so the base URL, error
 * shape and timeout live in exactly one file.
 *
 * When VITE_API_URL is empty, requests go to the same origin and Vite proxies
 * /api to the FastAPI server (see vite.config.js).
 */

const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS || 60000)

/** Error thrown for any non-2xx response or network failure. */
export class ApiError extends Error {
  constructor(message, { status, detail, url } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.url = url
  }

  /** True when the failure is a connectivity problem rather than an API error. */
  get isNetworkError() {
    return this.status === 0
  }
}

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), options.timeout ?? TIMEOUT_MS)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
    })

    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`
      try {
        const body = await response.json()
        detail = body.detail || detail
      } catch {
        // Non-JSON error body — keep the generic message.
      }
      throw new ApiError(detail, { status: response.status, detail, url })
    }

    if (response.status === 204) return null
    return response.json()
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error.name === 'AbortError') {
      throw new ApiError('The request timed out. Is the backend running on port 8000?', {
        status: 0,
        url,
      })
    }
    throw new ApiError(
      'Could not reach the Q-Compass API. Make sure the backend is running.',
      { status: 0, url },
    )
  } finally {
    clearTimeout(timer)
  }
}

const json = (body) => ({ method: 'POST', body: JSON.stringify(body) })

export const api = {
  /** Liveness probe used by the topbar indicator. */
  health: () => request('/api/health', { timeout: 5000 }),

  /** Capability description (what is implemented vs. mocked). */
  meta: () => request('/api/meta', { timeout: 5000 }),

  /**
   * Upload a dataset.
   * @param {File} file
   * @param {string} problemDescription
   */
  uploadDataset: (file, problemDescription = '') => {
    const form = new FormData()
    form.append('file', file)
    if (problemDescription) form.append('problem_description', problemDescription)
    return request('/api/upload', { method: 'POST', body: form, timeout: 120000 })
  },

  /** Run the analysis pipeline for an existing upload. */
  startAnalysis: (analysisId, problemDescription) =>
    request('/api/analyze', json({ analysis_id: analysisId, problem_description: problemDescription })),

  /** Fetch the full analysis payload. */
  getAnalysis: (analysisId) => request(`/api/analysis/${analysisId}`),

  /** Recent analyses for the dashboard. */
  listAnalyses: (limit = 5) => request(`/api/analyses?limit=${limit}`),

  /** Pipeline stage statuses only. */
  getStatus: (analysisId) => request(`/api/analysis/${analysisId}/status`),

  /** Delete a stored analysis. */
  deleteAnalysis: (analysisId) =>
    request(`/api/analysis/${analysisId}`, { method: 'DELETE' }),

  /** Report download URL — the browser handles the file save. */
  reportDownloadUrl: (analysisId) => `${BASE_URL}/api/analysis/${analysisId}/report/download`,
}

export default api
