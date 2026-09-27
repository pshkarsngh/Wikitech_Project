/**
 * A section that was never finished must not claim it found nothing.
 *
 * The distinction is between "there is nothing here" and "we stopped looking",
 * and it is invisible in a payload: an aborted analysis sends the same empty list
 * as a clean one. The panels are therefore the last place the difference can be
 * made, and this file is what stops a future edit from making the page quietly
 * wrong again.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import EntitySections from './EntitySections.jsx'

afterEach(cleanup)

// One person that exists, so the non-empty branch is exercised too: an unfinished
// stage must not blank out a section that did produce real entities.
const LINKS = [
  {
    title: 'Ada Lovelace',
    exists: true,
    url: 'https://en.wikipedia.org/wiki/Ada_Lovelace',
    entity_type: 'person',
    source_title: 'Chandni Chowk',
    source_url: 'https://en.wikipedia.org/wiki/Chandni_Chowk',
    state: 'mutual',
  },
]

function renderSections(summary = {}) {
  return render(
    <EntitySections
      links={LINKS}
      sourceTitle="Chandni Chowk"
      summary={summary}
    />,
  )
}

describe('a complete analysis', () => {
  it('reports the count for a section that found something', () => {
    renderSections({})
    expect(screen.getByText(/1 with an article/)).toBeTruthy()
  })

  it('says a section is empty when the typing stage finished', () => {
    renderSections({})
    // "No places identified" is a real finding when every name was looked at.
    expect(screen.getByText('No places identified')).toBeTruthy()
  })
})

describe('an analysis whose typing stage never finished', () => {
  const CUT = { entity_types_incomplete: true, aborted: true }

  it('does not say a section is empty', () => {
    renderSections(CUT)
    // The false negative this guards: the places stage never ran, so "no places
    // identified" is a claim about a stage that produced nothing.
    expect(screen.queryByText('No places identified')).toBeNull()
    expect(screen.queryByText('No missing places')).toBeNull()
    expect(screen.queryByText('No people identified')).toBeNull()
  })

  it('admits the section was not checked instead', () => {
    renderSections(CUT)
    expect(screen.getAllByText('Not checked').length).toBeGreaterThan(0)
  })

  it('drops the count, which is a floor rather than a total', () => {
    renderSections(CUT)
    expect(screen.queryByText(/1 with an article/)).toBeNull()
  })

  it('still lists the entities that were typed before the stop', () => {
    renderSections(CUT)
    // Suppressing the empty state is not suppressing real findings.
    expect(screen.getByText('Ada Lovelace ↗')).toBeTruthy()
  })
})
