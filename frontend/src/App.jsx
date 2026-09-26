import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import AnalysisPage from './pages/AnalysisPage'
import EntitiesPage from './pages/EntitiesPage'
import HomePage from './pages/HomePage'
import MissingConnectionsPage from './pages/MissingConnectionsPage'
import NotFoundPage from './pages/NotFoundPage'
import OneWayConnectionsPage from './pages/OneWayConnectionsPage'
import SearchPage from './pages/SearchPage'
import { Loading } from './components/ui'

// Cytoscape.js is only needed on the map page, so it loads on demand.
const ConnectionMapPage = lazy(() => import('./pages/ConnectionMapPage'))

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<Loading label="Loading connection map..." />}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/analyze" element={<AnalysisPage />} />
          <Route path="/people-and-places" element={<EntitiesPage />} />
          <Route path="/missing-connections" element={<MissingConnectionsPage />} />
          <Route path="/one-way-connections" element={<OneWayConnectionsPage />} />
          <Route path="/connection-map" element={<ConnectionMapPage />} />
          <Route path="/home" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </Layout>
  )
}
