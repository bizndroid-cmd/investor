import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { useActivePortfolio } from "@/contexts/PortfolioContext";
import { Layers } from "lucide-react";

interface NetWorthData {
  total_value: number;
  total_invested: number;
  total_gain_loss: number;
  gain_loss_pct: number;
  etf_value_inr: number;
  etf_value_usd: number;
  portfolios: {
    id: string;
    name: string;
    geo_id: string;
    currency_symbol: string;
    total_value: number;
    total_invested: number;
    total_gain_loss: number;
    gain_loss_pct: number;
  }[];
}

function formatCompact(value: number): string {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(2)} Cr`;
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(2)} L`;
  return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export function NetWorthCard() {
  const { isMultiPortfolio } = useActivePortfolio();

  const { data, isLoading } = useQuery({
    queryKey: ["net-worth"],
    queryFn: () => apiFetch<NetWorthData>("/portfolios/net-worth"),
    staleTime: 5 * 60_000,
    enabled: isMultiPortfolio,
  });

  if (!isMultiPortfolio || isLoading || !data) return null;

  const gainColor = data.total_gain_loss >= 0 ? "text-emerald-500" : "text-red-500";

  return (
    <div className="bento-card border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
      <div className="flex items-center gap-2 mb-3">
        <Layers className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-bold">Combined Net Worth</h3>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold">{formatCompact(data.total_value)}</span>
        <span className={`text-sm font-medium ${gainColor}`}>
          {data.total_gain_loss >= 0 ? "+" : ""}
          {data.gain_loss_pct.toFixed(2)}%
        </span>
      </div>

      <div className="mt-3 space-y-1.5">
        {data.portfolios.map((p) => (
          <div key={p.id} className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">{p.name}</span>
            <span className="font-medium">
              {p.currency_symbol}
              {p.total_value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            </span>
          </div>
        ))}
        {(data.etf_value_inr > 0 || data.etf_value_usd > 0) && (
          <div className="flex items-center justify-between text-xs border-t border-border/50 pt-1.5">
            <span className="text-muted-foreground">ETFs</span>
            <span className="font-medium">
              {data.etf_value_inr > 0 && `₹${data.etf_value_inr.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`}
              {data.etf_value_inr > 0 && data.etf_value_usd > 0 && " + "}
              {data.etf_value_usd > 0 && `$${data.etf_value_usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
