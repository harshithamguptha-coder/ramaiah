/** Poll the backend health endpoint to drive the topbar status indicator. */

import { useEffect, useState } from 'react'
import api from '../services/api'

export function useApiHealth({ intervalMs = 30000 } = {}) {
  const [state, setState] = useState({ status: 'checking', service: null, version: null })

  useEffect(() => {
    let cancelled = false

    const check = async () => {
      try {
        const data = await api.health()
        if (!cancelled) {
          setState({ status: 'online', service: data.service, version: data.version })
        }
      } catch {
        if (!cancelled) setState({ status: 'offline', service: null, version: null })
      }
    }

    check()
    const timer = setInterval(check, intervalMs)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [intervalMs])

  return state
}

export default useApiHealth
