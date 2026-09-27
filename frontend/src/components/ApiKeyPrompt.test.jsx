/**
 * The shared analysis key, end to end through the client and the prompt.
 *
 * The behaviour these cover is the whole point of A3: a deployment that sets
 * ANALYSIS_API_KEY must refuse an anonymous crawl, and a visitor holding the key must be
 * able to get in with one paste. The client is exercised against a stubbed `fetch` rather
 * than a real backend, because nothing here may touch the network.
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ApiKeyPrompt from './ApiKeyPrompt'
import { AnalysisProvider, useAnalysis } from '../context/AnalysisContext'
import { clearAnalysisKey, readAnalysisKey, writeAnalysisKey } from '../api/apiKey'
import { analyzeArticle } from '../api/client'

afterEach(cleanup)

beforeEach(() => {
  clearAnalysisKey()
  vi.restoreAllMocks()
})

function stubFetch(response) {
  const fetchMock = vi.fn(async () => response)
  globalThis.fetch = fetchMock
  return fetchMock
}

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

// Starts an analysis the way a real page does, so the tests drive the context through
// its public entry point instead of setting state directly.
function Trigger() {
  const { run } = useAnalysis()
  useEffect(() => {
    run('Ada Lovelace')
  }, [run])
  return null
}

describe('the analysis key store', () => {
  it('keeps the key for the tab and trims what it is given', () => {
    expect(writeAnalysisKey('  hunter2  ')).toBe('hunter2')
    expect(readAnalysisKey()).toBe('hunter2')
  })

  it('treats an empty key as no key rather than storing an empty string', () => {
    writeAnalysisKey('hunter2')
    expect(writeAnalysisKey('   ')).toBe('')
    expect(readAnalysisKey()).toBe('')
  })

  it('reports no key on a first visit', () => {
    expect(readAnalysisKey()).toBe('')
  })
})

describe('the client', () => {
  it('sends no key header when the visitor has not entered one', async () => {
    const fetchMock = stubFetch(jsonResponse(401, { detail: 'This analysis key is required.' }))

    await expect(analyzeArticle('Ada Lovelace')).rejects.toMatchObject({ status: 401 })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['X-Api-Key']).toBeUndefined()
  })

  it('sends the stored key once the visitor has entered one', async () => {
    const fetchMock = stubFetch(
      jsonResponse(200, { article: { title: 'Ada Lovelace' }, summary: {}, missing_connections: [], one_way_connections: [], links: [], generated_at: 'now' }),
    )
    writeAnalysisKey('hunter2')

    await analyzeArticle('Ada Lovelace')

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['X-Api-Key']).toBe('hunter2')
  })

  it('surfaces a 401 as a status the context can branch on', async () => {
    stubFetch(jsonResponse(401, { detail: 'That analysis key is not correct.' }))

    // The message alone would be indistinguishable from a 404 or a 502, and the prompt
    // is chosen by the status code rather than by parsing English.
    await expect(analyzeArticle('Ada Lovelace')).rejects.toMatchObject({ status: 401 })
  })
})

function Harness() {
  const { status } = useAnalysis()
  return <p data-testid="status">{status}</p>
}

describe('the context', () => {
  it('reports a refused analysis as unauthorized rather than as an error', async () => {
    stubFetch(jsonResponse(401, { detail: 'This analysis key is required.' }))

    render(
      <MemoryRouter>
        <AnalysisProvider>
          <Trigger />
          <Harness />
        </AnalysisProvider>
      </MemoryRouter>,
    )

    // The distinction the prompt depends on: 401 is a state, everything else is a
    // message in the error panel.
    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveProperty('textContent', 'unauthorized'),
    )
  })

  it('reports a failed article as an error, not as unauthorized', async () => {
    stubFetch(jsonResponse(404, { detail: 'No Wikipedia article with that title.' }))

    render(
      <MemoryRouter>
        <AnalysisProvider>
          <Trigger />
          <Harness />
        </AnalysisProvider>
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('status')).toHaveProperty('textContent', 'error'),
    )
  })
})

describe('the prompt', () => {
  it('appears in place of the error panel when the analysis is refused', async () => {
    stubFetch(jsonResponse(401, { detail: 'This analysis key is required.' }))

    render(
      <MemoryRouter>
        <AnalysisProvider>
          <Trigger />
          <ApiKeyPrompt />
        </AnalysisProvider>
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.getByText('This deployment needs an analysis key')).toBeTruthy(),
    )
  })

  it('will not submit an empty key', () => {
    stubFetch(jsonResponse(200, {}))
    const { unmount } = render(
      <MemoryRouter>
        <AnalysisProvider>
          <ApiKeyPrompt />
        </AnalysisProvider>
      </MemoryRouter>,
    )

    const button = screen.getByRole('button', { name: 'Unlock' })
    // No jest-dom in this project, so the property rather than `toBeDisabled()`.
    expect(button.disabled).toBe(true)
    unmount()
  })

  it('stores the typed key and retries the refused analysis', async () => {
    const fetchMock = stubFetch(jsonResponse(401, { detail: 'This analysis key is required.' }))

    render(
      <MemoryRouter>
        <AnalysisProvider>
          <Trigger />
          <ApiKeyPrompt />
        </AnalysisProvider>
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByRole('button', { name: 'Unlock' })).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Analysis key'), {
      target: { value: 'hunter2' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Unlock' }))

    await waitFor(() => expect(readAnalysisKey()).toBe('hunter2'))
    // The refused article is retried, because the analysis never happened and there is no
    // earlier result to fall back to.
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1))
    const [, retryInit] = fetchMock.mock.calls[1]
    expect(retryInit.headers['X-Api-Key']).toBe('hunter2')
  })

  it('masks the field, because the key is a shared secret', () => {
    stubFetch(jsonResponse(200, {}))
    render(
      <MemoryRouter>
        <AnalysisProvider>
          <ApiKeyPrompt />
        </AnalysisProvider>
      </MemoryRouter>,
    )

    expect(screen.getByLabelText('Analysis key')).toHaveProperty('type', 'password')
  })
})
