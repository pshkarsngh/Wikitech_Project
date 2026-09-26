/**
 * Missing-connection highlighting.
 *
 * Phase 5 requires that a missing connection be visually distinguishable from
 * an existing one. That behaviour lives entirely in the stylesheet, so these
 * tests assert the two halves of it: the component picks a different class per
 * state, and those classes resolve to genuinely different colours.
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ConnectionStateBadge } from './ui.jsx'

// Testing Library only registers its own cleanup when the runner exposes a
// global afterEach, and this suite imports its hooks instead.
afterEach(cleanup)

const MODULE_CSS = readFileSync(join(process.cwd(), 'src', 'components', 'ui.module.css'), 'utf8')
function ruleBody(selector) {
  // A selector can appear in more than one rule, including inside a group such
  // as `.state_exists,\n.state_missing { ... }`, so every match is collected and
  // the later declaration wins the way the cascade would resolve it.
  const escaped = selector.replace('.', '\\.')
  const bodies = [...MODULE_CSS.matchAll(new RegExp(`${escaped}\\s*(?:,[^{]*)?\\{([^}]*)\\}`, 'g'))]
    .map((match) => match[1])
  expect(bodies.length, `${selector} has no rule in ui.module.css`).toBeGreaterThan(0)
  return bodies.join('\n')
}

function declarations(selector, property) {
  const body = ruleBody(selector)
  const match = body.match(new RegExp(`${property}\\s*:\\s*([^;]+)`))
  return match ? match[1].trim() : null
}

describe('ConnectionStateBadge', () => {
  it('labels an existing article EXISTS', () => {
    render(<ConnectionStateBadge state="exists" />)
    expect(screen.getByText('EXISTS')).toBeDefined()
  })

  it('labels a missing article MISSING', () => {
    render(<ConnectionStateBadge state="missing" />)
    expect(screen.getByText('MISSING')).toBeDefined()
  })

  it('falls back to the boolean when no state string is supplied', () => {
    const { unmount } = render(<ConnectionStateBadge exists />)
    expect(screen.getByText('EXISTS')).toBeDefined()
    unmount()
    render(<ConnectionStateBadge exists={false} />)
    expect(screen.getByText('MISSING')).toBeDefined()
  })

  it('never shows an unrecognised classification as a confirmed article', () => {
    render(<ConnectionStateBadge state="something-new" />)
    expect(screen.getByText('MISSING')).toBeDefined()
    expect(screen.queryByText('EXISTS')).toBeNull()
  })

  it('applies a different class per state', () => {
    const { container: existing, unmount } = render(<ConnectionStateBadge state="exists" />)
    const existsClass = existing.querySelector('span').className
    unmount()
    const { container: missing } = render(<ConnectionStateBadge state="missing" />)
    const missingClass = missing.querySelector('span').className
    expect(existsClass).not.toEqual(missingClass)
  })
})

describe('state highlight styling', () => {
  it('gives the missing badge its own background', () => {
    expect(declarations('.state_missing', 'background')).toBe('var(--missing)')
  })

  it('gives the existing badge its own background', () => {
    expect(declarations('.state_exists', 'background')).toBe('var(--mutual-soft)')
  })

  it('makes the two states visually distinct', () => {
    expect(declarations('.state_missing', 'background')).not.toEqual(
      declarations('.state_exists', 'background'),
    )
    expect(declarations('.state_missing', 'color')).not.toEqual(
      declarations('.state_exists', 'color'),
    )
  })
})
