import { apiFetch } from "./client";

// --- Types ---

export type SentimentScore = "bullish" | "bearish" | "neutral";
export type ImpactLevel = "high" | "medium" | "low";

export interface NewsItem {
  id: string;
  title: string;
  source_name: string;
  source_url: string | null;
  published_at: string;
  summary: string;
  sentiment_score: SentimentScore;
  impact_level: ImpactLevel;
  related_tickers: string[];
  relevance_score: number;
  is_stub: boolean;
  analyzed_at: string;
}

export interface PaginatedNewsResponse {
  items: NewsItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface NewsRefreshStatus {
  status: "started" | "in_progress" | "completed" | "failed";
  articles_fetched: number;
  articles_analyzed: number;
  last_refresh_at: string | null;
}

// --- Query Params ---

export interface NewsFeedParams {
  sentiment?: SentimentScore;
  impact_level?: ImpactLevel;
  ticker?: string;
  page?: number;
  page_size?: number;
}

// --- API Functions ---

export async function getNewsFeed(
  params: NewsFeedParams = {}
): Promise<PaginatedNewsResponse> {
  const searchParams = new URLSearchParams();

  if (params.sentiment) searchParams.set("sentiment", params.sentiment);
  if (params.impact_level) searchParams.set("impact_level", params.impact_level);
  if (params.ticker) searchParams.set("ticker", params.ticker);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));

  const query = searchParams.toString();
  const path = `/news${query ? `?${query}` : ""}`;

  return apiFetch<PaginatedNewsResponse>(path);
}

export async function triggerRefresh(): Promise<NewsRefreshStatus> {
  return apiFetch<NewsRefreshStatus>("/news/refresh", {
    method: "POST",
  });
}

// --- Briefing ---

export interface BriefingResponse {
  briefing: string;
  generated_at: string;
  is_stub: boolean;
  is_cached?: boolean;
  collection_date?: string;
  last_news_pull?: string | null;
  cache_message?: string | null;
  error_reason?: "rate_limited" | "error" | "disabled" | "no_data" | null;
  error_message?: string | null;
}

export interface LLMStatus {
  status: "operational" | "rate_limited" | "error" | "disabled";
  message: string;
  provider: string;
  model: string | null;
  rate_limited: boolean;
  retry_after: string | null;
  cooldown_remaining_seconds: number;
  last_error: string | null;
  last_error_at: string | null;
  calls_last_hour: number;
  total_calls_today: number;
  limits_info: {
    note: string;
    rpm: number;
    rpd: number;
    tpm: number;
  } | null;
}

export async function getPortfolioBriefing(): Promise<BriefingResponse> {
  return apiFetch<BriefingResponse>("/news/briefing");
}

export async function getLLMStatus(): Promise<LLMStatus> {
  return apiFetch<LLMStatus>("/telemetry/llm-status");
}
