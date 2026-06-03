import { apiFetch } from "./client";
import type { Order, OrderRequest, OrderFilters } from "./types";

export async function placeOrder(request: OrderRequest): Promise<Order> {
  return apiFetch<Order>("/orders", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getOrders(filters?: OrderFilters): Promise<Order[]> {
  const params = new URLSearchParams();
  if (filters?.broker_id) params.set("broker_id", filters.broker_id);
  if (filters?.ticker) params.set("ticker", filters.ticker);
  if (filters?.side) params.set("side", filters.side);
  if (filters?.status) params.set("status", filters.status);

  const query = params.toString();
  return apiFetch<Order[]>(`/orders${query ? `?${query}` : ""}`);
}

export async function getOrder(id: string): Promise<Order> {
  return apiFetch<Order>(`/orders/${id}`);
}
