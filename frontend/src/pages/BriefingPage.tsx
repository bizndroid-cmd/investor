import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { useBriefing, useLLMStatus } from "@/hooks/useNews";
import {
  FileText, Clock, Loader2, Sparkles, ChevronDown, ChevronUp,
  Calendar, AlertTriangle, Zap, XCircle,
} from "lucide-react";

interface BriefingHistoryItem {
  id: string;
  collection_date: string;
  briefing_text: string;
  provider: string;
  model: string;
  articles_used: number;
  generated_at: string | null;
}

async function getBriefingHistory(): Promise<BriefingHistoryItem[]> {
  return apiFetch("/news/briefing/history?days=30");
}

export function BriefingPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <FileText className="h-6 w-6 text-blue-500" />
          Portfolio Briefing
        </h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          AI-generated daily analysis combining your holdings, market news, fundamentals, and prediction accuracy into one actionable brief. Generated at 9:30 AM and 8:00 PM IST.
        </p>
      </div>

      <TodaysBriefing />
      <BriefingHistory />
    </div>
  );
}

// ============================================================
// TODAY'S BRIEFING
// ============================================================
function TodaysBriefing() {
  const { data, isLoading, isFetching, refetch } = useBriefing();
  const { data: llmStatus } = useLLMStatus();

  const isLLMAvailable = llmStatus?.status === "operational";
  const isRateLimited = llmStatus?.status === "rate_limited";
  const isLLMDisabled = llmStatus?.status === "disabled";

  return (
    <div className="bento-card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-bold">Today's Briefing</h3>
        </div>
        {data && !isFetching && isLLMAvailable && (
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="text-xs text-primary hover:text-primary/80 transition-colors disabled:opacity-50"
          >
            ↻ Regenerate
          </button>
        )}
      </div>

      {/* LLM Status Banner */}
      {llmStatus && llmStatus.status !== "operational" && (
        <LLMStatusBanner
          status={llmStatus.status}
          message={llmStatus.message}
          cooldownSeconds={llmStatus.cooldown_remaining_seconds}
          limitsInfo={llmStatus.limits_info}
        />
      )}

      {/* Error */}
      {data?.error_reason && data.error_reason !== "disabled" && (
        <BriefingErrorBanner reason={data.error_reason} message={data.error_message} />
      )}

      {/* Generate button when no data */}
      {!data && !isLoading && !isFetching && (
        <div className="text-center py-8">
          <FileText className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground mb-4">
            Get a personalized AI briefing based on your portfolio and today's market news.
          </p>
          <button
            onClick={() => refetch()}
            disabled={isLLMDisabled || isRateLimited}
            className="btn-primary"
          >
            <Sparkles className="h-4 w-4 mr-2" />
            {isRateLimited ? "Rate Limited" : isLLMDisabled ? "AI Not Configured" : "Generate Briefing"}
          </button>
        </div>
      )}

      {/* Loading */}
      {(isLoading || isFetching) && !data && (
        <div className="flex items-center justify-center py-10 gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">Generating your briefing...</span>
        </div>
      )}

      {/* Content */}
      {data && data.briefing && (
        <div className="space-y-1">
          {data.cache_message && (
            <div className="mb-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
              <p className="text-xs text-primary">{data.cache_message}</p>
            </div>
          )}

          <div className="prose-content">
            {formatBriefingText(data.briefing)}
          </div>

          <div className="mt-4 pt-3 border-t border-border flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3 flex-wrap text-[11px] text-muted-foreground">
              {data.generated_at && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {new Date(data.generated_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  {data.is_cached && " (cached)"}
                </span>
              )}
              {data.provider && (
                <span>AI: {data.provider}/{data.model}</span>
              )}
              {data.articles_used && (
                <span>{data.articles_used} articles analyzed</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// BRIEFING HISTORY
// ============================================================
function BriefingHistory() {
  const { data: history, isLoading } = useQuery({
    queryKey: ["briefing-history"],
    queryFn: getBriefingHistory,
    staleTime: 5 * 60 * 1000,
  });

  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="bento-card">
        <div className="h-5 w-40 skeleton rounded mb-4" />
        <div className="space-y-2">
          <div className="h-12 skeleton-shimmer rounded-lg" />
          <div className="h-12 skeleton-shimmer rounded-lg" />
          <div className="h-12 skeleton-shimmer rounded-lg" />
        </div>
      </div>
    );
  }

  if (!history || history.length === 0) {
    return (
      <div className="bento-card">
        <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          Past Briefings
        </h3>
        <div className="text-center py-6 text-sm text-muted-foreground">
          <Calendar className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p>No past briefings found</p>
          <p className="text-xs mt-1 text-muted-foreground/70">
            Briefings are generated daily and stored for your reference
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        Past Briefings
        <span className="text-xs font-normal text-muted-foreground">
          ({history.length} in last 30 days)
        </span>
      </h3>

      <div className="space-y-2">
        {history.map((item) => {
          const isExpanded = expandedId === item.id;
          const dateStr = new Date(item.collection_date + "T00:00:00").toLocaleDateString([], {
            weekday: "short", month: "short", day: "numeric",
          });

          return (
            <div key={item.id} className="rounded-lg border transition-colors hover:border-primary/20">
              <button
                onClick={() => setExpandedId(isExpanded ? null : item.id)}
                className="w-full flex items-center justify-between p-3 text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{dateStr}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {item.provider}/{item.model} · {item.articles_used} articles
                    </p>
                  </div>
                </div>
                {isExpanded ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
              </button>

              {isExpanded && (
                <div className="px-3 pb-4 pt-1 border-t animate-fade-in">
                  <div className="prose-content mt-2">
                    {formatBriefingText(item.briefing_text)}
                  </div>
                  {item.generated_at && (
                    <p className="text-[10px] text-muted-foreground mt-3 pt-2 border-t border-border">
                      Generated: {new Date(item.generated_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// HELPERS
// ============================================================

function formatBriefingText(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const trimmed = line.trim();

    if (trimmed.startsWith("**") && trimmed.endsWith("**")) {
      const content = trimmed.slice(2, -2);
      return <p key={i} className="font-bold mt-3 mb-1">{content}</p>;
    }

    if (trimmed.startsWith("**") && trimmed.includes(":**")) {
      const boldEnd = trimmed.indexOf(":**") + 3;
      const boldPart = trimmed.slice(2, boldEnd - 3);
      const rest = trimmed.slice(boldEnd);
      return (
        <p key={i} className="mt-2">
          <span className="font-bold">{boldPart}:</span>
          <span className="text-muted-foreground">{rest}</span>
        </p>
      );
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
      const content = trimmed.slice(2);
      return <li key={i} className="ml-4 text-sm text-muted-foreground">{content}</li>;
    }

    if (trimmed === "") return <div key={i} className="h-2" />;

    return <p key={i} className="text-sm text-card-foreground/80">{line}</p>;
  });
}

function LLMStatusBanner({
  status,
  message,
  cooldownSeconds,
}: {
  status: string;
  message: string;
  cooldownSeconds?: number;
  limitsInfo?: { note: string; rpm: number; rpd: number; tpm: number } | null;
}) {
  const isRateLimit = status === "rate_limited";
  return (
    <div className={`mb-4 rounded-lg border p-3 ${
      isRateLimit ? "bg-amber-500/5 border-amber-500/20" : "bg-red-500/5 border-red-500/20"
    }`}>
      <div className="flex items-start gap-2">
        {isRateLimit ? (
          <Clock className="h-4 w-4 text-amber-500 shrink-0" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-red-500 shrink-0" />
        )}
        <div>
          <p className="text-xs">{message}</p>
          {isRateLimit && cooldownSeconds && cooldownSeconds > 0 && (
            <p className="text-[11px] text-amber-500 mt-1">
              Cooldown: {cooldownSeconds < 60 ? `${cooldownSeconds}s` : `${Math.floor(cooldownSeconds / 60)}m`} remaining
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function BriefingErrorBanner({ reason, message }: { reason?: string | null; message?: string | null }) {
  if (!reason || !message) return null;
  const isRateLimit = reason === "rate_limited";
  return (
    <div className={`mb-4 rounded-lg border p-3 ${
      isRateLimit ? "bg-amber-500/5 border-amber-500/20" : "bg-red-500/5 border-red-500/20"
    }`}>
      <div className="flex items-start gap-2">
        {isRateLimit ? (
          <Zap className="h-4 w-4 text-amber-500 shrink-0" />
        ) : (
          <XCircle className="h-4 w-4 text-red-500 shrink-0" />
        )}
        <p className="text-xs">{message}</p>
      </div>
    </div>
  );
}
