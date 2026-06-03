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
