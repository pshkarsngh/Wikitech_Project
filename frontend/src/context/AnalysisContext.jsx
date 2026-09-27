import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

import { analyzeArticle } from '../api/client'

const AnalysisContext = createContext(null)

const EMPTY_SUMMARY = {
  total_links: 0,
  total_articles: 0,
  total_missing: 0,
  total_one_way: 0,
  one_way_targets_checked: 0,
  one_way_truncated: false,
  one_way_incomplete: 0,
  links_truncated: false,
  described_links: 0,
  classify_truncated: false,
  total_people: 0,
  total_places: 0,
  missing_people: 0,
  missing_places: 0,
}

const initialState = {
  title: '',
  status: 'idle', // idle | loading | ready | error | unauthorized
  error: null,
  article: null,
  summary: EMPTY_SUMMARY,
  missingConnections: [],
  oneWayConnections: [],
  links: [],
  generatedAt: null,
}

export function AnalysisProvider({ children }) {
  const [state, setState] = useState(initialState)

  // Identifies the newest run. A response only owns the screen if it is still the
  // latest, because two analyses can be in flight at once: submit A, then B, and if B
  // answers first, A's slower response would otherwise overwrite B's result while the
  // URL still says B. The ref is stable, so `run` keeps its empty dependency list.
  const latestRunRef = useRef(0)

  // Kept free of `state` so the identity is stable across renders.
  const run = useCallback(async (title) => {
    const trimmed = String(title ?? '').trim()
    if (!trimmed) {
      setState({
        ...initialState,
        status: 'error',
        error: 'Enter the name of an article to analyze.',
      })
      return null
    }

    const runId = latestRunRef.current + 1
    latestRunRef.current = runId
    const isCurrent = () => runId === latestRunRef.current

    setState({ ...initialState, title: trimmed, status: 'loading' })
    try {
      const result = await analyzeArticle(trimmed)
      if (!isCurrent()) return null
      setState({
        title: result.article.title,
        status: 'ready',
        error: null,
        article: result.article,
        summary: result.summary,
        missingConnections: result.missing_connections,
        oneWayConnections: result.one_way_connections,
        links: result.links,
        generatedAt: result.generated_at,
      })
      return result.article.title
    } catch (error) {
      if (!isCurrent()) return null
      // 401 is its own state, not an error message. A wrong or absent key is not a
      // failure the visitor can retry their way out of, and the fix is a field to fill
      // in rather than a button - so it gets a prompt instead of the error panel.
      const unauthorized = error?.status === 401
      setState({
        ...initialState,
        title: trimmed,
        status: unauthorized ? 'unauthorized' : 'error',
        error: unauthorized ? null : error.message,
      })
      return null
    }
  }, [])

  const reset = useCallback(() => setState(initialState), [])

  const value = useMemo(
    () => ({ ...state, run, reset }),
    [state, run, reset],
  )

  return <AnalysisContext value={value}>{children}</AnalysisContext>
}

export function useAnalysis() {
  const context = useContext(AnalysisContext)
  if (!context) {
    throw new Error('useAnalysis must be used inside <AnalysisProvider>')
  }
  return context
}
