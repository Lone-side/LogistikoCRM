import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API layer the store depends on.
const { authApi } = vi.hoisted(() => ({
  authApi: {
    login: vi.fn(),
    verifyToken: vi.fn(),
    refreshToken: vi.fn(),
    getCurrentUser: vi.fn(),
  },
}))
vi.mock('../api/client', () => ({ authApi }))

import { useAuthStore } from './authStore'

const FRESH = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  rememberMe: true,
}

describe('authStore', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    useAuthStore.setState(FRESH)
    authApi.login.mockReset()
    authApi.verifyToken.mockReset()
    authApi.refreshToken.mockReset()
    authApi.getCurrentUser.mockReset()
  })

  // ---- login ----
  it('login stores tokens in localStorage when rememberMe=true', async () => {
    authApi.login.mockResolvedValue({
      access: 'acc', refresh: 'ref', user: { id: 1, is_client: false },
    })
    await useAuthStore.getState().login('u', 'p', true)

    const s = useAuthStore.getState()
    expect(s.isAuthenticated).toBe(true)
    expect(s.accessToken).toBe('acc')
    expect(localStorage.getItem('accessToken')).toBe('acc')
    expect(localStorage.getItem('refreshToken')).toBe('ref')
  })

  it('login with rememberMe=false uses sessionStorage and clears localStorage', async () => {
    authApi.login.mockResolvedValue({ access: 'acc', refresh: 'ref', user: { id: 1 } })
    await useAuthStore.getState().login('u', 'p', false)

    expect(sessionStorage.getItem('accessToken')).toBe('acc')
    expect(localStorage.getItem('accessToken')).toBeNull()
    expect(localStorage.getItem('refreshToken')).toBeNull()
  })

  it('login failure sets error and leaves user unauthenticated', async () => {
    authApi.login.mockRejectedValue(new Error('Λάθος στοιχεία'))
    await expect(useAuthStore.getState().login('u', 'bad')).rejects.toThrow()

    const s = useAuthStore.getState()
    expect(s.isAuthenticated).toBe(false)
    expect(s.error).toBe('Λάθος στοιχεία')
    expect(s.isLoading).toBe(false)
  })

  // ---- logout ----
  it('logout clears state and BOTH storages', () => {
    localStorage.setItem('accessToken', 'a')
    localStorage.setItem('refreshToken', 'r')
    sessionStorage.setItem('accessToken', 'a')
    sessionStorage.setItem('refreshToken', 'r')
    useAuthStore.setState({ isAuthenticated: true, user: { id: 1 } as never, accessToken: 'a' })

    useAuthStore.getState().logout()

    const s = useAuthStore.getState()
    expect(s.isAuthenticated).toBe(false)
    expect(s.user).toBeNull()
    expect(s.accessToken).toBeNull()
    expect(localStorage.getItem('accessToken')).toBeNull()
    expect(sessionStorage.getItem('accessToken')).toBeNull()
  })

  // ---- checkAuth ----
  it('checkAuth returns false and unauthenticated when no token', async () => {
    useAuthStore.setState({ accessToken: null })
    const ok = await useAuthStore.getState().checkAuth()
    expect(ok).toBe(false)
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('checkAuth returns true when token verifies', async () => {
    useAuthStore.setState({ accessToken: 'acc', user: { id: 1 } as never })
    authApi.verifyToken.mockResolvedValue({})
    const ok = await useAuthStore.getState().checkAuth()
    expect(ok).toBe(true)
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('checkAuth fetches the user when missing but token valid', async () => {
    useAuthStore.setState({ accessToken: 'acc', user: null })
    authApi.verifyToken.mockResolvedValue({})
    authApi.getCurrentUser.mockResolvedValue({ data: { id: 7, is_client: true } })
    await useAuthStore.getState().checkAuth()
    expect(useAuthStore.getState().user).toEqual({ id: 7, is_client: true })
  })

  it('checkAuth refreshes the token when verify fails but refresh works', async () => {
    useAuthStore.setState({ accessToken: 'old', refreshToken: 'ref', user: { id: 1 } as never })
    authApi.verifyToken.mockRejectedValue(new Error('expired'))
    authApi.refreshToken.mockResolvedValue({ access: 'new' })
    authApi.getCurrentUser.mockResolvedValue({ data: { id: 1 } })

    const ok = await useAuthStore.getState().checkAuth()
    expect(ok).toBe(true)
    expect(useAuthStore.getState().accessToken).toBe('new')
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('checkAuth logs out when both verify and refresh fail', async () => {
    useAuthStore.setState({ accessToken: 'old', refreshToken: 'ref', isAuthenticated: true })
    authApi.verifyToken.mockRejectedValue(new Error('expired'))
    authApi.refreshToken.mockRejectedValue(new Error('refresh dead'))

    const ok = await useAuthStore.getState().checkAuth()
    expect(ok).toBe(false)
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(useAuthStore.getState().accessToken).toBeNull()
  })

  it('checkAuth logs out when verify fails and there is no refresh token', async () => {
    useAuthStore.setState({ accessToken: 'old', refreshToken: null, isAuthenticated: true })
    authApi.verifyToken.mockRejectedValue(new Error('expired'))

    const ok = await useAuthStore.getState().checkAuth()
    expect(ok).toBe(false)
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  // ---- clearError ----
  it('clearError resets the error', () => {
    useAuthStore.setState({ error: 'boom' })
    useAuthStore.getState().clearError()
    expect(useAuthStore.getState().error).toBeNull()
  })
})
