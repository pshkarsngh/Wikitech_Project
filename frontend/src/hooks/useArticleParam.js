import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useAnalysis } from '../context/AnalysisContext'

/**
 * Keeps `?title=` and the loaded analysis in sync.
 *
 * `title` is the resolved Wikipedia title once the analysis has finished, so a
 * redirect such as "Bongaon" is reflected back into the URL as "Bangaon".
 */
export function useArticleParam() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { title, status, run } = useAnalysis()
  const requestedTitle = searchParams.get('title') ?? ''

  // Guards against re-running for a title that is already being analyzed.
  const startedFor = useRef(null)

  useEffect(() => {
    if (!requestedTitle || requestedTitle === title) return
    if (startedFor.current === requestedTitle) return
    startedFor.current = requestedTitle

    let active = true
    run(requestedTitle).then((resolved) => {
      if (active && resolved && resolved !== requestedTitle) {
        setSearchParams({ title: resolved }, { replace: true })
      }
    })

    return () => {
      active = false
    }
  }, [requestedTitle, title, run, setSearchParams])

  return {
    title: title || requestedTitle,
    requestedTitle,
    status,
    setSearchParams,
  }
}
