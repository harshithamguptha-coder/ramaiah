/**
 * Global analysis state - the single owner of the active analysis id.
 *
 * The payload is the single source of truth: no page invents analysis values.
 *
 * ## Why the id is held in a ref as well as state
 *
 * The active id decides which analysis every stage page shows, so a *stale* id
 * is the worst possible bug in this app: the pages either render the previous
 * run or nothing at all. Three things used to let a stale id through:
 *
 * 1. `useState(() => localStorage.getItem(KEY))` adopted whatever id the last
 *    session left behind, and the effect below immediately fetched it. After a
 *    backend restart that id no longer exists, producing
 *    `GET /api/analysis/an_OLDID -> 404`.
 * 2. The 404 handler cleared `analysisId`/`analysis` **without checking the
 *    request sequence**, so a late 404 from that stale request wiped the
 *    brand-new id and payload created by an upload that had already finished.
 * 3. `upload()` neither invalidated in-flight requests nor cleared the previous
 *    id, so the old fetch stayed live across the new upload.
 *
 * `analysisIdRef` is the authoritative value: callbacks read it instead of
 * closing over state, so they can never act on a stale id, and every response is
 * sequence-checked before it is allowed to write state.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import api, { ApiError } from '../services/api'

const AnalysisContext = createContext(null)

const STORAGE_KEY = 'q-compass:analysis-id'

/** True once the pipeline has produced every stage block. */
function isCompletePayload(payload) {
  return Boolean(
    payload &&
      payload.dataset &&
      payload.problem &&
      payload.classical_analysis &&
      payload.quantum_analysis &&
      payload.comparison &&
      payload.recommendation &&
      payload.report,
  )
}

/** Temporary id-flow tracing. Remove this helper to silence it. */
function trace(label, value) {
   
  console.log(`[Q-Compass] ${label}:`, value)
}

export function AnalysisProvider({ children }) {
  // Authoritative current id. State mirrors it for rendering only.
  const analysisIdRef = useRef(null)
  const [analysisId, setAnalysisIdState] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [stageProgress, setStageProgress] = useState(null)

  // Monotonic counter: only the newest request may write state.
  const requestSeq = useRef(0)

  /** The only way the current id changes. */
  const setCurrentId = useCallback((id) => {
    analysisIdRef.current = id
    setAnalysisIdState(id)
  }, [])

  /** Discard everything belonging to a previous run. */
  const invalidate = useCallback(() => {
    requestSeq.current += 1
    setCurrentId(null)
    setAnalysis(null)
    setStageProgress(null)
  }, [setCurrentId])

  // Persist the active run so a refresh can resume it.
  useEffect(() => {
    if (analysisId) {
      localStorage.setItem(STORAGE_KEY, analysisId)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }, [analysisId])

  const accept = useCallback((payload, seq) => {
    // Ignore a response from a superseded request.
    if (seq !== undefined && seq !== requestSeq.current) return false
    // Never let a partial record replace a complete one.
    setAnalysis((previous) => {
      if (isCompletePayload(previous) && !isCompletePayload(payload)) return previous
      return payload
    })
    return true
  }, [])

  const loadAnalysis = useCallback(
    async (id, { silent = false } = {}) => {
      if (!id) return null
      const seq = ++requestSeq.current
      trace('FETCHING ANALYSIS ID', id)
      if (!silent) setLoading(true)
      try {
        const payload = await api.getAnalysis(id)
        if (!accept(payload, seq)) return null
        setError(null)
        return payload
      } catch (err) {
        // Only the newest request may react. A late failure from a superseded
        // request must never clear state that has since been created.
        if (seq !== requestSeq.current) return null
        if (err.status === 404) {
          // The saved run no longer exists (e.g. the backend restarted). Reset
          // silently: this is not an error the user caused, and it must not
          // disturb a newer analysis that is already loaded.
          trace('STALE SESSION DISCARDED', id)
          setCurrentId(null)
          setAnalysis(null)
          return null
        }
        setError(err instanceof ApiError ? err.message : 'Failed to load the analysis.')
        return null
      } finally {
        if (seq === requestSeq.current && !silent) setLoading(false)
      }
    },
    [accept, setCurrentId],
  )

  // Resume a saved run on mount. The persisted id is only a *hint*: if it is
  // gone, `loadAnalysis` discards it above without surfacing an error.
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      trace('RESUMING SAVED ANALYSIS ID', stored)
      setCurrentId(stored)
      loadAnalysis(stored, { silent: true })
    }
    // Mount-only: a new id is always loaded explicitly by upload/startAnalysis.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const upload = useCallback(
    async (file, problemDescription, targetColumn) => {
      // Drop the previous run *before* the request goes out, so no fetch for the
      // old id can still be in flight once the new one is created.
      invalidate()
      setError(null)

      const result = await api.uploadDataset(file, problemDescription, targetColumn)
      trace('UPLOAD ANALYSIS ID', result.analysis_id)

      setAnalysis({ ...result, status: 'uploaded' })
      setCurrentId(result.analysis_id)
      return result
    },
    [invalidate, setCurrentId],
  )

  const startAnalysis = useCallback(
    async (problemDescription, targetColumn, explicitId) => {
      // Read the id from the ref, never from a closure - a closure can still be
      // a render behind if the upload and the click land in the same tick.
      const id = explicitId || analysisIdRef.current
      if (!id) throw new Error('No analysis id available.')

      const seq = ++requestSeq.current
      setLoading(true)
      setError(null)
      setStageProgress({ message: 'Analyzing dataset…' })
      try {
        const payload = await api.startAnalysis(id, problemDescription, targetColumn)
        trace('ANALYZE REQUEST ID', id)
        trace('ANALYZE RESPONSE ID', payload.analysis_id)

        if (seq !== requestSeq.current) return payload

        // A full pipeline result always wins, whatever arrived before it. The
        // response *is* the analysis, so the id can never drift from the data.
        setAnalysis(payload)
        setCurrentId(payload.analysis_id)
        setStageProgress(null)
        return payload
      } catch (err) {
        if (seq === requestSeq.current) {
          setStageProgress(null)
          setError(err instanceof ApiError ? err.message : 'Analysis failed to start.')
        }
        throw err
      } finally {
        if (seq === requestSeq.current) setLoading(false)
      }
    },
    [setCurrentId],
  )

  const reset = useCallback(() => {
    invalidate()
    setError(null)
  }, [invalidate])

  const value = useMemo(() => {
    const pipeline = analysis?.pipeline ?? []
    return {
      analysisId,
      analysis,
      dataset: analysis?.dataset ?? null,
      problem: analysis?.problem ?? null,
      classical: analysis?.classical_analysis ?? null,
      quantum: analysis?.quantum_analysis ?? null,
      comparison: analysis?.comparison ?? null,
      recommendation: analysis?.recommendation ?? null,
      report: analysis?.report ?? null,
      pipeline,
      warnings: analysis?.warnings ?? [],
      // "Complete" means every block is actually present, not just that the
      // payload claims status=completed.
      isComplete: isCompletePayload(analysis) || analysis?.status === 'completed',
      hasStages: isCompletePayload(analysis),
      hasDataset: Boolean(analysis?.dataset?.file_name),
      completedStages: pipeline.filter((s) => s.status === 'completed').length,
      loading,
      error,
      stageProgress,
      upload,
      startAnalysis,
      loadAnalysis,
      reset,
      setAnalysisId: setCurrentId,
    }
  }, [analysisId, analysis, loading, error, stageProgress, upload, startAnalysis, loadAnalysis, reset, setCurrentId])

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
