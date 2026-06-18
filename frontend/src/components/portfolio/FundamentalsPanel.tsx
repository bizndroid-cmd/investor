import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getFundamentals, refreshFundamentals } from "@/api/portfolio";
import type { StockFundamental } from "@/api/portfolio";
import { RefreshCw, Loader2 } from "lucide-react";

export function FundamentalsPanel() {
  const queryClient = useQueryClient();
  const { data: fundamentals, isLoading } = useQuery({
    queryKey: ["fundamentals"],
    queryFn: getFundamentals,
    staleTime: 60 * 60 * 1000, // 1 hour
  });

  const refreshMutation = useMutation({
    mutationFn: refreshFundamentals,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["fundamentals"] });
    },
  });

  if (isLoading) {
    return (
      <div className="rounded-lg border bg-card p-4 animate-pulse">
        <div className="h-5 w-40 bg-muted rounded mb-4" />
        <div className="grid gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-muted rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!fundamentals || fundamentals.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground mb-3">
          No stock fundamentals loaded yet.
        </p>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {refreshMutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Load from Screener.in
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold">Stock Fundamentals</h3>
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          {refreshMutation.isPending ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          Refresh
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b">
            <tr className="text-muted-foreground">
              <th className="text-left py-2 pr-3 font-medium">Ticker</th>
              <th className="text-right py-2 px-2 font-medium">P/E</th>
              <th className="text-right py-2 px-2 font-medium">ROCE%</th>
              <th className="text-right py-2 px-2 font-medium">ROE%</th>
              <th className="text-right py-2 px-2 font-medium">Div%</th>
              <th className="text-left py-2 pl-3 font-medium">Key Signal</th>
            </tr>
          </thead>
          <tbody>
            {fundamentals.map((f) => (
              <FundamentalRow key={f.ticker} data={f} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground mt-3 italic">
        Data from screener.in · Refreshed weekly
      </p>
    </div>
  );
}

function FundamentalRow({ data }: { data: StockFundamental }) {
  const pe = parseFloat(data.pe_ratio || "0");
  const roce = parseFloat(data.roce || "0");
  const roe = parseFloat(data.roe || "0");

  // Simple signal logic
  let signal = "";
  let signalColor = "text-gray-500";

  if (roce > 20 && roe > 15 && pe < 25) {
    signal = "Strong fundamentals";
    signalColor = "text-green-600";
  } else if (roce > 15 || roe > 12) {
    signal = "Decent";
    signalColor = "text-emerald-600";
  } else if (pe > 40 && roe < 10) {
    signal = "Overvalued risk";
    signalColor = "text-red-500";
  } else if (pe > 30) {
    signal = "Premium valuation";
    signalColor = "text-amber-600";
  } else {
    signal = "Average";
    signalColor = "text-gray-500";
  }

  // Use pros/cons for a more specific signal
  if (data.cons && data.cons.includes("low return on equity")) {
    signal = "Low ROE ⚠️";
    signalColor = "text-amber-600";
  }
  if (data.pros && data.pros.includes("debt free")) {
    signal = "Debt-free ✓";
    signalColor = "text-green-600";
  }

  return (
    <tr className="border-b last:border-0 hover:bg-muted/30">
      <td className="py-2 pr-3 font-medium">{data.ticker}</td>
      <td className="py-2 px-2 text-right font-mono">
        <span className={pe > 35 ? "text-amber-600" : pe < 20 ? "text-green-600" : ""}>
          {data.pe_ratio || "—"}
        </span>
      </td>
      <td className="py-2 px-2 text-right font-mono">
        <span className={roce > 20 ? "text-green-600" : roce < 10 ? "text-red-500" : ""}>
          {data.roce || "—"}
        </span>
      </td>
      <td className="py-2 px-2 text-right font-mono">
        <span className={roe > 15 ? "text-green-600" : roe < 8 ? "text-red-500" : ""}>
          {data.roe || "—"}
        </span>
      </td>
      <td className="py-2 px-2 text-right font-mono">{data.dividend_yield || "—"}</td>
      <td className={`py-2 pl-3 ${signalColor} font-medium`}>{signal}</td>
    </tr>
  );
}
