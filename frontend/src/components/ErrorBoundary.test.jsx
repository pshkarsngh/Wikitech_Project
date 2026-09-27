/**
 * A render error must not blank the page.
 *
 * Without a boundary, an error thrown during render unmounts the whole tree and the user
 * gets a white page with no explanation. This is the same failure class as DEF-003 - a
 * layer nothing observes - seen from the other end: the app was fully broken and there was
 * no test and no UI to say so.
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ErrorBoundary from './ErrorBoundary.jsx'

// Testing Library only registers its own cleanup when the runner exposes a global
// afterEach, and this suite imports its hooks instead.
afterEach(cleanup)

// React logs the caught error itself, and the boundary logs it again in componentDidCatch.
// Silence both so a deliberate failure does not look like a broken suite.
let consoleError

function Boom({ explode }) {
  if (explode) throw new Error('component exploded')
  return <p>page content</p>
}

describe('ErrorBoundary', () => {
  function renderBoundary(explode) {
    return render(
      <ErrorBoundary>
        <Boom explode={explode} />
      </ErrorBoundary>,
    )
  }

  it('renders its children when nothing throws', () => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderBoundary(false)

    expect(screen.getByText('page content')).toBeDefined()
    expect(screen.queryByText('Something went wrong')).toBeNull()
    consoleError.mockRestore()
  })

  it('shows a message instead of a blank page when a child throws', () => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    renderBoundary(true)

    // Exactly one alert. ErrorMessage already carries role="alert", and a second one
    // wrapped around it would make a screen reader announce the failure twice.
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(screen.getByText('Something went wrong')).toBeDefined()
    // The original failure is still shown, not swallowed by a generic apology.
    expect(screen.getByText(/component exploded/)).toBeDefined()
    // And a way out that does not depend on the broken tree.
    expect(screen.getByRole('link', { name: 'Back to the start' })).toBeDefined()
    consoleError.mockRestore()
  })

  it('logs the error so a render failure is never invisible', () => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    renderBoundary(true)

    expect(consoleError).toHaveBeenCalledWith(
      'Unhandled render error',
      expect.any(Error),
      expect.anything(),
    )
    consoleError.mockRestore()
  })

  it('recovers when a retry renders cleanly', () => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { rerender } = renderBoundary(true)
    expect(screen.queryByText('page content')).toBeNull()

    // The child stops throwing, then the user retries.
    rerender(
      <ErrorBoundary>
        <Boom explode={false} />
      </ErrorBoundary>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(screen.getByText('page content')).toBeDefined()
    expect(screen.queryByText('Something went wrong')).toBeNull()
    consoleError.mockRestore()
  })

  it('offers reload rather than a retry button that cannot work', () => {
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderBoundary(true)

    // First failure: a retry is worth offering.
    expect(screen.getByRole('button', { name: 'Try again' })).toBeDefined()

    // The same error throws again, so the retry is withdrawn rather than repeated.
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Back to the start' })).toBeDefined()
    consoleError.mockRestore()
  })
})
