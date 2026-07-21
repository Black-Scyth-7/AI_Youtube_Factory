import { create } from "zustand";
import { persist } from "zustand/middleware";

import { type AuthUser, type TokenPair, authApi } from "./auth-api";

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setSession: (tokens: TokenPair) => Promise<void>;
  loadUser: () => Promise<void>;
  logout: () => Promise<void>;
}

/**
 * Authentication store. Tokens persist to localStorage so a session survives a
 * page reload. `setSession` stores tokens and hydrates the current user.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      setSession: async (tokens) => {
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          isAuthenticated: true,
        });
        await get().loadUser();
      },

      loadUser: async () => {
        const token = get().accessToken;
        if (!token) return;
        try {
          const user = await authApi.me(token);
          set({ user, isAuthenticated: true });
        } catch {
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
          });
        }
      },

      logout: async () => {
        const { accessToken, refreshToken } = get();
        if (accessToken && refreshToken) {
          await authApi.logout(accessToken, refreshToken).catch(() => undefined);
        }
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },
    }),
    {
      name: "ayf-auth",
      partialize: (s) => ({
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
      }),
    },
  ),
);
