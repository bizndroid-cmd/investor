import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from "recharts";
import { usePortfolio } from "@/hooks/usePortfolio";

export function GainLossChart() {
  const { data: portfolio } = usePortfolio();

  const data = useMemo(() => {
    if (!portfolio) return [];
    return portfolio.holdings.map((h) => ({
      name: h.ticker,
      gainLoss: h.gain_loss,
    }));
  }, [portfolio]);

  if (data.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground">
        No gain/loss data available.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-medium mb-4">Gain/Loss by Stock</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" fontSize={12} />
          <YAxis fontSize={12} />
          <Tooltip
            formatter={(value: number) =>
              new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value)
            }
          />
          <Bar dataKey="gainLoss">
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.gainLoss >= 0 ? "#16a34a" : "#dc2626"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
