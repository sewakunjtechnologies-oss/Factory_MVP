import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AuthUser } from "../types/api";

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  setSession: (token: string, user: AuthUser) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
    }),
    {
      name: "factory-session",
      partialize: (state) => ({ token: state.token, user: state.user }),
    },
  ),
);
