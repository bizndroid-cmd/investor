import { useEffect, useRef, useCallback } from "react";
import { useSocketStore } from "@/stores/socketStore";
import type { PriceQuote } from "@/api/types";
import { apiFetch } from "@/api/client";

const WS_BASE = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws`;
const MAX_BACKOFF = 30_000;
const POLL_INTERVAL = 60_000;

export function usePriceSocket(tickers: string[]) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const pollIntervalRef = useRef<ReturnType<typeof setInterval>>();
  const retriesRef = useRef(0);
  const tickersRef = useRef<string[]>(tickers);
  tickersRef.current = tickers;

  const { setConnected, setReconnecting, updatePrice } = useSocketStore();

  const getToken = () => localStorage.getItem("access_token") || "";

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) {
      // No token — don't try to connect, just fall back to polling
      startPolling();
      return;
    }

    try {
      const ws = new WebSocket(`${WS_BASE}?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        setReconnecting(false);
        retriesRef.current = 0;
        stopPolling();

        // Subscribe to tickers
        if (tickersRef.current.length > 0) {
          ws.send(JSON.stringify({ type: "subscribe", tickers: tickersRef.current }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "price_update" && data.payload) {
            const quote = data.payload as PriceQuote;
            updatePrice(quote.ticker, quote);
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = (event) => {
        setConnected(false);
        wsRef.current = null;
        // If the server rejected with 403, don't endlessly retry — fall back to polling
        if (event.code === 1006 && retriesRef.current > 2) {
          startPolling();
          return;
        }
        scheduleReconnect();
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // WebSocket constructor can throw — fall back to polling
      startPolling();
    }
  }, [setConnected, setReconnecting, updatePrice]);

  const scheduleReconnect = useCallback(() => {
    setReconnecting(true);
    startPolling();

    const delay = Math.min(1000 * 2 ** retriesRef.current, MAX_BACKOFF);
    retriesRef.current += 1;

    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect, setReconnecting]);

  const startPolling = useCallback(() => {
    if (pollIntervalRef.current) return;
    pollIntervalRef.current = setInterval(async () => {
      if (tickersRef.current.length === 0) return;
      try {
        const prices = await apiFetch<Record<string, PriceQuote>>(
          "/market/prices/batch",
          {
            method: "POST",
            body: JSON.stringify({ tickers: tickersRef.current }),
          }
        );
        for (const [ticker, quote] of Object.entries(prices)) {
          updatePrice(ticker, quote);
        }
      } catch {
        // ignore polling errors
      }
    }, POLL_INTERVAL);
  }, [updatePrice]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = undefined;
    }
  }, []);

  // Subscribe/unsubscribe when tickers change
  useEffect(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && tickers.length > 0) {
      ws.send(JSON.stringify({ type: "subscribe", tickers }));
    }
  }, [tickers]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      stopPolling();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, stopPolling]);
}
