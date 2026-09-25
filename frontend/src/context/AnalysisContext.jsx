import { createContext, useCallback, useContext, useMemo, useState } from 'react'

import { analyzeArticle } from '../api/client'

const AnalysisContext = createContext(null)

const EMPTY_SUMMARY = {
  total_links: 0,
  total_missing: 0,
  total_one_way: 0,
  one_way_targets_checked: 0,
  one_way_truncated: false,
}

const initialState = {
  title: '',
  status: 'idle', // idle | loading | ready | error
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

    setState({ ...initialState, title: trimmed, status: 'loading' })
    try {
      const result = await analyzeArticle(trimmed)
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
      setState({
        ...initialState,
        title: trimmed,
        status: 'error',
        error: error.message,
      })
      return null
    }
  }, [])

  const reset = useCallback(() => setState(initialState), [])

  const value = useMemo(() => ({ ...state, run, reset }), [state, run, reset])

  return <AnalysisContext value={value}>{children}</AnalysisContext>
}

export function useAnalysis() {
  const context = useContext(AnalysisContext)
  if (!context) {
    throw new Error('useAnalysis must be used inside <AnalysisProvider>')
  }
  return context
}
