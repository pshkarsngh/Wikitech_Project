import { useEffect, useState } from 'react'

import ConnectionMap from '../components/ConnectionMap'
import ResultLayout from '../components/ResultLayout'
import { Card, ErrorMessage, Loading } from '../components/ui'
import { getConnectionMap } from '../api/client'
import { useArticleParam } from '../hooks/useArticleParam'

export default function ConnectionMapPage() {
  const { title, status } = useArticleParam()
  const [result, setResult] = useState({ key: null, map: null, error: null })

  useEffect(() => {
    if (status !== 'ready' || !title) return undefined

    const controller = new AbortController()
    getConnectionMap(title, { signal: controller.signal })
      .then((map) => setResult({ key: title, map, error: null }))
      .catch((error) => {
        if (error.name !== 'AbortError') setResult({ key: title, map: null, error })
      })

    return () => controller.abort()
  }, [title, status])

  // Derived rather than stored, so there is no extra render before the fetch.
  const isCurrent = result.key === title
  const loading = status === 'ready' && !isCurrent

  return (
    <ResultLayout showSummary={false} loadingLabel="Building connection map...">
      {loading && <Loading label="Building connection map..." />}
      {isCurrent && result.error && <ErrorMessage error={result.error} />}
      {isCurrent && !result.error && result.map && (
        <Card
          title="Connection map"
          subtitle={`One hop out from "${result.map.article.title}". Arrow heads point at the linked article.`}
        >
          <ConnectionMap map={result.map} />
        </Card>
      )}
    </ResultLayout>
  )
}
