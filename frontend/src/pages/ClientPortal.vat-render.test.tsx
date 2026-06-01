import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const { getVat } = vi.hoisted(() => ({ getVat: vi.fn() }))

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
    getVat: (...a: unknown[]) => getVat(...a),
    uploadDocument: () => Promise.resolve({}),
  },
}))

import ClientPortal from './ClientPortal'

const FULL = {
  summary: {
    output: { net: '1500.00', vat: '360.00' },
    input: { net: '300.00', vat: '72.00' },
  },
  periods: [
    { id: 1, period_type: 'monthly', year: 2026, period: 5, vat_output: '360.00',
      vat_input: '72.00', vat_difference: '288.00', final_result: '188.00', is_locked: true },
  ],
  records: [
    { id: 11, mark: 400100001, issue_date: '2026-05-10', rec_type: 1, kind: 'output',
      inv_type: '1.1', net_value: '1000.00', vat_amount: '240.00' },
    { id: 12, mark: 400100003, issue_date: '2026-05-20', rec_type: 2, kind: 'input',
      inv_type: 'ΕΙΣΡΟΕΣ_361', net_value: '300.00', vat_amount: '72.00' },
  ],
  records_truncated: false,
}

const EMPTY = {
  summary: { output: { net: '0.00', vat: '0.00' }, input: { net: '0.00', vat: '0.00' } },
  periods: [],
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

async function gotoVat(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('tab', { name: 'ΦΠΑ' }))
}

describe('ClientPortal — VAT tab rendering', () => {
  beforeEach(() => {
    getVat.mockReset()
    getVat.mockResolvedValue(FULL)
  })

  it('renders the summary cards (output/input net & vat)', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoVat(user)
    expect(await screen.findByText('Εκροές (Έσοδα)')).toBeInTheDocument()
    expect(screen.getByText('Εισροές (Έξοδα)')).toBeInTheDocument()
    // €1500.00 is unique to the summary; €360.00 also appears in the periods
    // table, so assert at least one occurrence.
    expect(screen.getByText('€1500.00')).toBeInTheDocument()
    expect(screen.getAllByText('€360.00').length).toBeGreaterThan(0)
    expect(screen.getByText('€1500.00')).toBeInTheDocument()
  })

  it('renders the periods table with the locked badge', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoVat(user)
    expect(await screen.findByText('Περίοδοι ΦΠΑ')).toBeInTheDocument()
    // Month + year render in the same <td>; scope the matcher to the cell tag
    // so ancestors (tr/tbody/table) don't also match.
    expect(
      screen.getByText(
        (_, el) =>
          el?.tagName === 'TD' && (el.textContent?.includes('Μάιος 2026') ?? false),
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('€288.00')).toBeInTheDocument()  // vat_difference
    expect(screen.getByText('€188.00')).toBeInTheDocument()  // final_result
    expect(screen.getByText(/κλειδωμέν/i)).toBeInTheDocument()
  })

  it('renders the records table with both directions', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoVat(user)
    expect(await screen.findByText('400100001')).toBeInTheDocument()
    expect(screen.getByText('Εκροή')).toBeInTheDocument()
    expect(screen.getByText('Εισροή')).toBeInTheDocument()
  })

  it('shows empty states when there is no VAT data', async () => {
    const user = userEvent.setup()
    getVat.mockResolvedValue(EMPTY)
    renderPortal()
    await gotoVat(user)
    expect(await screen.findByText('Δεν υπάρχουν υπολογισμένες περίοδοι.')).toBeInTheDocument()
    expect(screen.getByText('Δεν υπάρχουν παραστατικά.')).toBeInTheDocument()
  })

  it('shows an error state when the VAT query fails', async () => {
    const user = userEvent.setup()
    getVat.mockRejectedValue(new Error('500'))
    renderPortal()
    await gotoVat(user)
    expect(await screen.findByText('Σφάλμα φόρτωσης δεδομένων ΦΠΑ.')).toBeInTheDocument()
  })
})
