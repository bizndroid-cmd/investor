import { AlertTriangle, Clock, Loader2, Sparkles, Zap, XCircle } from "lucide-react";
import { useBriefing, useLLMStatus } from "@/hooks/useNews";

function formatBriefingText(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const trimmed = line.trim();

    // Bold headers (lines starting with **)
    if (trimmed.startsWith("**") && trimmed.endsWith("**")) {
      const content = trimmed.slice(2, -2);
      return (
        <p key={i} className="font-bold text-gray-900 mt-3 mb-1">
          {content}
        </p>
      );
    }

    // Bold prefix headers (e.g., **Label:** value)
    if (trimmed.startsWith("**") && trimmed.includes(":**")) {
      const boldEnd = trimmed.indexOf(":**") + 3;
      const boldPart = trimmed.slice(2, boldEnd - 3);
      const rest = trimmed.slice(boldEnd);
      return (
        <p key={i} className="mt-2">
          <span className="font-bold text-gray-900">{boldPart}:</span>
          {rest}
        </p>
      );
    }

    // Bullet points
    if (trimmed.startsWith("- ") || trimmed.startsWith("• ")) {
      const content = trimmed.slice(2);
      return (
        <li key={i} className="ml-4 text-gray-700">
          {content}
        </li>
      );
    }

    // Empty lines
    if (trimmed === "") {
      return <div key={i} className="h-2" />;
    }

    // Regular text
    return (
      <p key={i} className="text-gray-700">
        {line}
      </p>
    );
  });
}

export function PortfolioBriefing() {
  const { data, isLoading, isFetching, refetch } = useBriefing();
  const { data: llmStatus } = useLLMStatus();

  const handleGenerate = () => {
    refetch();
  };

  const isLLMAvailable = llmStatus?.status === "operational";
  const isRateLimited = llmStatus?.status === "rate_limited";
  const isLLMDisabled = llmStatus?.status === "disabled";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          📊 Daily Portfolio Briefing
        </h3>
        {data && !isFetching && isLLMAvailable && (
          <button
            onClick={handleGenerate}
            disabled={isFetching}
            className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
          >
            Regenerate
          </button>
        )}
      </div>

      {/* LLM Status Banner */}
      <LLMStatusBanner
        status={llmStatus?.status}
        message={llmStatus?.message}
        retryAfter={llmStatus?.retry_after}
        cooldownSeconds={llmStatus?.cooldown_remaining_seconds}
        limitsInfo={llmStatus?.limits_info}
      />

      {/* Error from last briefing attempt */}
      {data?.error_reason && data.error_reason !== "disabled" && (
        <BriefingErrorBanner
          reason={data.error_reason}
          message={data.error_message}
        />
      )}

      {/* Generate button when no data yet */}
      {!data && !isLoading && !isFetching && (
        <div className="text-center py-6">
          <p className="text-gray-500 mb-4">
            Get a personalized AI briefing based on your portfolio and today's
            market news.
          </p>
          <button
            onClick={handleGenerate}
            disabled={isLLMDisabled || isRateLimited}
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Sparkles className="h-4 w-4" />
            {isRateLimited ? "Rate Limited — Try Later" : isLLMDisabled ? "AI Not Configured" : "Generate Briefing"}
          </button>
        </div>
      )}

      {/* Loading state */}
      {(isLoading || isFetching) && !data && (
        <div className="flex items-center justify-center py-8 gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
          <span className="text-gray-600">
            Generating your personalized briefing...
          </span>
        </div>
      )}

      {/* Briefing content */}
      {data && (
        <div className="space-y-1">
          {/* Cache/source info banner */}
          {data.cache_message && (
            <div className="mb-3 rounded-md border border-blue-100 bg-blue-50 px-3 py-2">
              <p className="text-xs text-blue-700">{data.cache_message}</p>
            </div>
          )}

          <div className="prose prose-sm max-w-none">
            {formatBriefingText(data.briefing)}
          </div>

          <div className="mt-4 pt-3 border-t border-gray-100 space-y-1">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-xs text-gray-400">
                  Generated: {new Date(data.generated_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  {data.is_cached && " (cached)"}
                  {data.is_stub && " (fallback)"}
                </span>
                {data.provider && (
                  <span className="text-xs text-gray-400">
                    · AI: {data.provider}/{data.model}
                  </span>
                )}
                {data.articles_used && (
                  <span className="text-xs text-gray-400">
                    · {data.articles_used} articles analyzed
                  </span>
                )}
                {data.last_news_pull && (
                  <span className="text-xs text-gray-400">
                    · News from: {new Date(data.last_news_pull).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
              {isLLMAvailable && (
                <button
                  onClick={handleGenerate}
                  disabled={isFetching}
                  className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50"
                >
                  {isFetching ? "Generating..." : "↻ Regenerate"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LLMStatusBanner({
  status,
  message,
  cooldownSeconds,
  limitsInfo,
}: {
  status?: string;
  message?: string;
  retryAfter?: string | null;
  cooldownSeconds?: number;
  limitsInfo?: { note: string; rpm: number; rpd: number; tpm: number } | null;
}) {
  if (!status || status === "operational") return null;

  const config = {
    rate_limited: {
      icon: <Clock className="h-4 w-4 text-amber-600 shrink-0" />,
      bg: "bg-amber-50 border-amber-200",
      textColor: "text-amber-800",
    },
    error: {
      icon: <XCircle className="h-4 w-4 text-red-500 shrink-0" />,
      bg: "bg-red-50 border-red-200",
      textColor: "text-red-700",
    },
    disabled: {
      icon: <AlertTriangle className="h-4 w-4 text-gray-500 shrink-0" />,
      bg: "bg-gray-50 border-gray-200",
      textColor: "text-gray-600",
    },
  }[status] || {
    icon: <AlertTriangle className="h-4 w-4 text-gray-500 shrink-0" />,
    bg: "bg-gray-50 border-gray-200",
    textColor: "text-gray-600",
  };

  return (
    <div className={`mb-4 rounded-md border p-3 ${config.bg}`}>
      <div className="flex items-start gap-2">
        {config.icon}
        <div className="flex-1 min-w-0">
          <p className={`text-sm ${config.textColor}`}>{message}</p>
          {status === "rate_limited" && cooldownSeconds && cooldownSeconds > 0 && (
            <p className="text-xs text-amber-600 mt-1 font-medium">
              ⏱ Cooldown: {formatCooldown(cooldownSeconds)} remaining
            </p>
          )}
          {status === "rate_limited" && limitsInfo && (
            <p className="text-xs text-amber-600/70 mt-1">
              {limitsInfo.note} — {limitsInfo.rpm} req/min · {limitsInfo.rpd} req/day
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function formatCooldown(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function BriefingErrorBanner({
  reason,
  message,
}: {
  reason?: string | null;
  message?: string | null;
}) {
  if (!reason || !message) return null;

  const isRateLimit = reason === "rate_limited";

  return (
    <div
      className={`mb-4 rounded-md border p-3 ${
        isRateLimit ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200"
      }`}
    >
      <div className="flex items-start gap-2">
        {isRateLimit ? (
          <Zap className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
        ) : (
          <XCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
        )}
        <p
          className={`text-sm ${
            isRateLimit ? "text-amber-800" : "text-red-700"
          }`}
        >
          {message}
        </p>
      </div>
    </div>
  );
}
