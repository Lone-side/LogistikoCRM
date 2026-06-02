import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const { getVat, syncVat } = vi.hoisted(() => ({ getVat: vi.fn(), syncVat: vi.fn() }))

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
    syncVat: (...a: unknown[]) => syncVat(...a),
    uploadDocument: () => Promise.resolve({}),
  },
}))

import ClientPortal from './ClientPortal'

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

describe('ClientPortal — VAT self-sync', () => {
  beforeEach(() => {
    getVat.mockReset()
    getVat.mockResolvedValue(EMPTY)
    syncVat.mockReset()
  })

  it('shows a sync button on the VAT tab and calls syncVat on click', async () => {
    const user = userEvent.setup()
    syncVat.mockResolvedValue({ success: true, skipped: false })
    renderPortal()
    await gotoVat(user)

    const btn = await screen.findByRole('button', { name: /Συγχρονισμός από myDATA/ })
    await user.click(btn)

    expect(syncVat).toHaveBeenCalledTimes(1)
    expect(await screen.findByText(/Ο συγχρονισμός ολοκληρώθηκε/)).toBeInTheDocument()
  })

  it('shows a warning when the sync is skipped (locked period)', async () => {
    const user = userEvent.setup()
    syncVat.mockResolvedValue({
      success: false,
      skipped: true,
      locked: true,
      message: 'Ο συγχρονισμός παραλείφθηκε: η περίοδος είναι κλειδωμένη.',
    })
    renderPortal()
    await gotoVat(user)

    await user.click(await screen.findByRole('button', { name: /Συγχρονισμός από myDATA/ }))
    expect(await screen.findByText(/κλειδωμένη/)).toBeInTheDocument()
  })

  it('shows an error message when sync fails', async () => {
    const user = userEvent.setup()
    syncVat.mockRejectedValue({ response: { status: 503, data: { detail: 'Σφάλμα συγχρονισμού.' } } })
    renderPortal()
    await gotoVat(user)

    await user.click(await screen.findByRole('button', { name: /Συγχρονισμός από myDATA/ }))
    expect(await screen.findByText(/Σφάλμα συγχρονισμού/)).toBeInTheDocument()
  })
})
