import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { NewsItem as NewsItemType } from "@/api/news";

interface NewsItemProps {
  item: NewsItemType;
}

export function NewsItem({ item }: NewsItemProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="border rounded-lg p-4 hover:bg-accent/50 transition-colors cursor-pointer"
      onClick={() => setExpanded(!expanded)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setExpanded(!expanded);
        }
      }}
      aria-expanded={expanded}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <SentimentIndicator sentiment={item.sentiment_score} />
            <ImpactBadge impact={item.impact_level} />
          </div>
          <h3 className="font-medium text-sm leading-tight line-clamp-2">
            {item.title}
          </h3>
          <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
            <span>{item.source_name}</span>
            <span>·</span>
            <span>{getRelativeTime(item.published_at)}</span>
          </div>
        </div>
        <div className="flex-shrink-0 mt-1">
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t space-y-2">
          <p className="text-sm text-muted-foreground">{item.summary}</p>
          {item.related_tickers.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {item.related_tickers.map((ticker) => (
                <span
                  key={ticker}
                  className="inline-flex items-center rounded-full bg-accent px-2 py-0.5 text-xs font-medium"
                >
                  {ticker}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SentimentIndicator({ sentiment }: { sentiment: string }) {
  const config = {
    bullish: { color: "bg-green-500", label: "Bullish" },
    bearish: { color: "bg-red-500", label: "Bearish" },
    neutral: { color: "bg-gray-400", label: "Neutral" },
  }[sentiment] ?? { color: "bg-gray-400", label: "Neutral" };

  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium">
      <span
        className={`h-2 w-2 rounded-full ${config.color}`}
        aria-hidden="true"
      />
      {config.label}
    </span>
  );
}

function ImpactBadge({ impact }: { impact: string }) {
  const config = {
    high: "bg-red-100 text-red-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-gray-100 text-gray-600",
  }[impact] ?? "bg-gray-100 text-gray-600";

  const label = impact.charAt(0).toUpperCase() + impact.slice(1);

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${config}`}
    >
      {label}
    </span>
  );
}

function getRelativeTime(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.max(0, Math.floor(diffMs / 1000));

  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return date.toLocaleDateString();
}
