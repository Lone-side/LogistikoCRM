import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User, AuthTokens } from '../types';
import { authApi } from '../api/client';
import {
  clearTokens,
  setAccessToken,
  setTokens as persistTokens,
} from '../utils/tokenStorage';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  rememberMe: boolean;

  // Actions
  login: (username: string, password: string, rememberMe?: boolean) => Promise<void>;
  logout: () => void;
  setUser: (user: User | null) => void;
  setTokens: (tokens: AuthTokens) => void;
  clearError: () => void;
  checkAuth: () => Promise<boolean>;
}

// Η αποθήκευση των tokens γίνεται αποκλειστικά μέσω του tokenStorage
// helper, ώστε γράψιμο και ανάγνωση (axios interceptor) να συμφωνούν.

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      rememberMe: true,

      login: async (username: string, password: string, rememberMe: boolean = true) => {
        set({ isLoading: true, error: null, rememberMe });
        try {
          const response = await authApi.login(username, password);

          // rememberMe -> localStorage, αλλιώς sessionStorage. Ο helper
          // καθαρίζει το άλλο storage ώστε να μη μείνει stale token.
          persistTokens(response.access, response.refresh, rememberMe);

          set({
            accessToken: response.access,
            refreshToken: response.refresh,
            user: response.user || null,
            isAuthenticated: true,
            isLoading: false,
            error: null,
            rememberMe,
          });
        } catch (error) {
          const message = error instanceof Error
            ? error.message
            : 'Σφάλμα κατά τη σύνδεση';
          set({
            isLoading: false,
            error: message,
            isAuthenticated: false,
          });
          throw error;
        }
      },

      logout: () => {
        clearTokens();
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          error: null,
          rememberMe: true,
        });
      },

      setUser: (user: User | null) => {
        set({ user });
      },

      setTokens: (tokens: AuthTokens) => {
        persistTokens(tokens.access, tokens.refresh, get().rememberMe);
        set({
          accessToken: tokens.access,
          refreshToken: tokens.refresh,
          isAuthenticated: true,
        });
      },

      clearError: () => {
        set({ error: null });
      },

      checkAuth: async () => {
        const { accessToken, refreshToken, user } = get();

        if (!accessToken) {
          set({ isAuthenticated: false });
          return false;
        }

        try {
          await authApi.verifyToken(accessToken);

          // If we don't have user info, fetch it
          if (!user) {
            try {
              const response = await authApi.getCurrentUser();
              set({ user: response.data || response });
            } catch {
              // Ignore user fetch errors, token is still valid
            }
          }

          set({ isAuthenticated: true });
          return true;
        } catch {
          // Try to refresh the token
          if (refreshToken) {
            try {
              const newTokens = await authApi.refreshToken(refreshToken);
              setAccessToken(newTokens.access);

              // Also fetch user info after refresh
              try {
                const response = await authApi.getCurrentUser();
                set({
                  accessToken: newTokens.access,
                  user: response.data || response,
                  isAuthenticated: true,
                });
              } catch {
                set({
                  accessToken: newTokens.access,
                  isAuthenticated: true,
                });
              }
              return true;
            } catch {
              // Refresh also failed, logout
              get().logout();
              return false;
            }
          }
          get().logout();
          return false;
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.rememberMe ? state.accessToken : null,
        refreshToken: state.rememberMe ? state.refreshToken : null,
        user: state.rememberMe ? state.user : null,
        rememberMe: state.rememberMe,
      }),
    }
  )
);

export default useAuthStore;
