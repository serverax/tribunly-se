import { create } from "zustand";
import type { AuthUser } from "@/lib/auth";
import { getCurrentUser, logout as authLogout } from "@/lib/auth";

type UserState = {
  user: AuthUser | null;
  checked: boolean;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};

export const useUserStore = create<UserState>((set) => ({
  user: null,
  checked: false,
  loading: false,

  async refresh() {
    set({ loading: true });
    try {
      const user = await getCurrentUser();
      set({ user, checked: true, loading: false });
    } catch {
      set({ user: null, checked: true, loading: false });
    }
  },

  async logout() {
    await authLogout();
    set({ user: null });
  },
}));
