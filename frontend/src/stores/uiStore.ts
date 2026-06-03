import { create } from "zustand";

export type TimeRange = "1d" | "1w" | "1m" | "3m" | "1y" | "5y";

interface UIState {
  selectedTimeRange: TimeRange;
  activeBrokerFilter: string | null;
  setTimeRange: (range: TimeRange) => void;
  setBrokerFilter: (brokerId: string | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  selectedTimeRange: "1m",
  activeBrokerFilter: null,
  setTimeRange: (range) => set({ selectedTimeRange: range }),
  setBrokerFilter: (brokerId) => set({ activeBrokerFilter: brokerId }),
}));
