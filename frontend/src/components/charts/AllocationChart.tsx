import { useState, useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { usePortfolio } from "@/hooks/usePortfolio";

const COLORS = [
  "#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a",
  "#0891b2", "#4f46e5", "#c026d3", "#d97706", "#059669",
];

type ViewMode = "pie" | "bar";

export function AllocationChart() {
  const { data: portfolio } = usePortfolio();
  const [viewMode, setViewMode] = useState<ViewMode>("pie");

  const data = useMemo(() => {
    if (!portfolio || portfolio.holdings.length === 0) return [];
    const total = portfolio.total_value;
    return portfolio.holdings.map((h) => ({
      name: h.ticker,
      value: h.current_value,
      percent: total > 0 ? (h.current_value / total) * 100 : 0,
    }));
  }, [portfolio]);

  if (data.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground">
        No allocation data available.
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium">Portfolio Allocation</h3>
        <div className="inline-flex rounded-md border" role="group" aria-label="Chart view toggle">
          <button
            onClick={() => setViewMode("pie")}
            aria-pressed={viewMode === "pie"}
            className={`px-2 py-1 text-xs rounded-l-md ${
              viewMode === "pie" ? "bg-primary text-primary-foreground" : "bg-background"
            }`}
          >
            Pie
          </button>
          <button
            onClick={() => setViewMode("bar")}
            aria-pressed={viewMode === "bar"}
            className={`px-2 py-1 text-xs rounded-r-md ${
              viewMode === "bar" ? "bg-primary text-primary-foreground" : "bg-background"
            }`}
          >
            Bar
          </button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={250}>
        {viewMode === "pie" ? (
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={90}
              label={({ name, percent }) => `${name} ${percent.toFixed(1)}%`}
            >
              {data.map((_, index) => (
                <Cell key={index} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) =>
                new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value)
              }
            />
          </PieChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" fontSize={12} />
            <YAxis fontSize={12} />
            <Tooltip
              formatter={(value: number) =>
                new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value)
              }
            />
            <Bar dataKey="value">
              {data.map((_, index) => (
                <Cell key={index} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
