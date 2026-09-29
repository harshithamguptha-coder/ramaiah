/**
 * Global analysis state.
 *
 * Holds the active analysis id and the full payload fetched from the API so
 * that navigating between pipeline pages does not re-request the same data.
 * The payload is the single source of truth — no page invents analysis values.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import api, { ApiError } from '../services/api'

const AnalysisContext = createContext(null)

const STORAGE_KEY = 'q-compass:analysis-id'

export function AnalysisProvider({ children }) {
  const [analysisId, setAnalysisId] = useState(() => localStorage.getItem(STORAGE_KEY))
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Persist the active run so a page refresh keeps the user in context.
  useEffect(() => {
    if (analysisId) localStorage.setItem(STORAGE_KEY, analysisId)
    else localStorage.removeItem(STORAGE_KEY)
  }, [analysisId])

  const loadAnalysis = useCallback(async (id, { silent = false } = {}) => {
    if (!id) return null
    if (!silent) setLoading(true)
    setError(null)
    try {
      const payload = await api.getAnalysis(id)
      setAnalysis(payload)
      return payload
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load the analysis.')
      // A stale id (e.g. backend restarted) must not trap the user.
      if (err.status === 404) {
        setAnalysisId(null)
        setAnalysis(null)
      }
      return null
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  // Re-fetch whenever the active id changes (or on mount after a refresh).
  useEffect(() => {
    if (analysisId) loadAnalysis(analysisId)
  }, [analysisId, loadAnalysis])

  const upload = useCallback(async (file, problemDescription) => {
    const result = await api.uploadDataset(file, problemDescription)
    setAnalysisId(result.analysis_id)
    setAnalysis({ ...result, status: 'uploaded' })
    return result
  }, [])

  const startAnalysis = useCallback(async (problemDescription) => {
    if (!analysisId) throw new Error('No analysis id available.')
    setLoading(true)
    setError(null)
    try {
      const payload = await api.startAnalysis(analysisId, problemDescription)
      setAnalysis(payload)
      return payload
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Analysis failed to start.')
      throw err
    } finally {
      setLoading(false)
    }
  }, [analysisId])

  const reset = useCallback(() => {
    setAnalysisId(null)
    setAnalysis(null)
    setError(null)
  }, [])

  const value = useMemo(
    () => ({
      analysisId,
      analysis,
      dataset: analysis?.dataset ?? null,
      problem: analysis?.problem ?? null,
      classical: analysis?.classical_analysis ?? null,
      quantum: analysis?.quantum_analysis ?? null,
      comparison: analysis?.comparison ?? null,
      recommendation: analysis?.recommendation ?? null,
      report: analysis?.report ?? null,
      pipeline: analysis?.pipeline ?? [],
      isComplete: analysis?.status === 'completed',
      hasDataset: Boolean(analysis?.dataset?.file_name),
      loading,
      error,
      upload,
      startAnalysis,
      loadAnalysis,
      reset,
      setAnalysisId,
    }),
    [analysisId, analysis, loading, error, upload, startAnalysis, loadAnalysis, reset],
  )

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}

export function useAnalysisContext() {
  const context = useContext(AnalysisContext)
  if (!context) {
    throw new Error('useAnalysisContext must be used inside <AnalysisProvider>.')
  }
  return context
}

export default AnalysisProvider
