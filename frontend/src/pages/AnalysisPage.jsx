import ArticleConnections from '../components/ArticleConnections'
import { OneWayConnectionsList } from '../components/ConnectionLists'
import EntitySections from '../components/EntitySections'
import ResultLayout from '../components/ResultLayout'
import { useAnalysis } from '../context/AnalysisContext'

export default function AnalysisPage() {
  const { status, article, links, oneWayConnections, summary } = useAnalysis()

  const ready = status === 'ready'

  return (
    <ResultLayout loadingLabel="Analyzing article...">
      {ready && (
        <EntitySections
          links={links}
          sourceTitle={article?.title}
          summary={summary}
        />
      )}

      {ready && (
        <OneWayConnectionsList
          connections={oneWayConnections}
          checkedCount={summary.one_way_targets_checked}
          truncated={summary.one_way_truncated}
        />
      )}

      {ready && (
        <ArticleConnections links={links} sourceTitle={article?.title} />
      )}
    </ResultLayout>
  )
}
