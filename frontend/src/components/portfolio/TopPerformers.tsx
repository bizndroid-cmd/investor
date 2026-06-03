import { useMemo } from "react";
import { usePortfolio } from "@/hooks/usePortfolio";
import { TrendingUp, TrendingDown } from "lucide-react";

function toNum(v: number | string): number {
  return typeof v === "string" ? parseFloat(v) || 0 : v || 0;
}

export function TopPerformers() {
  const { data: portfolio } = usePortfolio();

  const { top5, bottom5 } = useMemo(() => {
    if (!portfolio || portfolio.holdings.length === 0) {
      return { top5: [], bottom5: [] };
    }
    const sorted = [...portfolio.holdings].sort(
      (a, b) => toNum(b.gain_loss_percent) - toNum(a.gain_loss_percent)
    );
    return {
      top5: sorted.slice(0, 5),
      bottom5: sorted.slice(-5).reverse(),
    };
  }, [portfolio]);

  if (top5.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground">
        No performance data available.
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* Top 5 */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-green-600" aria-hidden="true" />
          Top Performers
        </h3>
        <ul className="space-y-2">
          {top5.map((h) => (
            <li key={`${h.broker_id}-${h.ticker}`} className="flex justify-between text-sm">
              <span className="font-medium">{h.ticker}</span>
              <span className="text-green-600">+{toNum(h.gain_loss_percent).toFixed(2)}%</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Bottom 5 */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
          <TrendingDown className="h-4 w-4 text-red-600" aria-hidden="true" />
          Bottom Performers
        </h3>
        <ul className="space-y-2">
          {bottom5.map((h) => (
            <li key={`${h.broker_id}-${h.ticker}`} className="flex justify-between text-sm">
              <span className="font-medium">{h.ticker}</span>
              <span className="text-red-600">{toNum(h.gain_loss_percent).toFixed(2)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
