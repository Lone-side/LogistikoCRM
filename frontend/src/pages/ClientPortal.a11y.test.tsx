import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('../stores/authStore', () => ({
  useAuthStore: (s: (x: unknown) => unknown) =>
    s({ user: { is_client: true, client_name: 'A', client_afm: '1' }, logout: () => {} }),
}))
vi.mock('../api/client', () => ({
  portalApi: {
    getProfile: () => Promise.resolve({ afm: '1', eponimia: 'A' }),
    getObligations: () => Promise.resolve({ count: 0, results: [] }),
    getDocuments: () => Promise.resolve({ count: 0, results: [] }),
    getVat: () => Promise.resolve({
      summary: { output: { net: '0.00', vat: '0.00' }, input: { net: '0.00', vat: '0.00' } },
      periods: [], records: [], records_truncated: false,
    }),
    getLiabilities: () => Promise.resolve({ count: 0, results: [], totals: {}, links: { aade: '', efka: '' } }),
    uploadDocument: () => Promise.resolve({}),
  },
}))

import ClientPortal from './ClientPortal'

const renderPortal = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><ClientPortal /></QueryClientProvider>)
}

describe('ClientPortal accessibility', () => {
  beforeEach(() => {})

  it('exposes the tabs as an accessible tablist', () => {
    renderPortal()
    expect(screen.getByRole('tablist', { name: 'Ενότητες πύλης' })).toBeInTheDocument()
    const tabs = screen.getAllByRole('tab')
    expect(tabs.length).toBe(5)
  })

  it('marks the active tab with aria-selected', () => {
    renderPortal()
    const overview = screen.getByRole('tab', { name: 'Επισκόπηση' })
    expect(overview).toHaveAttribute('aria-selected', 'true')
    const vat = screen.getByRole('tab', { name: 'ΦΠΑ' })
    expect(vat).toHaveAttribute('aria-selected', 'false')
  })

  it('has an accessible logout control', () => {
    renderPortal()
    expect(screen.getByRole('button', { name: 'Αποσύνδεση' })).toBeInTheDocument()
  })
})
