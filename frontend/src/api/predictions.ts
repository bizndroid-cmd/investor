import { apiFetch } from "./client";

export interface PredictionEntry {
  prediction_date: string;
  market_mood: string;
  confidence_score: number | null;
  mood_accuracy: number | null;
  ticker_accuracy: number | null;
  provider: string;
  model: string;
  scored: boolean;
}

export interface PredictionAverage {
  average_score: number | null;
  total_predictions: number;
  scored_predictions: number;
  highest_score?: number;
  lowest_score?: number;
  days: number;
}

export async function getPredictionHistory(days = 30): Promise<PredictionEntry[]> {
  return apiFetch<PredictionEntry[]>(`/predictions/history?days=${days}`);
}

export async function getPredictionAverage(days = 30): Promise<PredictionAverage> {
  return apiFetch<PredictionAverage>(`/predictions/average?days=${days}`);
}

export async function computePredictionScore(date: string): Promise<any> {
  return apiFetch(`/predictions/compute-score?prediction_date=${date}`, {
    method: "POST",
  });
}

export interface TodayPrediction {
  has_prediction: boolean;
  prediction_date?: string;
  market_mood?: string;
  market_mood_reason?: string;
  ticker_predictions?: Array<{
    ticker: string;
    sentiment: string;
    expected_direction: string;
    confidence: string;
    reason: string;
  }>;
  suggestions?: string[];
  confidence_score?: number | null;
  scored?: boolean;
  provider?: string;
  model?: string;
}

export interface PortfolioImpact {
  has_data: boolean;
  period_days?: number;
  actual_change?: number;
  actual_change_pct?: number;
  hypothetical_change?: number;
  hypothetical_change_pct?: number;
  ai_edge?: number;
  ai_edge_pct?: number;
  correct_calls?: number;
  total_calls?: number;
  accuracy_rate?: number;
  start_value?: number;
  end_value?: number;
}

export interface CalendarEntry {
  date: string;
  mood: string;
  score: number | null;
  scored: boolean;
}

export async function getTodayPrediction(): Promise<TodayPrediction> {
  return apiFetch<TodayPrediction>("/predictions/today");
}

export async function getPortfolioImpact(): Promise<PortfolioImpact> {
  return apiFetch<PortfolioImpact>("/predictions/impact");
}

export async function getMoodCalendar(days = 30): Promise<CalendarEntry[]> {
  return apiFetch<CalendarEntry[]>(`/predictions/calendar?days=${days}`);
}
