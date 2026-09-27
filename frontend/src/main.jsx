import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { AnalysisProvider } from './context/AnalysisContext.jsx'
import './index.css'

// Outside the router on purpose: a boundary inside it would only cover one route, and the
// Layout that every route shares is exactly as likely to be what throws.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <AnalysisProvider>
          <App />
        </AnalysisProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
