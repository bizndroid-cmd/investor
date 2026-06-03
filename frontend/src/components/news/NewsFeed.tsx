import { useState, useEffect } from "react";
import { RefreshCw, Loader2, Sparkles, CheckCircle2, Database, Wifi, AlertTriangle } from "lucide-react";
import { useNews, useRefreshNews, useLLMStatus } from "@/hooks/useNews";
import { NewsItem } from "./NewsItem";
import { NewsFilters, type NewsFilterState } from "./NewsFilters";

type RefreshStage = "idle" | "confirming" | "fetching" | "analyzing" | "done";

export function NewsFeed() {
  const [filters, setFilters] = useState<NewsFilterState>({});
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useNews({ ...filters, page, page_size: 20 });
  const refreshMutation = useRefreshNews();
  const { data: llmStatus } = useLLMStatus();
  const [stage, setStage] = useState<RefreshStage>("idle");
  const [articlesFetched, setArticlesFetched] = useState(0);

  // Reset to page 1 when filters change
  const handleFilterChange = (newFilters: NewsFilterState) => {
    setFilters(newFilters);
    setPage(1);
  };

  // Handle refresh stages
  useEffect(() => {
    if (refreshMutation.isPending) {
      setStage("fetching");
    } else if (refreshMutation.isSuccess && refreshMutation.data) {
      const fetched = refreshMutation.data.articles_fetched ?? 0;
      setArticlesFetched(fetched);
      if (fetched > 0) {
        setStage("analyzing");
        refetch();
        const interval = setInterval(() => refetch(), 5000);
        const timeout = setTimeout(() => {
          clearInterval(interval);
          setStage("done");
          setTimeout(() => setStage("idle"), 3000);
        }, 120000);
        return () => {
          clearInterval(interval);
          clearTimeout(timeout);
        };
      } else {
        setStage("done");
        setTimeout(() => setStage("idle"), 3000);
      }
    }
  }, [refreshMutation.isPending, refreshMutation.isSuccess, refreshMutation.data]);

  const handleRefreshClick = () => {
    setStage("confirming");
  };

  const handleConfirmRefresh = () => {
    setStage("fetching");
    refreshMutation.mutate();
  };

  const handleCancelRefresh = () => {
    setStage("idle");
  };

  const analyzedCount = data?.items.filter(
    (i) => i.summary && i.summary !== i.title
  ).length ?? 0;
  const totalCount = data?.total ?? 0;

  return (
    <div className="space-y-4">
      {/* Header with data source info */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Data source indicator */}
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-xs text-emerald-700">
            <Database className="h-3 w-3" />
            From stored data
          </span>
          {data && data.total > 0 && (
            <span className="text-xs text-muted-foreground">
              {data.total} articles
              {data.items.length > 0 && (
                <> · News pulled last on: {new Date(data.items[0].published_at).toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" })}</>
              )}
            </span>
          )}
          {isError && (
            <span className="text-xs text-red-500">
              Failed to load — showing cached data
            </span>
          )}
        </div>

        {/* Pull Fresh News button */}
        <button
          onClick={handleRefreshClick}
          disabled={stage === "fetching" || stage === "analyzing"}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border hover:bg-accent transition-colors disabled:opacity-50"
        >
          {stage === "fetching" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Wifi className="h-3.5 w-3.5" />
          )}
          Pull Fresh News
        </button>
      </div>

      {/* Refresh confirmation dialog */}
      {stage === "confirming" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800">
                Pull fresh news from live sources?
              </p>
              <p className="text-xs text-amber-700 mt-1">
                This will fetch articles from RSS feeds and use AI tokens to analyze them.
                {llmStatus?.status === "rate_limited" && (
                  <span className="font-medium"> ⚠️ AI is currently rate-limited — articles will be stored but analysis may be delayed.</span>
                )}
                {llmStatus?.status === "operational" && (
                  <span> Estimated cost: ~10 API calls for sentiment analysis.</span>
                )}
              </p>
              <p className="text-xs text-amber-600 mt-1">
                💡 Tip: Use the date and filter options below to browse stored news for free.
              </p>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={handleConfirmRefresh}
                  className="inline-flex items-center gap-1 rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700"
                >
                  <Wifi className="h-3 w-3" />
                  Yes, pull fresh news
                </button>
                <button
                  onClick={handleCancelRefresh}
                  className="rounded-md border border-amber-300 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Background process status banner */}
      {(stage === "fetching" || stage === "analyzing" || stage === "done") && (
        <ProcessBanner
          stage={stage}
          articlesFetched={articlesFetched}
          analyzedCount={analyzedCount}
          totalCount={totalCount}
        />
      )}

      {/* Filters */}
      <NewsFilters filters={filters} onChange={handleFilterChange} />

      {/* Content */}
      {isLoading ? (
        <LoadingSkeleton />
      ) : !data || data.items.length === 0 ? (
        <EmptyState onRefresh={handleRefreshClick} />
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Page {data.page} · Showing {data.items.length} of {data.total} articles
            </p>
          </div>
          <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
            {data.items.map((item) => (
              <NewsItem key={item.id} item={item} />
            ))}
          </div>
          {/* Pagination */}
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-xs font-medium rounded-md border hover:bg-accent disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ← Previous
            </button>
            <span className="text-xs text-muted-foreground">
              Page {page} of {Math.ceil(data.total / 20)}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!data.has_next}
              className="px-3 py-1.5 text-xs font-medium rounded-md border hover:bg-accent disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function ProcessBanner({
  stage,
  articlesFetched,
  analyzedCount,
  totalCount,
}: {
  stage: RefreshStage;
  articlesFetched: number;
  analyzedCount: number;
  totalCount: number;
}) {
  if (stage === "fetching") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm text-blue-700">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Fetching latest news from Economic Times, LiveMint, Moneycontrol...</span>
      </div>
    );
  }

  if (stage === "analyzing") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-700">
        <Sparkles className="h-4 w-4 animate-pulse" />
        <span>
          AI is analyzing {articlesFetched} articles for sentiment &amp; relevance...
          {analyzedCount > 0 && (
            <span className="ml-1 font-medium">
              ({analyzedCount}/{totalCount} done)
            </span>
          )}
        </span>
      </div>
    );
  }

  if (stage === "done") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-2.5 text-sm text-green-700">
        <CheckCircle2 className="h-4 w-4" />
        <span>
          {articlesFetched > 0
            ? `Done! ${articlesFetched} articles fetched and stored.`
            : "No new articles found."}
        </span>
      </div>
    );
  }

  return null;
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3" aria-label="Loading news">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="border rounded-lg p-4 animate-pulse">
          <div className="flex gap-2 mb-2">
            <div className="h-4 w-16 bg-accent rounded" />
            <div className="h-4 w-12 bg-accent rounded" />
          </div>
          <div className="h-4 w-3/4 bg-accent rounded mb-2" />
          <div className="h-3 w-1/3 bg-accent rounded" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="text-center py-12 text-muted-foreground">
      <p className="text-sm mb-3">
        No news articles found for the selected filters.
      </p>
      <p className="text-xs mb-4">
        Try adjusting your filters or pull fresh news from live sources.
      </p>
      <button
        onClick={onRefresh}
        className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent"
      >
        <Wifi className="h-3.5 w-3.5" />
        Pull Fresh News
      </button>
    </div>
  );
}
