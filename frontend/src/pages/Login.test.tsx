import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// --- Mocks -------------------------------------------------------------
// vi.mock factories are hoisted, so shared state must be created via vi.hoisted.
const { navigate, authState } = vi.hoisted(() => ({
  navigate: vi.fn(),
  authState: {
    user: null as { is_client?: boolean } | null,
    isLoading: false,
    error: null as string | null,
    login: vi.fn(),
    clearError: vi.fn(),
  },
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigate,
}))

// useAuthStore is used both as a hook (returns the state) and statically
// via useAuthStore.getState() (reads user after login). Support both.
vi.mock('../stores/authStore', () => ({
  useAuthStore: Object.assign(() => authState, { getState: () => authState }),
}))

import Login from './Login'

describe('Login', () => {
  beforeEach(() => {
    navigate.mockReset()
    authState.user = null
    authState.isLoading = false
    authState.error = null
    authState.login = vi.fn().mockResolvedValue(undefined)
    authState.clearError = vi.fn()
  })

  it('renders the login form', () => {
    render(<Login />)
    expect(screen.getByLabelText('Όνομα χρήστη')).toBeInTheDocument()
    expect(screen.getByLabelText('Κωδικός')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Σύνδεση/ })).toBeInTheDocument()
  })

  it('submits the entered credentials', async () => {
    const user = userEvent.setup()
    render(<Login />)
    await user.type(screen.getByLabelText('Όνομα χρήστη'), 'staffuser')
    await user.type(screen.getByLabelText('Κωδικός'), 'secret123')
    await user.click(screen.getByRole('button', { name: /Σύνδεση/ }))

    await waitFor(() => {
      expect(authState.login).toHaveBeenCalledWith('staffuser', 'secret123', true)
    })
  })

  it('redirects a staff user to /dashboard', async () => {
    const user = userEvent.setup()
    authState.login = vi.fn().mockImplementation(async () => {
      authState.user = { is_client: false }
    })
    render(<Login />)
    await user.type(screen.getByLabelText('Όνομα χρήστη'), 'staff')
    await user.type(screen.getByLabelText('Κωδικός'), 'pw')
    await user.click(screen.getByRole('button', { name: /Σύνδεση/ }))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/dashboard'))
  })

  it('redirects a client user to /portal', async () => {
    const user = userEvent.setup()
    authState.login = vi.fn().mockImplementation(async () => {
      authState.user = { is_client: true }
    })
    render(<Login />)
    await user.type(screen.getByLabelText('Όνομα χρήστη'), '099000117')
    await user.type(screen.getByLabelText('Κωδικός'), 'pw')
    await user.click(screen.getByRole('button', { name: /Σύνδεση/ }))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/portal'))
  })

  it('shows an error message on failed login', () => {
    authState.error = 'Λάθος στοιχεία σύνδεσης'
    render(<Login />)
    expect(screen.getByText('Λάθος στοιχεία σύνδεσης')).toBeInTheDocument()
  })

  it('does not navigate when login throws', async () => {
    const user = userEvent.setup()
    authState.login = vi.fn().mockRejectedValue(new Error('bad creds'))
    render(<Login />)
    await user.type(screen.getByLabelText('Όνομα χρήστη'), 'x')
    await user.type(screen.getByLabelText('Κωδικός'), 'y')
    await user.click(screen.getByRole('button', { name: /Σύνδεση/ }))

    await waitFor(() => expect(authState.login).toHaveBeenCalled())
    expect(navigate).not.toHaveBeenCalled()
  })

  it('disables the submit button while loading', () => {
    authState.isLoading = true
    render(<Login />)
    expect(screen.getByRole('button', { name: /Σύνδεση/ })).toBeDisabled()
  })
})
