import { useUIStore, type TimeRange } from "@/stores/uiStore";

const ranges: TimeRange[] = ["1d", "1w", "1m", "3m", "1y", "5y"];

export function TimeRangeSelector() {
  const { selectedTimeRange, setTimeRange } = useUIStore();

  return (
    <div className="inline-flex rounded-md border" role="group" aria-label="Time range selector">
      {ranges.map((range) => (
        <button
          key={range}
          onClick={() => setTimeRange(range)}
          aria-pressed={selectedTimeRange === range}
          className={`px-3 py-1.5 text-sm font-medium transition-colors first:rounded-l-md last:rounded-r-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            selectedTimeRange === range
              ? "bg-primary text-primary-foreground"
              : "bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          }`}
        >
          {range.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
