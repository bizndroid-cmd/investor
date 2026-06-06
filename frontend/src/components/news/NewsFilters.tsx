import type { SentimentScore, ImpactLevel } from "@/api/news";

export interface NewsFilterState {
  sentiment?: SentimentScore;
  impact_level?: ImpactLevel;
  source_type?: "rss" | "newsapi_ai";
}

interface NewsFiltersProps {
  filters: NewsFilterState;
  onChange: (filters: NewsFilterState) => void;
}

const sentimentOptions: { value: SentimentScore | undefined; label: string }[] = [
  { value: undefined, label: "All" },
  { value: "bullish", label: "Bullish" },
  { value: "bearish", label: "Bearish" },
  { value: "neutral", label: "Neutral" },
];

const impactOptions: { value: ImpactLevel | undefined; label: string }[] = [
  { value: undefined, label: "All" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const sourceOptions: { value: "rss" | "newsapi_ai" | undefined; label: string }[] = [
  { value: undefined, label: "All Sources" },
  { value: "rss", label: "RSS Feeds" },
  { value: "newsapi_ai", label: "NewsAPI.ai" },
];

export function NewsFilters({ filters, onChange }: NewsFiltersProps) {
  return (
    <div className="space-y-3">
      {/* Source filter */}
      <div>
        <span className="text-xs font-medium text-muted-foreground mr-2">
          Source:
        </span>
        <div className="inline-flex gap-1">
          {sourceOptions.map((opt) => (
            <button
              key={opt.label}
              onClick={() => onChange({ ...filters, source_type: opt.value })}
              className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
                filters.source_type === opt.value
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sentiment filter */}
      <div>
        <span className="text-xs font-medium text-muted-foreground mr-2">
          Sentiment:
        </span>
        <div className="inline-flex gap-1">
          {sentimentOptions.map((opt) => (
            <button
              key={opt.label}
              onClick={() => onChange({ ...filters, sentiment: opt.value })}
              className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
                filters.sentiment === opt.value
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Impact filter */}
      <div>
        <span className="text-xs font-medium text-muted-foreground mr-2">
          Impact:
        </span>
        <div className="inline-flex gap-1">
          {impactOptions.map((opt) => (
            <button
              key={opt.label}
              onClick={() => onChange({ ...filters, impact_level: opt.value })}
              className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
                filters.impact_level === opt.value
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
