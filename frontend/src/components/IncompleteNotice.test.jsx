/**
 * An analysis that ran out of time must not read like a complete one.
 *
 * The API returns 200 with the article's real links and missing connections plus
 * `summary.aborted`, and the payload has nowhere else to say that the entity
 * types and the reverse-link check did not finish. The screen is the last place
 * it can be said, so these tests pin down that it is said: a notice above the
 * tiles, and no panel that turns "not finished" into "there is nothing here".
 *
 * The tempting failure is a page that renders cleanly and reads as a quiet
 * article with no people and no one-way links.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import IncompleteNotice from './IncompleteNotice.jsx'

afterEach(cleanup)

const COMPLETE = {
  aborted: false,
  abort_reason: null,
  entity_types_incomplete: false,
  one_way_truncated: false,
}

function summary(overrides) {
  return { ...COMPLETE, ...overrides }
}

function renderNotice(overrides) {
  return render(<IncompleteNotice summary={summary(overrides)} />)
}

describe('a complete analysis', () => {
  it('shows nothing at all', () => {
    const { container } = renderNotice({})
    // Not merely a styled nothing: a permanently present "everything is fine"
    // banner is noise that teaches people to ignore the banner.
    expect(container.textContent).toBe('')
  })

  it('stays quiet when only the name cap was hit', () => {
    // `classify_truncated` is a budget that ran short on purpose and is already
    // explained by the entity sections themselves. It is not a deadline.
    const { container } = renderNotice({ classify_truncated: true })
    expect(container.textContent).toBe('')
  })
})

describe('an analysis that ran out of time', () => {
  it('says the result is incomplete', () => {
    renderNotice({ aborted: true, abort_reason: 'deadline' })
    expect(screen.getByText('This analysis is incomplete')).toBeTruthy()
  })

  it('announces itself to assistive technology rather than sitting there', () => {
    renderNotice({ aborted: true, abort_reason: 'deadline' })
    // A status region, not an alert: nothing failed, and this appears on load
    // alongside the results it qualifies.
    expect(screen.getByRole('status')).toBeTruthy()
  })

  it('names the entity types as unfinished when that stage did not run', () => {
    renderNotice({
      aborted: true,
      abort_reason: 'deadline',
      entity_types_incomplete: true,
    })
    expect(screen.getByText(/people or places/)).toBeTruthy()
  })

  it('names the reverse links as unfinished when that stage did not run', () => {
    renderNotice({
      aborted: true,
      abort_reason: 'deadline',
      one_way_truncated: true,
    })
    expect(screen.getByText(/link back/)).toBeTruthy()
  })

  it('does not blame the missing connections, which are resolved first', () => {
    // The stage order is the whole reason a partial is worth returning. Saying
    // the links are incomplete too would make the notice sound worse than the
    // result is.
    renderNotice({
      aborted: true,
      abort_reason: 'deadline',
      entity_types_incomplete: true,
      one_way_truncated: true,
    })
    const body = screen.getByRole('status').textContent
    expect(body).toMatch(/links/)
    expect(body).toMatch(/complete/)
  })

  it('does not call the links complete when the crawl was itself capped', () => {
    // `links_truncated` is a different budget from the deadline, and it is hit
    // first. The tile already hints at it; claiming "complete" here would
    // contradict that hint on the same page.
    renderNotice({
      aborted: true,
      abort_reason: 'deadline',
      entity_types_incomplete: true,
      links_truncated: true,
    })
    const body = screen.getByRole('status').textContent
    expect(body).toMatch(/per-article limit/)
    expect(body).not.toMatch(/are complete/)
  })

  it('still calls the links complete when the crawl was not capped', () => {
    renderNotice({
      aborted: true,
      abort_reason: 'deadline',
      entity_types_incomplete: true,
      links_truncated: false,
    })
    expect(screen.getByRole('status').textContent).toMatch(/are complete/)
  })

  it('leaves out the unfinished list when nothing was cut short', () => {
    // A notice that says "Not finished:" and then names nothing reads as a bug.
    renderNotice({ aborted: true, abort_reason: 'deadline' })
    const body = screen.getByRole('status').textContent
    expect(body).not.toMatch(/Not finished/)
    expect(body).toMatch(/ran out of time/)
  })

  it('says the counts on the page are minimums, not findings', () => {
    renderNotice({ aborted: true, abort_reason: 'deadline' })
    expect(screen.getByText(/minimum, not a final/i)).toBeTruthy()
  })
})
