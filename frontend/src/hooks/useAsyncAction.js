import { useCallback, useState } from "react"

/**
 * Wraps async handlers with loading guard and double-submit prevention.
 */
export default function useAsyncAction(action) {
  const [loading, setLoading] = useState(false)

  const run = useCallback(
    async (...args) => {
      if (loading) return
      setLoading(true)
      try {
        return await action(...args)
      } finally {
        setLoading(false)
      }
    },
    [action, loading],
  )

  return { run, loading }
}
