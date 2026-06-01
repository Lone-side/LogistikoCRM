import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

// --- Mocks -------------------------------------------------------------
const { authState } = vi.hoisted(() => ({
  authState: {
    isAuthenticated: false,
    user: null as { is_client?: boolean } | null,
    checkAuth: vi.fn().mockResolvedValue(undefined),
  },
}))

// Zustand-style selector hook over the hoisted state.
vi.mock('../stores/authStore', () => ({
  useAuthStore: (selector: (s: typeof authState) => unknown) => selector(authState),
}))

// Stub Navigate so we can assert the redirect target without a real router.
vi.mock('react-router-dom', () => ({
  Navigate: ({ to }: { to: string }) => <div data-testid="navigate">{to}</div>,
}))

// Stub Layout (from the components barrel) so staff content renders bare.
vi.mock('../components', () => ({
  Layout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}))

import { ProtectedRoute, ClientRoute } from './guards'

const Child = () => <div data-testid="child">CONTENT</div>

describe('ProtectedRoute (staff)', () => {
  beforeEach(() => {
    authState.isAuthenticated = false
    authState.user = null
    authState.checkAuth = vi.fn().mockResolvedValue(undefined)
  })

  it('redirects unauthenticated users to /login', async () => {
    authState.isAuthenticated = false
    render(<ProtectedRoute><Child /></ProtectedRoute>)
    await waitFor(() =>
      expect(screen.getByTestId('navigate')).toHaveTextContent('/login'))
  })

  it('redirects a client off the staff area to /portal', async () => {
    authState.isAuthenticated = true
    authState.user = { is_client: true }
    render(<ProtectedRoute><Child /></ProtectedRoute>)
    await waitFor(() =>
      expect(screen.getByTestId('navigate')).toHaveTextContent('/portal'))
  })

  it('renders staff content for a staff user', async () => {
    authState.isAuthenticated = true
    authState.user = { is_client: false }
    render(<ProtectedRoute><Child /></ProtectedRoute>)
    await waitFor(() => expect(screen.getByTestId('child')).toBeInTheDocument())
    expect(screen.getByTestId('layout')).toBeInTheDocument()
  })
})

describe('ClientRoute (portal)', () => {
  beforeEach(() => {
    authState.isAuthenticated = false
    authState.user = null
    authState.checkAuth = vi.fn().mockResolvedValue(undefined)
  })

  it('redirects unauthenticated users to /login', async () => {
    authState.isAuthenticated = false
    render(<ClientRoute><Child /></ClientRoute>)
    await waitFor(() =>
      expect(screen.getByTestId('navigate')).toHaveTextContent('/login'))
  })

  it('redirects a staff user off the portal to /dashboard', async () => {
    authState.isAuthenticated = true
    authState.user = { is_client: false }
    render(<ClientRoute><Child /></ClientRoute>)
    await waitFor(() =>
      expect(screen.getByTestId('navigate')).toHaveTextContent('/dashboard'))
  })

  it('renders portal content for a client user', async () => {
    authState.isAuthenticated = true
    authState.user = { is_client: true }
    render(<ClientRoute><Child /></ClientRoute>)
    await waitFor(() => expect(screen.getByTestId('child')).toBeInTheDocument())
  })
})
