import { apiFetch } from "@/api/client";

export interface ETFHolding {
  id: string;
  ticker: string;
  name: string;
  quantity: number;
  buy_price: number;
  buy_date: string | null;
  geo_id: string;
  currency: string;
  current_price: number;
  current_value: number;
  invested_value: number;
  gain_loss: number;
  gain_loss_pct: number;
  day_change: number;
  day_change_pct: number;
  category: string;
  expense_ratio: number | null;
}

export interface ETFListResponse {
  has_data: boolean;
  holdings: ETFHolding[];
  total_value_inr: number;
  total_value_usd: number;
}

export interface AddETFBody {
  ticker: string;
  quantity: number;
  buy_price: number;
  buy_date?: string;
  geo_id: string;
}

export interface UpdateETFBody {
  quantity?: number;
  buy_price?: number;
}

export interface ETFInsights {
  has_data: boolean;
  total_value_inr: number;
  total_value_usd: number;
  holdings_count: number;
  allocation: { category: string; value: number; percentage: number }[];
  best_performer: { ticker: string; gain_loss_pct: number } | null;
  worst_performer: { ticker: string; gain_loss_pct: number } | null;
  projections: {
    current_value: number;
    projected_1y: number | null;
    projected_3y: number | null;
    projected_5y: number | null;
    cagr_1y: number;
    cagr_3y: number;
    cagr_5y: number;
  };
}

export interface ETFDetail {
  id: string;
  ticker: string;
  name: string;
  geo_id: string;
  currency: string;
  quantity: number;
  buy_price: number;
  buy_date: string | null;
  current_price: number;
  day_change: number;
  day_change_pct: number;
  expense_ratio: number | null;
  category: string;
  fund_family: string;
  total_assets: number;
  tracking_index: string;
  returns: Record<string, number | null>;
  top_holdings: { symbol: string; name: string; weight: number }[];
}

export function getETFs(portfolioId?: string): Promise<ETFListResponse> {
  const params = portfolioId ? `?portfolio_id=${portfolioId}` : "";
  return apiFetch(`/etfs${params}`);
}

export function addETF(body: AddETFBody): Promise<{ id: string }> {
  return apiFetch("/etfs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateETF(id: string, body: UpdateETFBody): Promise<{ id: string }> {
  return apiFetch(`/etfs/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function deleteETF(id: string): Promise<void> {
  return apiFetch(`/etfs/${id}`, { method: "DELETE" });
}

export function getETFDetails(id: string): Promise<ETFDetail> {
  return apiFetch(`/etfs/${id}/details`);
}

export function getETFInsights(portfolioId?: string): Promise<ETFInsights> {
  const params = portfolioId ? `?portfolio_id=${portfolioId}` : "";
  return apiFetch(`/etfs/insights${params}`);
}


export interface ETFComparisonTicker {
  ticker: string;
  geo_id: string;
  is_mock: boolean;
}

export interface ETFComparisonResponse {
  has_data: boolean;
  tickers: ETFComparisonTicker[];
  chart_data: Record<string, any>[];
  start_date: string;
}

export function getETFComparison(
  portfolioId?: string,
  mockTicker?: string,
  mockGeoId?: string
): Promise<ETFComparisonResponse> {
  const params = new URLSearchParams();
  if (portfolioId) params.set("portfolio_id", portfolioId);
  if (mockTicker) params.set("mock_ticker", mockTicker);
  if (mockGeoId) params.set("mock_geo_id", mockGeoId);
  const query = params.toString();
  return apiFetch(`/etfs/comparison${query ? `?${query}` : ""}`);
}
