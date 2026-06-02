import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const { api } = vi.hoisted(() => ({
  api: {
    getPortalStatus: vi.fn(),
    createPortalAccount: vi.fn(),
    resendPortalInvite: vi.fn(),
    setPortalPassword: vi.fn(),
  },
}))
vi.mock('../../api/client', () => ({ clientsApi: api }))

import { PortalAccessCard } from './PortalAccessCard'

function renderCard(clientId = 1) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <PortalAccessCard clientId={clientId} />
    </QueryClientProvider>,
  )
}

describe('PortalAccessCard', () => {
  beforeEach(() => {
    api.getPortalStatus.mockReset()
    api.createPortalAccount.mockReset()
    api.resendPortalInvite.mockReset()
    api.setPortalPassword.mockReset()
  })

  it('shows "no account" state with a create button', async () => {
    api.getPortalStatus.mockResolvedValue({
      client_id: 1, has_portal_account: false, portal_username: null,
      has_email: true, email: 'c@e.gr',
    })
    renderCard()
    expect(await screen.findByText(/Χωρίς πρόσβαση|Δεν έχει λογαριασμό/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Δημιουργία λογαριασμού/i })).toBeInTheDocument()
  })

  it('shows account info + resend button when account exists', async () => {
    api.getPortalStatus.mockResolvedValue({
      client_id: 1, has_portal_account: true, portal_username: '123456783',
      has_email: true, email: 'c@e.gr',
    })
    renderCard()
    expect(await screen.findByText('123456783')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Επαναποστολή/i })).toBeInTheDocument()
  })

  it('creates an account and shows confirmation', async () => {
    const user = userEvent.setup()
    api.getPortalStatus.mockResolvedValue({
      client_id: 1, has_portal_account: false, portal_username: null,
      has_email: true, email: 'c@e.gr',
    })
    api.createPortalAccount.mockResolvedValue({
      client_id: 1, has_portal_account: true, portal_username: '123456783',
      has_email: true, email: 'c@e.gr', invite_sent: true,
      detail: 'Δημιουργήθηκε λογαριασμός portal.',
    })
    renderCard()
    await user.click(await screen.findByRole('button', { name: /Δημιουργία λογαριασμού/i }))
    await waitFor(() => expect(api.createPortalAccount).toHaveBeenCalledWith(1))
    expect(await screen.findByText(/στάλθηκε|Δημιουργήθηκε/i)).toBeInTheDocument()
  })

  it('warns when client has no email', async () => {
    api.getPortalStatus.mockResolvedValue({
      client_id: 1, has_portal_account: false, portal_username: null,
      has_email: false, email: null,
    })
    renderCard()
    expect(await screen.findByText(/χωρίς email|δεν έχει email/i)).toBeInTheDocument()
  })

  it('resends the invite', async () => {
    const user = userEvent.setup()
    api.getPortalStatus.mockResolvedValue({
      client_id: 1, has_portal_account: true, portal_username: '123456783',
      has_email: true, email: 'c@e.gr',
    })
    api.resendPortalInvite.mockResolvedValue({ detail: 'Η πρόσκληση στάλθηκε ξανά.', invite_sent: true })
    renderCard()
    await user.click(await screen.findByRole('button', { name: /Επαναποστολή/i }))
    await waitFor(() => expect(api.resendPortalInvite).toHaveBeenCalledWith(1))
    expect(await screen.findByText(/στάλθηκε ξανά/i)).toBeInTheDocument()
  })

  it('lets staff set the portal password directly', async () => {
    const user = userEvent.setup()
    api.getPortalStatus.mockResolvedValue({
      client_id: 1, has_portal_account: true, portal_username: '123456783',
      has_email: true, email: 'c@e.gr',
    })
    api.setPortalPassword.mockResolvedValue({ detail: 'Ο κωδικός ορίστηκε. Δώστε τον στον πελάτη.' })
    renderCard()
    const input = await screen.findByPlaceholderText(/Νέος κωδικός/i)
    await user.type(input, 'Sup3rStr0ng!pw')
    await user.click(screen.getByRole('button', { name: /Ορισμός κωδικού/i }))
    await waitFor(() =>
      expect(api.setPortalPassword).toHaveBeenCalledWith(1, 'Sup3rStr0ng!pw'))
    expect(await screen.findByText(/Ο κωδικός ορίστηκε/i)).toBeInTheDocument()
  })
})
