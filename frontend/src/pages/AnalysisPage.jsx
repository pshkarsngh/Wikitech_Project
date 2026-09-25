import ArticleConnections from '../components/ArticleConnections'
import { MissingConnectionsList, OneWayConnectionsList } from '../components/ConnectionLists'
import ResultLayout from '../components/ResultLayout'
import { useAnalysis } from '../context/AnalysisContext'

export default function AnalysisPage() {
  const { status, article, links, missingConnections, oneWayConnections, summary } =
    useAnalysis()

  const ready = status === 'ready'

  return (
    <ResultLayout loadingLabel="Analyzing article...">
      {ready && (
        <MissingConnectionsList
          connections={missingConnections}
          totalLinks={summary.total_links}
          totalMissing={summary.total_missing}
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
