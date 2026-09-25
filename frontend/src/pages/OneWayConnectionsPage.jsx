import { OneWayConnectionsList } from '../components/ConnectionLists'
import ResultLayout from '../components/ResultLayout'
import { useAnalysis } from '../context/AnalysisContext'

export default function OneWayConnectionsPage() {
  const { status, oneWayConnections, summary } = useAnalysis()

  return (
    <ResultLayout loadingLabel="Checking which articles link back...">
      {status === 'ready' && (
        <OneWayConnectionsList
          connections={oneWayConnections}
          checkedCount={summary.one_way_targets_checked}
          truncated={summary.one_way_truncated}
        />
      )}
    </ResultLayout>
  )
}
