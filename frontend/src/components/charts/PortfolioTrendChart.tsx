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

export function PortfolioTrendChart() {
  const selectedTimeRange = useUIStore((s) => s.selectedTimeRange);
  // Use a portfolio-level ticker or aggregate; for now we show a placeholder
  const { data: history, isLoading } = useMarketData("PORTFOLIO", selectedTimeRange);

  if (isLoading) {
    return <div className="rounded-lg border bg-card p-4 h-64 animate-pulse" aria-busy="true" />;
  }

  if (!history || history.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground h-64 flex items-center justify-center">
        No trend data available for the selected range.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-medium mb-4">Portfolio Value Over Time</h3>
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
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
