/** Run an async loader and expose { data, loading, error, reload }. */

import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../services/api'

export function useAsync(loader, deps = [], { enabled = true, initialData = null } = {}) {
  const [data, setData] = useState(initialData)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState(null)

  const run = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await loader()
      setData(result)
      return result
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong.')
      return null
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    if (enabled) run()
  }, [run, enabled])

  return { data, loading, error, reload: run, setData }
}

export default useAsync
