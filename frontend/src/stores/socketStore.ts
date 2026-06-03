import { create } from "zustand";
import type { PriceQuote } from "@/api/types";

interface SocketState {
  isConnected: boolean;
  isReconnecting: boolean;
  priceUpdates: Map<string, PriceQuote>;
  setConnected: (connected: boolean) => void;
  setReconnecting: (reconnecting: boolean) => void;
  updatePrice: (ticker: string, quote: PriceQuote) => void;
}

export const useSocketStore = create<SocketState>((set) => ({
  isConnected: false,
  isReconnecting: false,
  priceUpdates: new Map(),
  setConnected: (connected) => set({ isConnected: connected }),
  setReconnecting: (reconnecting) => set({ isReconnecting: reconnecting }),
  updatePrice: (ticker, quote) =>
    set((state) => {
      const updated = new Map(state.priceUpdates);
      updated.set(ticker, quote);
      return { priceUpdates: updated };
    }),
}));
