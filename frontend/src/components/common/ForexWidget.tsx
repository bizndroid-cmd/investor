/**
 * Compact USD/INR rate badge for TopBar.
 * Shows live rate + daily change. Refreshes every 5 min.
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { TrendingUp, TrendingDown } from "lucide-react";

interface ForexRate {
  rate: number;
  previous_close: number;
  change: number;
  change_pct: number;
  high_52w: number;
  low_52w: number;
  timestamp: string;
  is_fallback?: boolean;
}

export function ForexBadge() {
  const { data } = useQuery({
    queryKey: ["forex-usdinr"],
    queryFn: () => apiFetch<ForexRate>("/market/forex/usdinr"),
    staleTime: 5 * 60_000,
    refetchInterval: 5 * 60_000,
  });

  if (!data || data.rate === 0) return null;

  const isUp = data.change >= 0;

  return (
    <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-secondary/50 text-[10px] font-medium">
      <span className="text-muted-foreground">$1 =</span>
      <span className="font-bold tabular-nums">₹{data.rate.toFixed(2)}</span>
      <span className={`flex items-center gap-0.5 ${isUp ? "text-red-500" : "text-emerald-500"}`}>
        {isUp ? <TrendingUp className="h-2.5 w-2.5" /> : <TrendingDown className="h-2.5 w-2.5" />}
        {Math.abs(data.change_pct).toFixed(2)}%
      </span>
    </div>
  );
}

/**
 * Detailed forex card for Market/Portfolio page.
 * Shows rate, 52w range, impact on USD holdings.
 */
export function ForexDetailCard({ usdHoldingsValue }: { usdHoldingsValue?: number }) {
  const { data } = useQuery({
    queryKey: ["forex-usdinr"],
    queryFn: () => apiFetch<ForexRate>("/market/forex/usdinr"),
    staleTime: 5 * 60_000,
  });

  if (!data || data.rate === 0) return null;

  const isUp = data.change >= 0;
  const inrEquivalent = usdHoldingsValue ? usdHoldingsValue * data.rate : null;
  const inrChange1Pct = usdHoldingsValue ? usdHoldingsValue * data.rate * 0.01 : null;

  // Position in 52w range (0-100)
  const range52w = data.high_52w - data.low_52w;
  const position52w = range52w > 0 ? ((data.rate - data.low_52w) / range52w) * 100 : 50;

  return (
    <div className="bento-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500/10 to-emerald-500/10 flex items-center justify-center">
            <span className="text-xs font-bold">₹$</span>
          </div>
          <div>
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">USD/INR</p>
            <p className="text-lg font-bold tabular-nums">₹{data.rate.toFixed(2)}</p>
          </div>
        </div>
        <div className={`text-right ${isUp ? "text-red-500" : "text-emerald-500"}`}>
          <p className="text-sm font-bold">{isUp ? "+" : ""}{data.change.toFixed(2)}</p>
          <p className="text-[10px]">{isUp ? "+" : ""}{data.change_pct.toFixed(2)}% today</p>
        </div>
      </div>

      {/* 52-week range bar */}
      <div className="mt-2">
        <div className="flex justify-between text-[9px] text-muted-foreground mb-1">
          <span>52W Low: ₹{data.low_52w}</span>
          <span>52W High: ₹{data.high_52w}</span>
        </div>
        <div className="relative h-1.5 rounded-full bg-muted">
          <div
            className="absolute top-0 h-full w-2 rounded-full bg-primary"
            style={{ left: `calc(${position52w}% - 4px)` }}
          />
        </div>
      </div>

      {/* Impact on USD holdings */}
      {inrEquivalent && inrChange1Pct && (
        <div className="mt-3 pt-3 border-t border-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Currency Impact</p>
          <div className="grid grid-cols-2 gap-3 mt-1.5">
            <div>
              <p className="text-xs text-muted-foreground">USD holdings in ₹</p>
              <p className="text-sm font-bold">₹{Math.round(inrEquivalent).toLocaleString("en-IN")}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">If ₹ weakens 1%</p>
              <p className="text-sm font-bold text-emerald-500">+₹{Math.round(inrChange1Pct).toLocaleString("en-IN")}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
