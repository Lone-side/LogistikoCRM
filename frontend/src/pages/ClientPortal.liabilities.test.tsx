import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const { getLiabilities } = vi.hoisted(() => ({ getLiabilities: vi.fn() }))

vi.mock('../stores/authStore', () => ({
  useAuthStore: (selector: (s: unknown) => unknown) =>
    selector({
      user: { is_client: true, client_name: 'DOKIMI AE', client_afm: '099000117' },
      logout: () => {},
    }),
}))

vi.mock('../api/client', () => ({
  portalApi: {
    getProfile: () => Promise.resolve({ afm: '099000117', eponimia: 'DOKIMI AE' }),
    getObligations: () => Promise.resolve({ count: 0, results: [] }),
    getDocuments: () => Promise.resolve({ count: 0, results: [] }),
    getVat: () => Promise.resolve({
      summary: { output: { net: '0.00', vat: '0.00' }, input: { net: '0.00', vat: '0.00' } },
      periods: [], records: [], records_truncated: false,
    }),
    getLiabilities: (...a: unknown[]) => getLiabilities(...a),
    uploadDocument: () => Promise.resolve({}),
  },
}))

import ClientPortal from './ClientPortal'

const DATA = {
  count: 1,
  results: [
    {
      id: 1, source: 'aade', source_display: 'ΑΑΔΕ', description: 'ΦΠΑ Α τριμ.',
      amount: '100.00', due_date: '2026-04-30', payment_code: 'RF123', status: 'outstanding',
      status_display: 'Ανεξόφλητη',
    },
  ],
  totals: { aade: '100.00' },
  links: { aade: 'https://aade.example/debts', efka: 'https://efka.example/debts' },
}

const EMPTY = { count: 0, results: [], totals: {}, links: { aade: 'https://aade.example/debts', efka: 'https://efka.example/debts' } }

function renderPortal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ClientPortal />
    </QueryClientProvider>,
  )
}

async function gotoLiabilities(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('tab', { name: 'Οφειλές' }))
}

describe('ClientPortal — Οφειλές tab', () => {
  beforeEach(() => {
    getLiabilities.mockReset()
    getLiabilities.mockResolvedValue(DATA)
  })

  it('renders the AADE & EFKA deep-links with safe target/rel', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoLiabilities(user)
    const aade = await screen.findByRole('link', { name: /myAADE/ })
    expect(aade).toHaveAttribute('href', 'https://aade.example/debts')
    expect(aade).toHaveAttribute('target', '_blank')
    expect(aade).toHaveAttribute('rel', expect.stringContaining('noopener'))
    const efka = screen.getByRole('link', { name: /ΕΦΚΑ/ })
    expect(efka).toHaveAttribute('href', 'https://efka.example/debts')
  })

  it('renders the accountant-entered liabilities and the disclaimer', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoLiabilities(user)
    expect(await screen.findByText('ΦΠΑ Α τριμ.')).toBeInTheDocument()
    expect(screen.getByText('€100.00')).toBeInTheDocument()
    expect(screen.getByText('RF123')).toBeInTheDocument()
    expect(screen.getByText('Ανεξόφλητη')).toBeInTheDocument()
    expect(screen.getByText(/ενημερωτικά/i)).toBeInTheDocument()
  })

  it('shows an empty state when there are no liabilities', async () => {
    const user = userEvent.setup()
    getLiabilities.mockResolvedValue(EMPTY)
    renderPortal()
    await gotoLiabilities(user)
    expect(await screen.findByText('Δεν υπάρχουν καταχωρημένες οφειλές.')).toBeInTheDocument()
  })
})
