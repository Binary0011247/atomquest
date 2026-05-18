import { useEffect } from "react"

const BASE = "AtomQuest"

export default function usePageTitle(title) {
  useEffect(() => {
    const prev = document.title
    document.title = title ? `${title} — ${BASE}` : `${BASE} | Goal Portal`
    return () => {
      document.title = prev
    }
  }, [title])
}
