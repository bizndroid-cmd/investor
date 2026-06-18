import { apiFetch } from "./client";
import type { Portfolio, NormalizedHolding, HistoricalDataPoint, TimeRange } from "./types";

export async function getPortfolio(): Promise<Portfolio> {
  return apiFetch<Portfolio>("/portfolio");
}

export async function getHoldings(brokerId?: string): Promise<NormalizedHolding[]> {
  const params = brokerId ? `?broker_id=${brokerId}` : "";
  return apiFetch<NormalizedHolding[]>(`/portfolio/holdings${params}`);
}

export async function refreshPortfolio(): Promise<Portfolio> {
  return apiFetch<Portfolio>("/portfolio/refresh", { method: "POST" });
}

export async function getHistoricalData(
  ticker: string,
  range: TimeRange
): Promise<HistoricalDataPoint[]> {
  return apiFetch<HistoricalDataPoint[]>(
    `/market/history/${ticker}?range=${range}`
  );
}

export interface StockFundamental {
  ticker: string;
  market_cap?: string;
  pe_ratio?: string;
  book_value?: string;
  dividend_yield?: string;
  roce?: string;
  roe?: string;
  pros?: string;
  cons?: string;
}

export async function getFundamentals(): Promise<StockFundamental[]> {
  return apiFetch<StockFundamental[]>("/portfolio/fundamentals");
}

export async function refreshFundamentals(): Promise<{ status: string; updated: number }> {
  return apiFetch("/portfolio/fundamentals/refresh", { method: "POST" });
}
