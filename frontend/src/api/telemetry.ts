const BASE_URL = `${import.meta.env.VITE_API_URL || "/api"}/telemetry`;

export interface TelemetryStats {
  uptime_seconds: number;
  started_at: string;
  llm: {
    total_calls: number;
    successful: number;
    failed: number;
    total_prompt_tokens: number;
    total_completion_tokens: number;
    total_tokens: number;
    avg_latency_ms: number;
    by_provider: Record<string, { total: number; tokens: number; success: number; failed: number }>;
  };
  api: {
    total_calls: number;
    successful: number;
    failed: number;
    avg_latency_ms: number;
    by_service: Record<string, { total: number; success: number; failed: number }>;
  };
}

export interface LLMCallLog {
  timestamp: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  purpose: string;
  success: boolean;
  error: string | null;
}

export interface APICallLog {
  timestamp: string;
  service: string;
  endpoint: string;
  method: string;
  status_code: number | null;
  latency_ms: number;
  success: boolean;
  error: string | null;
}

export async function verifyTelemetryPin(pin: string): Promise<boolean> {
  const response = await fetch(`${BASE_URL}/verify-pin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  });
  if (!response.ok) return false;
  const data = await response.json();
  return data.valid;
}

export async function fetchTelemetryStats(pin: string): Promise<TelemetryStats> {
  const response = await fetch(`${BASE_URL}/stats?pin=${encodeURIComponent(pin)}`);
  if (!response.ok) throw new Error("Failed to fetch stats");
  return response.json();
}

export async function fetchLLMCalls(pin: string, limit = 50): Promise<LLMCallLog[]> {
  const response = await fetch(`${BASE_URL}/llm-calls?pin=${encodeURIComponent(pin)}&limit=${limit}`);
  if (!response.ok) throw new Error("Failed to fetch LLM calls");
  return response.json();
}

export async function fetchAPICalls(pin: string, limit = 50): Promise<APICallLog[]> {
  const response = await fetch(`${BASE_URL}/api-calls?pin=${encodeURIComponent(pin)}&limit=${limit}`);
  if (!response.ok) throw new Error("Failed to fetch API calls");
  return response.json();
}
