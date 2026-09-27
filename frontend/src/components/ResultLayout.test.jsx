/**
 * The summary tile must show the number a reader can count in the lists below it.
 *
 * `total_links` counts link targets as written in the wikitext, so an article that
 * links `Ghalib` and `Mirza Ghalib` reports two while only one article is at the
 * other end. The lists below the tile de-duplicate, so a tile showing the raw
 * count disagrees with its own lists — that is UAT-02's cosmetic half, D3.
 *
 * `ResultLayout` reads both `useArticleParam` and `useAnalysis`, so both are stubbed
 * rather than mounting the real provider. Nothing here renders the API response
 * through a real client; these are assertions about the two numbers the tile
 * chooses between.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ResultLayout from './ResultLayout.jsx'

afterEach(cleanup)

const ANALYSIS = {
  article: {
    page_id: 1,
    title: 'Chandni Chowk',
    url: 'https://en.wikipedia.org/wiki/Chandni_Chowk',
    exists: true,
  },
  generated_at: '2026-09-27T00:00:00Z',
  summary: {
    total_links: 0,
    total_articles: 0,
    total_missing: 0,
    total_one_way: 0,
    one_way_targets_checked: 0,
    one_way_truncated: false,
    one_way_incomplete: 0,
    links_truncated: false,
    described_links: 0,
    classify_truncated: false,
    total_people: 0,
    total_places: 0,
    missing_people: 0,
    missing_places: 0,
    aborted: false,
    abort_reason: null,
    entity_types_incomplete: false,
  },
  missing_connections: [],
  one_way_connections: [],
  links: [],
}

vi.mock('../context/AnalysisContext.jsx', () => ({
  useAnalysis: () => ANALYSIS,
}))

vi.mock('../hooks/useArticleParam.js', () => ({
  useArticleParam: () => ({
    title: 'Chandni Chowk',
    status: 'ready',
    setSearchParams: () => {},
  }),
}))

vi.mock('./SearchBar.jsx', () => ({ default: () => null }))
vi.mock('./ArticleSummary.jsx', () => ({ default: () => null }))

function withSummary(overrides) {
  ANALYSIS.summary = { ...ANALYSIS.summary, ...overrides }
}

function renderLayout() {
  return render(<ResultLayout />)
}

describe('the links tile', () => {
  it('shows the article count rather than the link-target count', () => {
    withSummary({ total_links: 444, total_articles: 440 })
    renderLayout()
    expect(screen.getByText('Articles linked')).toBeTruthy()
    expect(screen.getByText('440')).toBeTruthy()
  })

  it('reports the link-target count when it differs, so nothing is hidden', () => {
    withSummary({ total_links: 444, total_articles: 440 })
    renderLayout()
    expect(screen.getByText('444 link targets')).toBeTruthy()
  })

  it('does not print a redundant second number when the two agree', () => {
    withSummary({ total_links: 120, total_articles: 120 })
    renderLayout()
    // "120 link targets" against a tile already reading 120 is noise, and it
    // reads like an error.
    expect(screen.queryByText('120 link targets')).toBeNull()
    expect(screen.getByText('main-namespace links')).toBeTruthy()
  })

  it('says the count is a floor when the link budget truncated the article', () => {
    withSummary({ total_links: 500, total_articles: 500, links_truncated: true })
    renderLayout()
    expect(screen.getByText('at least this many, capped by budget')).toBeTruthy()
  })

  it('prefers the truncation warning over the redundant-count line', () => {
    withSummary({ total_links: 500, total_articles: 498, links_truncated: true })
    renderLayout()
    expect(screen.getByText('at least this many, capped by budget')).toBeTruthy()
    expect(screen.queryByText('500 link targets')).toBeNull()
  })
})

// The tile tests above are about which number is shown. These are about whether
// the reader is told the numbers are floors, which is the one thing a truncated
// analysis cannot leave to the payload.
describe('an analysis that was cut short', () => {
  it('warns above the tiles, not below them', () => {
    withSummary({ aborted: true, abort_reason: 'deadline', total_articles: 120 })
    renderLayout()
    const notice = screen.getByRole('status')
    // A warning under three big numbers is a warning nobody reads. This asserts
    // it exists on the page, not its position; the ordering is the CSS grid's
    // job and jsdom has no layout to measure.
    expect(notice).toBeTruthy()
    expect(screen.getByText('120')).toBeTruthy()
  })

  it('shows no warning for a complete analysis', () => {
    withSummary({ aborted: false, total_articles: 120 })
    renderLayout()
    expect(screen.queryByRole('status')).toBeNull()
  })
})
