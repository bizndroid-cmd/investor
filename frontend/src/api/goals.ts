import { apiFetch } from "./client";

export interface GoalProgress {
  id: string;
  name: string;
  target_amount: number;
  target_currency: string;
  deadline: string | null;
  icon: string;
  color: string;
  is_active: boolean;
  current_total: number;
  progress_pct: number;
  entries_total: number;
  stocks_value: number;
  etf_value: number;
  entries_count: number;
  months_to_goal: number | null;
}

export interface WealthEntry {
  id: string;
  category: string;
  label: string;
  amount: number;
  currency: string;
  entry_date: string;
  notes: string | null;
}

export interface WealthSummary {
  total_wealth_inr: number;
  total_wealth_usd: number;
  breakdown: { stocks_inr: number; etf_inr: number; manual_inr: number };
  categories: Record<string, number>;
}

export interface CreateGoalBody {
  name: string;
  target_amount: number;
  target_currency: string;
  deadline?: string;
  icon?: string;
  color?: string;
}

export interface AddEntryBody {
  goal_id?: string;
  category: string;
  label: string;
  amount: number;
  currency: string;
  entry_date: string;
  notes?: string;
}

export function getGoals(): Promise<GoalProgress[]> {
  return apiFetch("/goals");
}

export function createGoal(body: CreateGoalBody): Promise<{ id: string }> {
  return apiFetch("/goals", { method: "POST", body: JSON.stringify(body) });
}

export function updateGoal(id: string, body: Partial<CreateGoalBody & { is_active: boolean }>): Promise<any> {
  return apiFetch(`/goals/${id}`, { method: "PUT", body: JSON.stringify(body) });
}

export function deleteGoal(id: string): Promise<void> {
  return apiFetch(`/goals/${id}`, { method: "DELETE" });
}

export function getGoalEntries(goalId: string): Promise<WealthEntry[]> {
  return apiFetch(`/goals/${goalId}/entries`);
}

export function addEntry(body: AddEntryBody): Promise<{ id: string }> {
  return apiFetch("/goals/entries", { method: "POST", body: JSON.stringify(body) });
}

export function deleteEntry(id: string): Promise<void> {
  return apiFetch(`/goals/entries/${id}`, { method: "DELETE" });
}

export function getWealthSummary(): Promise<WealthSummary> {
  return apiFetch("/goals/summary");
}
