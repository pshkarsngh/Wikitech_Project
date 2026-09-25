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

      {status === 'error' && (
        <ErrorMessage error={error} onRetry={title ? () => run(title) : undefined} />
      )}

      {isIdle && status !== 'loading' && status !== 'error' && (
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
              label="Links found"
              value={summary.total_links}
              hint="main-namespace links"
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
