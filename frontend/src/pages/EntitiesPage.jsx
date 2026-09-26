import EntitySections from '../components/EntitySections'
import ResultLayout from '../components/ResultLayout'
import { useAnalysis } from '../context/AnalysisContext'

export default function EntitiesPage() {
  const { status, article, links, summary } = useAnalysis()

  return (
    <ResultLayout loadingLabel="Identifying people and places...">
      {status === 'ready' && (
        <EntitySections links={links} sourceTitle={article?.title} summary={summary} />
      )}
    </ResultLayout>
  )
}
