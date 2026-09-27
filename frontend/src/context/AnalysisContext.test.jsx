/**
 * The analysis context must not show the result of a superseded request.
 *
 * Two analyses can be in flight at once: a user submits one article, changes their mind
 * and submits another before the first has answered. The responses then race, and the
 * slower earlier one lands last. Without a guard it overwrites the newer result, so the
 * screen shows one article while the URL says another — with no error and nothing on the
 * page to tell the user.
 *
 * `fetch` is stubbed rather than mocked at the module boundary, so the real API client is
 * exercised too, and each request is resolved by hand to force the race in both orders.
 */

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { AnalysisProvider, useAnalysis } from './AnalysisContext.jsx'

// Testing Library only registers its own cleanup when the runner exposes a global
// afterEach, and this suite imports its hooks instead.
afterEach(cleanup)

const ADA = 'Ada Lovelace'
const BONGAON = 'Bongaon'

function analysisPayload(title) {
  return {
    article: {
      page_id: 1,
      title,
      url: `https://en.wikipedia.org/wiki/${title.replace(/ /g, '_')}`,
      exists: true,
    },
    generated_at: '2026-09-27T00:00:00Z',
    summary: { total_links: 2, total_missing: 1, total_one_way: 0 },
    missing_connections: [],
    one_way_connections: [],
    links: [],
  }
}

function respond(title) {
  return { ok: true, status: 200, json: async () => analysisPayload(title) }
}

function deferred() {
  let resolve
  const promise = new Promise((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function Probe() {
  const { title, status, error, run } = useAnalysis()
  return (
    <div>
      <span data-testid="title">{title}</span>
      <span data-testid="status">{status}</span>
      <span data-testid="error">{error ?? ''}</span>
      <button type="button" onClick={() => run(ADA)}>
        analyze Ada Lovelace
      </button>
      <button type="button" onClick={() => run(BONGAON)}>
        analyze Bongaon
      </button>
      <button type="button" onClick={() => run('   ')}>
        analyze blank
      </button>
    </div>
  )
}

function renderProvider() {
  render(
    <AnalysisProvider>
      <Probe />
    </AnalysisProvider>,
  )
}

// One deferred per requested title, so a test decides the order responses arrive in.
let pending

beforeEach(() => {
  pending = new Map()
  globalThis.fetch = (_url, init = {}) => {
    const { title } = JSON.parse(init.body ?? '{}')
    const entry = deferred()
    pending.set(title, entry)
    return entry.promise
  }
})

async function start(title, button) {
  fireEvent.click(screen.getByRole('button', { name: button }))
  await waitFor(() => expect(pending.has(title)).toBe(true))
}

async function answer(title, payload) {
  await act(async () => {
    pending.get(title).resolve(payload)
  })
}

describe('AnalysisContext.run', () => {
  it('reports the analysed article when the only request wins', async () => {
    renderProvider()
    await start(ADA, 'analyze Ada Lovelace')
    await answer(ADA, respond(ADA))

    expect(screen.getByTestId('title').textContent).toBe(ADA)
    expect(screen.getByTestId('status').textContent).toBe('ready')
  })

  it('a superseded analysis that answers last does not overwrite the newer result', async () => {
    renderProvider()

    await start(ADA, 'analyze Ada Lovelace')
    await start(BONGAON, 'analyze Bongaon')

    // Bongaon answers first, then the older request finally returns.
    await answer(BONGAON, respond(BONGAON))
    expect(screen.getByTestId('title').textContent).toBe(BONGAON)

    await answer(ADA, respond(ADA))
    expect(screen.getByTestId('title').textContent).toBe(BONGAON)
    expect(screen.getByTestId('status').textContent).toBe('ready')
  })

  it('a superseded analysis that fails late does not replace the newer result', async () => {
    renderProvider()

    await start(ADA, 'analyze Ada Lovelace')
    await start(BONGAON, 'analyze Bongaon')
    await answer(BONGAON, respond(BONGAON))

    await answer(ADA, { ok: false, status: 502, json: async () => ({ detail: 'upstream down' }) })

    expect(screen.getByTestId('title').textContent).toBe(BONGAON)
    expect(screen.getByTestId('status').textContent).toBe('ready')
    expect(screen.getByTestId('error').textContent).toBe('')
  })

  it('reports the failure when the newest analysis is the one that fails', async () => {
    renderProvider()
    await start(ADA, 'analyze Ada Lovelace')
    await answer(ADA, { ok: false, status: 404, json: async () => ({ detail: 'no such article' }) })

    expect(screen.getByTestId('status').textContent).toBe('error')
    expect(screen.getByTestId('error').textContent).toBe('no such article')
  })

  it('rejects a blank title without calling the API', async () => {
    renderProvider()
    fireEvent.click(screen.getByRole('button', { name: 'analyze blank' }))

    expect(screen.getByTestId('status').textContent).toBe('error')
    expect(pending.size).toBe(0)
  })
})
