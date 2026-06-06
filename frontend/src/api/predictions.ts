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
