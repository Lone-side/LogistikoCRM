import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'

const { cal } = vi.hoisted(() => ({
  cal: {
    data: { obligations: [], stats: {} } as unknown,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  },
}))

// Keep the real helper functions/constants; override only the data hooks.
vi.mock('../hooks/useCalendar', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useCalendar')>()
  return {
    ...actual,
    useCalendar: () => cal,
    useCompleteObligation: () => ({ mutate: vi.fn(), isPending: false }),
  }
})
vi.mock('../hooks/useClients', () => ({ useClients: () => ({ data: { results: [] } }) }))
vi.mock('../hooks/useObligations', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useObligations')>()
  return { ...actual, useObligationTypes: () => ({ data: [] }) }
})
vi.mock('../hooks/useEmail', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useEmail')>()
  return { ...actual, useCompleteAndNotify: () => ({ mutate: vi.fn(), isPending: false }) }
})

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Calendar from './Calendar'
import { ToastProvider } from '../components/Toast'

const renderCal = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider><Calendar /></ToastProvider>
    </QueryClientProvider>,
  )
}

describe('Calendar', () => {
  beforeEach(() => {
    cal.data = { obligations: [], stats: {} }
    cal.isLoading = false
    cal.isError = false
  })

  it('renders without crashing (empty data)', () => {
    const { container } = renderCal()
    expect(container).toBeTruthy()
    // A month/year control should be present.
    expect(container.querySelector('button, select')).toBeTruthy()
  })

  it('renders in loading state', () => {
    cal.isLoading = true
    const { container } = renderCal()
    expect(container).toBeTruthy()
  })

  it('renders in error state without throwing', () => {
    cal.isError = true
    const { container } = renderCal()
    expect(container).toBeTruthy()
  })
})
