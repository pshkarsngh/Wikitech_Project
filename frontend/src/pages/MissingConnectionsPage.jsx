import { MissingConnectionsList } from '../components/ConnectionLists'
import ResultLayout from '../components/ResultLayout'
import { useAnalysis } from '../context/AnalysisContext'

export default function MissingConnectionsPage() {
  const { status, missingConnections, summary } = useAnalysis()

  return (
    <ResultLayout loadingLabel="Looking for missing connections...">
      {status === 'ready' && (
        <MissingConnectionsList
          connections={missingConnections}
          totalLinks={summary.total_links}
          totalMissing={summary.total_missing}
        />
      )}
    </ResultLayout>
  )
}
