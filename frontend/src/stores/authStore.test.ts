import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { User } from '../types';
import { useAuthStore } from './authStore';
import { authApi } from '../api/client';
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from '../utils/tokenStorage';

const USER: User = {
  id: 1,
  username: 'logistis',
  email: 'logistis@example.gr',
  first_name: 'Γιάννης',
  last_name: 'Παπαδόπουλος',
  is_staff: true,
};

const RESET = {
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  rememberMe: true,
};

describe('authStore', () => {
  beforeEach(() => {
    clearTokens();
    localStorage.clear();
    sessionStorage.clear();
    useAuthStore.setState(RESET);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    clearTokens();
  });

  describe('login', () => {
    it('«να με θυμάσαι» ενεργό -> localStorage', async () => {
      vi.spyOn(authApi, 'login').mockResolvedValue({
        access: 'a1',
        refresh: 'r1',
        user: USER,
      });

      await useAuthStore.getState().login('logistis', 'pw', true);

      expect(localStorage.getItem('accessToken')).toBe('a1');
      expect(sessionStorage.getItem('accessToken')).toBeNull();
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it('«να με θυμάσαι» ανενεργό -> sessionStorage', async () => {
      vi.spyOn(authApi, 'login').mockResolvedValue({
        access: 'a1',
        refresh: 'r1',
        user: null,
      });

      await useAuthStore.getState().login('logistis', 'pw', false);

      expect(sessionStorage.getItem('accessToken')).toBe('a1');
      expect(localStorage.getItem('accessToken')).toBeNull();
    });

    it('αποτυχία αφήνει μήνυμα και ΔΕΝ αυθεντικοποιεί', async () => {
      vi.spyOn(authApi, 'login').mockRejectedValue(new Error('Λάθος στοιχεία'));

      await expect(
        useAuthStore.getState().login('logistis', 'λάθος')
      ).rejects.toThrow('Λάθος στοιχεία');

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.error).toBe('Λάθος στοιχεία');
      expect(state.isLoading).toBe(false);
    });
  });

  describe('checkAuth', () => {
    it('κρατά το ΝΕΟ refresh token μετά από rotation', async () => {
      // Regression: το backend τρέχει ROTATE_REFRESH_TOKENS +
      // BLACKLIST_AFTER_ROTATION. Κρατώντας μόνο το access, το επόμενο
      // refresh έστελνε blacklisted token και η συνεδρία έπεφτε. Το checkAuth
      // τρέχει σε ΚΑΘΕ φόρτωση προστατευμένης σελίδας.
      setTokens('expired-access', 'r1', true);
      useAuthStore.setState({
        accessToken: 'expired-access',
        refreshToken: 'r1',
        rememberMe: true,
      });

      vi.spyOn(authApi, 'verifyToken').mockRejectedValue(new Error('expired'));
      vi.spyOn(authApi, 'refreshToken').mockResolvedValue({
        access: 'a2',
        refresh: 'r2',
      });
      vi.spyOn(authApi, 'getCurrentUser').mockResolvedValue({
        data: USER,
      });

      const ok = await useAuthStore.getState().checkAuth();

      expect(ok).toBe(true);
      expect(getAccessToken()).toBe('a2');
      expect(getRefreshToken()).toBe('r2');
      expect(useAuthStore.getState().refreshToken).toBe('r2');
    });

    it('κρατά το νέο refresh ακόμη κι αν αποτύχει το getCurrentUser', async () => {
      setTokens('expired-access', 'r1', true);
      useAuthStore.setState({
        accessToken: 'expired-access',
        refreshToken: 'r1',
        rememberMe: true,
      });

      vi.spyOn(authApi, 'verifyToken').mockRejectedValue(new Error('expired'));
      vi.spyOn(authApi, 'refreshToken').mockResolvedValue({
        access: 'a2',
        refresh: 'r2',
      });
      vi.spyOn(authApi, 'getCurrentUser').mockRejectedValue(new Error('500'));

      const ok = await useAuthStore.getState().checkAuth();

      expect(ok).toBe(true);
      expect(getRefreshToken()).toBe('r2');
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
    });

    it('backend χωρίς rotation: κρατά το υπάρχον refresh', async () => {
      setTokens('expired-access', 'r1', true);
      useAuthStore.setState({
        accessToken: 'expired-access',
        refreshToken: 'r1',
        rememberMe: true,
      });

      vi.spyOn(authApi, 'verifyToken').mockRejectedValue(new Error('expired'));
      vi.spyOn(authApi, 'refreshToken').mockResolvedValue({ access: 'a2' });
      vi.spyOn(authApi, 'getCurrentUser').mockResolvedValue({ data: null });

      await useAuthStore.getState().checkAuth();

      expect(getAccessToken()).toBe('a2');
      expect(getRefreshToken()).toBe('r1');
    });

    it('χωρίς access token επιστρέφει false χωρίς κλήση δικτύου', async () => {
      const verify = vi.spyOn(authApi, 'verifyToken');

      const ok = await useAuthStore.getState().checkAuth();

      expect(ok).toBe(false);
      expect(verify).not.toHaveBeenCalled();
    });

    it('αποτυχία refresh -> logout και καθαρά tokens', async () => {
      setTokens('expired-access', 'blacklisted', true);
      useAuthStore.setState({
        accessToken: 'expired-access',
        refreshToken: 'blacklisted',
      });

      vi.spyOn(authApi, 'verifyToken').mockRejectedValue(new Error('expired'));
      vi.spyOn(authApi, 'refreshToken').mockRejectedValue(new Error('blacklisted'));

      const ok = await useAuthStore.getState().checkAuth();

      expect(ok).toBe(false);
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(getAccessToken()).toBeNull();
      expect(getRefreshToken()).toBeNull();
    });
  });

  it('logout καθαρίζει state ΚΑΙ storage', () => {
    setTokens('a1', 'r1', true);
    useAuthStore.setState({
      accessToken: 'a1',
      refreshToken: 'r1',
      user: USER,
      isAuthenticated: true,
    });

    useAuthStore.getState().logout();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
