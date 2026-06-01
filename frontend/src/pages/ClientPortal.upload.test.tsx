import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// --- Mocks -------------------------------------------------------------
const { uploadDocument } = vi.hoisted(() => ({ uploadDocument: vi.fn() }))

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
    uploadDocument: (...args: unknown[]) => uploadDocument(...args),
  },
}))

import ClientPortal from './ClientPortal'

function renderPortal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ClientPortal />
    </QueryClientProvider>,
  )
}

async function gotoDocuments(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('tab', { name: 'Έγγραφα' }))
}

function fileInput(): HTMLInputElement {
  // The file input is hidden (triggered via a button); query the DOM directly.
  const input = document.querySelector('input[type="file"]')
  if (!input) throw new Error('file input not found')
  return input as HTMLInputElement
}

describe('ClientPortal — document upload', () => {
  beforeEach(() => {
    uploadDocument.mockReset()
    uploadDocument.mockResolvedValue({ id: 1, filename: 'doc.pdf' })
  })

  it('shows the upload control on the documents tab', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoDocuments(user)
    expect(screen.getByText('Ανέβασμα εγγράφου')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Επιλογή αρχείου/ })).toBeInTheDocument()
  })

  it('uploads a selected file with the chosen category', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoDocuments(user)

    // Choose a category (default is 'general').
    await user.selectOptions(screen.getByRole('combobox'), 'invoices')

    const file = new File(['%PDF-1.4'], 'invoice.pdf', { type: 'application/pdf' })
    await user.upload(fileInput(), file)

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1))
    const [sentFile, category] = uploadDocument.mock.calls[0]
    expect((sentFile as File).name).toBe('invoice.pdf')
    expect(category).toBe('invoices')
  })

  it('shows a success message after upload', async () => {
    const user = userEvent.setup()
    renderPortal()
    await gotoDocuments(user)

    const file = new File(['%PDF-1.4'], 'report.pdf', { type: 'application/pdf' })
    await user.upload(fileInput(), file)

    await waitFor(() =>
      expect(screen.getByText(/ανέβηκε επιτυχώς/i)).toBeInTheDocument())
    expect(screen.getByText(/report\.pdf/)).toBeInTheDocument()
  })

  it('shows the backend error message on failure', async () => {
    const user = userEvent.setup()
    uploadDocument.mockRejectedValue({
      response: { data: { detail: 'Μη επιτρεπτός τύπος αρχείου.' } },
    })
    renderPortal()
    await gotoDocuments(user)

    const file = new File(['x'], 'hack.exe', { type: 'application/octet-stream' })
    await user.upload(fileInput(), file)

    await waitFor(() =>
      expect(screen.getByText('Μη επιτρεπτός τύπος αρχείου.')).toBeInTheDocument())
  })

  it('falls back to a generic error when no detail is provided', async () => {
    const user = userEvent.setup()
    uploadDocument.mockRejectedValue(new Error('network'))
    renderPortal()
    await gotoDocuments(user)

    const file = new File(['x'], 'x.pdf', { type: 'application/pdf' })
    await user.upload(fileInput(), file)

    await waitFor(() =>
      expect(screen.getByText(/Σφάλμα κατά το ανέβασμα/)).toBeInTheDocument())
  })
})
