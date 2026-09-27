/**
 * An empty one-way list means two different things, and the reader has to be
 * able to tell them apart.
 *
 * "Every target links back" is a finding about an article, and it is the whole
 * point of this panel. "Nothing was checked" is an absence of one, and an
 * analysis that stops on its deadline produces exactly that while looking, in the
 * payload, like the finding. This is the last place the difference can be made.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { OneWayConnectionsList } from './ConnectionLists.jsx'

afterEach(cleanup)

const CONNECTION = {
  target_title: 'Charles Babbage',
  target_url: 'https://en.wikipedia.org/wiki/Charles_Babbage',
}

function renderList({ connections = [], checkedCount = 0, truncated = false, incompleteCount = 0 } = {}) {
  return render(
    <OneWayConnectionsList
      connections={connections}
      checkedCount={checkedCount}
      truncated={truncated}
      incompleteCount={incompleteCount}
    />,
  )
}

describe('targets that were checked', () => {
  it('reports the finding when they all link back', () => {
    renderList({ connections: [], checkedCount: 25 })
    expect(screen.getByText('No one-way connections found')).toBeTruthy()
  })

  it('says how many were checked', () => {
    renderList({ connections: [], checkedCount: 25 })
    expect(screen.getByText(/25 targets checked/)).toBeTruthy()
  })

  it('lists a one-way connection it did find', () => {
    renderList({ connections: [CONNECTION], checkedCount: 25 })
    expect(screen.getByText('Charles Babbage ↗')).toBeTruthy()
  })
})

describe('targets that were never checked', () => {
  it('does not report a finding', () => {
    // An analysis that stopped before the reverse-link check reports zero
    // checked targets. Reading that as "none are one-way" is the false negative.
    renderList({ connections: [], checkedCount: 0, truncated: true })
    expect(screen.queryByText('No one-way connections found')).toBeNull()
  })

  it('says the check did not happen', () => {
    renderList({ connections: [], checkedCount: 0, truncated: true })
    expect(screen.getByText('No targets were checked')).toBeTruthy()
  })

  it('does not claim the checked count either', () => {
    renderList({ connections: [], checkedCount: 0, truncated: true })
    expect(screen.queryByText(/targets checked/)).toBeNull()
  })
})
