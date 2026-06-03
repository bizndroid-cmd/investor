import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useMarketData } from "@/hooks/useMarketData";
import { useUIStore } from "@/stores/uiStore";

interface PriceHistoryChartProps {
  ticker: string | null;
}

export function PriceHistoryChart({ ticker }: PriceHistoryChartProps) {
  const selectedTimeRange = useUIStore((s) => s.selectedTimeRange);
  const { data: history, isLoading, error, refetch } = useMarketData(ticker, selectedTimeRange);

  if (!ticker) {
    return (
      <div className="rounded-lg border bg-card p-4 h-64 flex items-center justify-center text-muted-foreground">
        Select a stock to view price history.
      </div>
    );
  }

  if (isLoading) {
    return <div className="rounded-lg border bg-card p-4 h-64 animate-pulse" aria-busy="true" />;
  }

  if (error || !history || history.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 h-64 flex flex-col items-center justify-center gap-2">
        <p className="text-muted-foreground">No price data available for {ticker}.</p>
        <button
          onClick={() => refetch()}
          className="text-sm text-primary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-medium mb-4">{ticker} Price History</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={history}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            fontSize={12}
            tickFormatter={(val) => new Date(val).toLocaleDateString()}
          />
          <YAxis fontSize={12} />
          <Tooltip
            labelFormatter={(val) => new Date(val).toLocaleDateString()}
            formatter={(value: number) =>
              new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value)
            }
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke="#7c3aed"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
