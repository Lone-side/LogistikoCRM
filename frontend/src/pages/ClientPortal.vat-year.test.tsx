import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// --- Mocks -------------------------------------------------------------
// authStore: a client user, no-op logout.
vi.mock('../stores/authStore', () => ({
  useAuthStore: (selector: (s: unknown) => unknown) =>
    selector({
      user: { is_client: true, client_name: 'DOKIMI AE', client_afm: '099000117' },
      logout: () => {},
    }),
}))

// portalApi: capture the year passed to getVat.
const getVat = vi.fn()
vi.mock('../api/client', () => ({
  portalApi: {
    getProfile: () => Promise.resolve({ afm: '099000117', eponimia: 'DOKIMI AE' }),
    getObligations: () => Promise.resolve({ count: 0, results: [] }),
    getDocuments: () => Promise.resolve({ count: 0, results: [] }),
    getVat: (...args: unknown[]) => getVat(...args),
    uploadDocument: () => Promise.resolve({}),
  },
}))

import ClientPortal from './ClientPortal'

const VAT_FIXTURE = {
  summary: { output: { net: '1500.00', vat: '360.00' }, input: { net: '300.00', vat: '72.00' } },
  periods: [
    { id: 1, period_type: 'monthly', year: 2026, period: 5, vat_output: '360.00',
      vat_input: '72.00', vat_difference: '288.00', final_result: '288.00', is_locked: false },
    { id: 2, period_type: 'monthly', year: 2025, period: 11, vat_output: '192.00',
      vat_input: '48.00', vat_difference: '144.00', final_result: '144.00', is_locked: false },
  ],
  records: [],
  records_truncated: false,
}

function renderPortal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ClientPortal />
    </QueryClientProvider>,
  )
}

describe('ClientPortal — VAT year selector', () => {
  beforeEach(() => {
    getVat.mockReset()
    getVat.mockResolvedValue(VAT_FIXTURE)
  })

  it('renders a year selector on the VAT tab', async () => {
    const user = userEvent.setup()
    renderPortal()
    await user.click(await screen.findByRole('tab', { name: 'ΦΠΑ' }))

    const select = await screen.findByLabelText(/έτος/i)
    expect(select).toBeInTheDocument()
    // Years derived from periods: 2026 and 2025 must be options.
    expect(screen.getByRole('option', { name: '2026' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '2025' })).toBeInTheDocument()
  })

  it('refetches VAT with the selected year', async () => {
    const user = userEvent.setup()
    renderPortal()
    await user.click(await screen.findByRole('tab', { name: 'ΦΠΑ' }))

    const select = await screen.findByLabelText(/έτος/i)
    await user.selectOptions(select, '2025')

    await waitFor(() => {
      // getVat must have been called with year 2025 at some point.
      const calledWith2025 = getVat.mock.calls.some(
        (args) => args[0] === 2025 || (args[0] && (args[0] as { year?: number }).year === 2025),
      )
      expect(calledWith2025).toBe(true)
    })
  })
})
