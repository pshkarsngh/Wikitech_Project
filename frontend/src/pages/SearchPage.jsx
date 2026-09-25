import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import SearchBar from '../components/SearchBar'
import { Card, EmptyState, ErrorMessage, Loading } from '../components/ui'
import { findArticle } from '../api/client'
import styles from './SearchPage.module.css'

const IDLE = { query: '', status: 'idle', article: null, error: null }

export default function SearchPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const query = (searchParams.get('title') ?? '').trim()

  const [state, setState] = useState(IDLE)
  const [notice, setNotice] = useState('')
  const [expanded, setExpanded] = useState(false)
  // Bumped to repeat a search whose name is already in the URL.
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!query) return undefined

    const controller = new AbortController()
    setState({ query, status: 'loading', article: null, error: null })

    findArticle(query, { signal: controller.signal })
      .then((article) => setState({ query, status: 'found', article, error: null }))
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setState({ query, status: 'error', article: null, error })
        }
      })

    return () => controller.abort()
  }, [query, attempt])

  function handleSearch(value) {
    const trimmed = value.trim()

    if (!trimmed) {
      // Nothing to look up: keep the last result rather than blanking the page.
      setNotice('Enter the name of a Wikipedia article to look up.')
      return
    }

    setNotice('')
    setExpanded(false)
    if (trimmed === query) {
      setAttempt((count) => count + 1)
    } else {
      setSearchParams({ title: trimmed })
    }
  }

  function handleAnalyze() {
    if (state.article) {
      navigate(`/analyze?title=${encodeURIComponent(state.article.title)}`)
    }
  }

  // Results only belong on screen once they are the ones for the current query.
  const loading = Boolean(query) && state.query !== query
  const article = !loading && state.query === query ? state.article : null
  const error = !loading && state.query === query ? state.error : null
  const notFound = error?.status === 404

  return (
    <div className={styles.page}>
      <h1 className={styles.heading}>Article search</h1>
      <p className={styles.description}>
        Look up a Wikipedia article to see its title, link and summary before analysing
        it.
      </p>

      <div className={styles.searchRow}>
        <SearchBar
          size="small"
          submitLabel="Search"
          initialValue={query}
          onAnalyze={handleSearch}
        />
      </div>

      {notice && (
        <p className={styles.notice} role="alert">
          {notice}
        </p>
      )}

      {loading && <Loading label="Searching Wikipedia..." />}

      {error && !notFound && (
        <>
          <ErrorMessage error={error} onRetry={() => setAttempt((count) => count + 1)} />
          {error.status === 0 && (
            <p className={styles.networkHint}>
              Start the backend with <code>uvicorn app.main:app --reload</code> from the{' '}
              <code>backend</code> directory.
            </p>
          )}
        </>
      )}

      {notFound && (
        <EmptyState
          title={`No article found for "${query}"`}
          description="Check the spelling, or pick one of the suggestions above."
        />
      )}

      {!query && !notice && (
        <EmptyState
          title="Nothing searched yet"
          description="Type an article name above to look it up on Wikipedia."
        />
      )}

      {article && (
        <Card
          title={article.title}
          subtitle={article.description ?? undefined}
          action={
            <button
              type="button"
              className={styles.analyzeButton}
              onClick={handleAnalyze}
            >
              Analyze Article
            </button>
          }
        >
          {article.url && (
            <p className={styles.url}>
              <span className={styles.urlLabel}>Article URL</span>
              <a
                className={styles.urlLink}
                href={article.url}
                target="_blank"
                rel="noreferrer noopener"
              >
                {article.url}
              </a>
            </p>
          )}

          {article.extract ? (
            <>
              <p className={expanded ? styles.extract : styles.extractClamped}>
                {article.extract}
              </p>
              <button
                type="button"
                className={styles.toggle}
                aria-expanded={expanded}
                onClick={() => setExpanded((value) => !value)}
              >
                {expanded ? 'Show less' : 'Show full extract'}
              </button>
            </>
          ) : (
            <p className={styles.noExtract}>
              Wikipedia has no summary text for this article.
            </p>
          )}

          <p className={styles.pageId}>
            Page ID <code>{article.page_id ?? 'unknown'}</code>
          </p>
        </Card>
      )}
    </div>
  )
}
