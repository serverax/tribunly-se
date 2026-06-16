import { create } from "zustand";
import type { LawAppCase } from "@/types/case";
import { createCase, getCase, listCases } from "@/lib/api";

type CaseState = {
  cases: LawAppCase[];
  activeCase: LawAppCase | null;
  loading: boolean;
  error: string | null;
  fetchCases: () => Promise<void>;
  fetchCase: (id: string) => Promise<void>;
  addCase: (title?: string, facts?: Record<string, unknown>) => Promise<LawAppCase>;
  setActiveCase: (c: LawAppCase | null) => void;
};

export const useCaseStore = create<CaseState>((set) => ({
  cases: [],
  activeCase: null,
  loading: false,
  error: null,

  async fetchCases() {
    set({ loading: true, error: null });
    try {
      const cases = await listCases();
      set({ cases, loading: false });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load cases",
      });
    }
  },

  async fetchCase(id) {
    set({ loading: true, error: null });
    try {
      const activeCase = await getCase(id);
      set({ activeCase, loading: false });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load case",
      });
    }
  },

  async addCase(title, facts) {
    const created = await createCase({
      title: title || "New case",
      claim_type: "unfair_dismissal",
      facts,
    });
    set((s) => ({ cases: [created, ...s.cases], activeCase: created }));
    return created;
  },

  setActiveCase(activeCase) {
    set({ activeCase });
  },
}));
