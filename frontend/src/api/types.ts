export type BrokerId = "groww" | "zerodha" | "fidelity" | "robinhood";
export type TimeRange = "1d" | "1w" | "1m" | "3m" | "1y" | "5y";
export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit";
export type OrderStatus = "pending" | "filled" | "rejected" | "cancelled";
export type AlertCondition = "above" | "below";
export type AlertStatus = "active" | "triggered";
export type BrokerConnectionStatus = "connected" | "disconnected" | "error";

export interface NormalizedHolding {
  ticker: string;
  company_name: string;
  broker_id: BrokerId;
  quantity: number;
  avg_buy_price: number;
  current_price: number;
  current_value: number;
  gain_loss: number;
  gain_loss_percent: number;
  currency: string;
  last_updated: string;
}

export interface BrokerStatus {
  broker_id: BrokerId;
  status: BrokerConnectionStatus;
  last_successful_fetch: string | null;
  error_message: string | null;
}

export interface Portfolio {
  user_id: string;
  holdings: NormalizedHolding[];
  total_value: number;
  total_invested: number;
  total_gain_loss: number;
  total_gain_loss_percent: number;
  day_change: number;
  day_change_percent: number;
  broker_statuses: BrokerStatus[];
  last_refreshed: string;
}

export interface PriceQuote {
  ticker: string;
  price: number;
  previous_close: number;
  change: number;
  change_percent: number;
  timestamp: string;
  is_stale: boolean;
}

export interface HistoricalDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OrderRequest {
  broker_id: BrokerId;
  ticker: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  limit_price?: number | null;
}

export interface Order {
  id: string;
  user_id: string;
  broker_id: BrokerId;
  broker_order_id: string | null;
  ticker: string;
  order_type: OrderType;
  side: OrderSide;
  quantity: number;
  limit_price: number | null;
  execution_price: number | null;
  status: OrderStatus;
  rejection_reason: string | null;
  placed_at: string;
  updated_at: string;
}

export interface OrderFilters {
  broker_id?: BrokerId;
  ticker?: string;
  side?: OrderSide;
  status?: OrderStatus;
}

export interface Alert {
  id: string;
  user_id: string;
  ticker: string;
  target_price: number;
  condition: AlertCondition;
  status: AlertStatus;
  triggered_at: string | null;
  created_at: string;
  updated_at?: string;
}

export interface CreateAlertRequest {
  ticker: string;
  target_price: number;
  condition: AlertCondition;
}

export interface UpdateAlertRequest {
  target_price?: number;
  condition?: AlertCondition;
  status?: AlertStatus;
}

export interface BrokerInfo {
  broker_id: BrokerId;
  status: BrokerConnectionStatus;
  last_successful_fetch: string | null;
  error_message: string | null;
}
