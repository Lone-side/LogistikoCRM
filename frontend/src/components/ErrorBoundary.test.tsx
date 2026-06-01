import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from './ErrorBoundary'

function Boom(): React.ReactElement {
  throw new Error('boom')
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Silence the expected React error log noise.
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders children when there is no error', () => {
    render(<ErrorBoundary><div>safe content</div></ErrorBoundary>)
    expect(screen.getByText('safe content')).toBeInTheDocument()
  })

  it('renders the fallback when a child throws', () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>)
    expect(screen.getByText('Κάτι πήγε στραβά')).toBeInTheDocument()
  })

  it('compact mode does not take the full screen', () => {
    const { container } = render(
      <ErrorBoundary compact><Boom /></ErrorBoundary>,
    )
    // Fallback present, but not the full-screen wrapper.
    expect(screen.getByText('Κάτι πήγε στραβά')).toBeInTheDocument()
    expect(container.querySelector('.min-h-screen')).toBeNull()
  })

  it('recovers when resetKeys change (e.g. route navigation)', () => {
    const { rerender } = render(
      <ErrorBoundary resetKeys={['/a']}><Boom /></ErrorBoundary>,
    )
    expect(screen.getByText('Κάτι πήγε στραβά')).toBeInTheDocument()
    // Navigate away → new resetKeys, child no longer throws.
    rerender(
      <ErrorBoundary resetKeys={['/b']}><div>recovered</div></ErrorBoundary>,
    )
    expect(screen.getByText('recovered')).toBeInTheDocument()
  })
})
