import { create } from "zustand";
import { tenancyApi } from "../api/modules/tenancy";
import type { TenantOverview } from "../api/types/tenancy";

interface TenantState {
  overview: TenantOverview | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  clear: () => void;
}

let refreshSequence = 0;

export const useTenantStore = create<TenantState>((set) => ({
  overview: null,
  loading: false,
  error: null,
  refresh: async () => {
    const sequence = ++refreshSequence;
    set({ loading: true, error: null });
    try {
      const overview = await tenancyApi.getTenantOverview();
      if (sequence === refreshSequence) {
        set({ overview, loading: false });
      }
    } catch (reason) {
      if (sequence === refreshSequence) {
        set({
          loading: false,
          error: reason instanceof Error ? reason.message : "企业空间读取失败",
        });
      }
    }
  },
  clear: () => {
    refreshSequence += 1;
    set({ overview: null, loading: false, error: null });
  },
}));
