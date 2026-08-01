import { apiFetch } from "./client";
import type { Portfolio, NormalizedHolding, HistoricalDataPoint, TimeRange } from "./types";

export async function getPortfolio(portfolioId?: string): Promise<Portfolio> {
  const params = portfolioId ? `?portfolio_id=${portfolioId}` : "";
  return apiFetch<Portfolio>(`/portfolio${params}`);
}

export async function getHoldings(brokerId?: string, portfolioId?: string): Promise<NormalizedHolding[]> {
  const searchParams = new URLSearchParams();
  if (brokerId) searchParams.set("broker_id", brokerId);
  if (portfolioId) searchParams.set("portfolio_id", portfolioId);
  const query = searchParams.toString();
  return apiFetch<NormalizedHolding[]>(`/portfolio/holdings${query ? `?${query}` : ""}`);
}

export async function refreshPortfolio(portfolioId?: string): Promise<Portfolio> {
  const params = portfolioId ? `?portfolio_id=${portfolioId}` : "";
  return apiFetch<Portfolio>(`/portfolio/refresh${params}`, { method: "POST" });
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

export async function getFundamentals(portfolioId?: string): Promise<StockFundamental[]> {
  const params = portfolioId ? `?portfolio_id=${portfolioId}` : "";
  return apiFetch<StockFundamental[]>(`/portfolio/fundamentals${params}`);
}

export async function refreshFundamentals(portfolioId?: string): Promise<{ status: string; updated: number }> {
  const params = portfolioId ? `?portfolio_id=${portfolioId}` : "";
  return apiFetch(`/portfolio/fundamentals/refresh${params}`, { method: "POST" });
}
