import { useMemo } from 'react'

import ApiKeyPrompt from './ApiKeyPrompt'
import ArticleSummary from './ArticleSummary'
import SearchBar from './SearchBar'
import { ErrorMessage, EmptyState, Loading, StatCard } from './ui'
import { useAnalysis } from '../context/AnalysisContext'
import { useArticleParam } from '../hooks/useArticleParam'
import styles from './ResultLayout.module.css'

export default function ResultLayout({ children, showSummary = true, loadingLabel }) {
  const { title, status, setSearchParams } = useArticleParam()
  const { error, article, summary, generatedAt, run } = useAnalysis()

  const isIdle = !title || status === 'idle'

  // The two counts differ only when the article links one redirect under more
  // than one name, so the raw figure is only worth the line when it is not
  // redundant. Showing both always would read as "440 articles / 444 links" on
  // pages where they are the same number, which looks like an error.
  const linksHint = useMemo(() => {
    if (summary.links_truncated) return 'at least this many, capped by budget'
    if (summary.total_links !== summary.total_articles) {
      return `${summary.total_links} link targets`
    }
    return 'main-namespace links'
  }, [summary.total_links, summary.total_articles, summary.links_truncated])

  return (
    <div>
      <div className={styles.searchRow}>
        <SearchBar
          size="small"
          initialValue={title}
          disabled={status === 'loading'}
          onAnalyze={(next) => setSearchParams({ title: next })}
        />
      </div>

      {status === 'loading' && <Loading label={loadingLabel} />}

      {status === 'unauthorized' && <ApiKeyPrompt />}

      {status === 'error' && (
        <ErrorMessage error={error} onRetry={title ? () => run(title) : undefined} />
      )}

      {isIdle && status !== 'loading' && status !== 'error' && status !== 'unauthorized' && (
        <EmptyState
          title="No article selected"
          description="Search for an article above, or start from the home page, to see its connections."
        />
      )}

      {status === 'ready' && article && (
        <>
          {showSummary && <ArticleSummary article={article} generatedAt={generatedAt} />}

          <div className={styles.stats}>
            <StatCard
              label="Articles linked"
              value={summary.total_articles}
              hint={linksHint}
              tone="links"
            />
            <StatCard
              label="Missing connections"
              value={summary.total_missing}
              hint="no article of their own"
              tone="missing"
            />
            <StatCard
              label="One-way connections"
              value={summary.total_one_way}
              hint={
                summary.one_way_targets_checked
                  ? `${summary.one_way_targets_checked} targets checked`
                  : 'no targets checked'
              }
              tone="oneway"
            />
          </div>

          {children}
        </>
      )}
    </div>
  )
}
