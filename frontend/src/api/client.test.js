/**
 * The API client must send what the caller asked for.
 *
 * `request` used to destructure only `signal` and rebuild the fetch init object from
 * scratch, so `method` and `body` were dropped on the floor. `analyzeArticle` asked for a
 * POST with a JSON body and the browser sent a bare GET, and the backend answered 405 for
 * every analysis. Nothing caught it: the smoke test talks HTTP directly and bypasses this
 * file, and no frontend test had ever exercised a request.
 *
 * These assertions are on the outgoing request, because that is the layer where the
 * information was being lost.
 */

import { cleanup } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import {
  ApiError,
  analyzeArticle,
  findArticle,
  getConnectionMap,
  searchArticles,
} from './client.js'

afterEach(cleanup)

let calls

function stubFetch(response) {
  calls = []
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url, init })
    return response ?? { ok: true, status: 200, json: async () => ({ ok: true }) }
  }
}

function lastCall() {
  return calls[calls.length - 1]
}

describe('request shaping', () => {
  it('analyzeArticle sends POST with a JSON body', async () => {
    stubFetch()

    await analyzeArticle('Ada Lovelace')

    const { url, init } = lastCall()
    expect(url).toBe('/api/analyze')
    expect(init.method).toBe('POST')
    expect(init.body).toBe(JSON.stringify({ title: 'Ada Lovelace' }))
    expect(init.headers['Content-Type']).toBe('application/json')
  })

  it('a title needing escaping is encoded, not pasted raw', async () => {
    stubFetch()

    await analyzeArticle('Ada Lovelaces husband')

    expect(JSON.parse(lastCall().init.body).title).toBe('Ada Lovelaces husband')
  })

  it('read endpoints send GET and carry their parameters in the query string', async () => {
    stubFetch()

    await searchArticles('ada lovelace', 5)
    expect(lastCall().url).toBe('/api/articles/search?q=ada+lovelace&limit=5')
    expect(lastCall().init.method).toBeUndefined()
    expect(lastCall().init.body).toBeUndefined()

    await findArticle('bongaon')
    expect(lastCall().url).toBe('/api/articles/find?q=bongaon')

    await getConnectionMap('Chandni Chowk')
    expect(lastCall().url).toBe('/api/connections/map?title=Chandni+Chowk')
  })

  it('always asks for JSON', async () => {
    stubFetch()

    await searchArticles('ada')

    expect(lastCall().init.headers.Accept).toBe('application/json')
  })

  it('forwards the abort signal so a superseded request can be cancelled', async () => {
    stubFetch()
    const controller = new AbortController()

    await searchArticles('ada', 10, { signal: controller.signal })

    expect(lastCall().init.signal).toBe(controller.signal)
  })

  it('surfaces the backend detail message', async () => {
    stubFetch({
      ok: false,
      status: 404,
      json: async () => ({ detail: "Article 'Zzqx' does not exist on Wikipedia" }),
    })

    await expect(getConnectionMap('Zzqx')).rejects.toThrow(/does not exist/)
  })

  it('reports a non-JSON error body without losing the status', async () => {
    stubFetch({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('not json')
      },
    })

    await expect(getConnectionMap('Ada Lovelace')).rejects.toMatchObject({
      name: 'ApiError',
      status: 502,
    })
  })

  it('rethrows an abort instead of dressing it up as a network failure', async () => {
    globalThis.fetch = async () => {
      const abort = new Error('aborted')
      abort.name = 'AbortError'
      throw abort
    }

    await expect(searchArticles('ada')).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('turns an unreachable backend into a status-0 ApiError', async () => {
    globalThis.fetch = async () => {
      throw new TypeError('Failed to fetch')
    }

    const error = await searchArticles('ada').catch((cause) => cause)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(0)
  })
})
