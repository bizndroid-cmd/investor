import { useMemo, useState } from "react";
import { Wifi, Loader2, AlertTriangle, PieChart as PieChartIcon } from "lucide-react";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { TopPerformers } from "@/components/portfolio/TopPerformers";
import { FundamentalsPanel } from "@/components/portfolio/FundamentalsPanel";
import { NetWorthCard } from "@/components/portfolio/NetWorthCard";
import { WhatIfSimulator } from "@/components/market/WhatIfSimulator";
import { RemittanceTracker } from "@/components/market/RemittanceTracker";
import { usePortfolio, useRefreshPortfolio } from "@/hooks/usePortfolio";
import { usePriceSocket } from "@/hooks/usePriceSocket";
import { useGeo } from "@/contexts/GeoContext";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

// Sector map — will be moved to backend-driven in future
// For now kept in frontend for the donut chart
const SECTOR_MAP: Record<string, string> = {
  RELIANCE: "Energy", ONGC: "Energy", IOC: "Energy", TATAPOWER: "Energy",
  HDFCBANK: "Banking", IDFCFIRSTB: "Banking", PNB: "Banking", YESBANK: "Banking",
  TCS: "IT", WIPRO: "IT",
  LT: "Engineering", BHEL: "Engineering", RANEHOLDIN: "Engineering",
  ITC: "FMCG",
  ITCHOTELS: "Hospitality",
  ADANIPORTS: "Infrastructure", BIBCL: "Infrastructure",
  ASHOKLEY: "Auto", MOTHERSON: "Auto", EXIDEIND: "Auto", MSUMI: "Auto", TMPV: "Auto", TMCV: "Auto",
  JIOFIN: "Financials",
  SERVOTECH: "Technology",
  PENIND: "Chemicals",
  VEDL: "Mining",
};

const SECTOR_COLORS: Record<string, string> = {
  Energy: "#f59e0b", Banking: "#3b82f6", IT: "#8b5cf6", Engineering: "#6366f1",
  FMCG: "#10b981", Hospitality: "#ec4899", Infrastructure: "#14b8a6",
  Auto: "#ef4444", Financials: "#0ea5e9", Technology: "#a855f7",
  Chemicals: "#f97316", Mining: "#84cc16", Other: "#6b7280",
};

function formatCurrency(value: number | string, symbol: string = "₹", locale: string = "en-IN"): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  const code = symbol === "$" ? "USD" : "INR";
  return new Intl.NumberFormat(locale, { style: "currency", currency: code, maximumFractionDigits: 0 }).format(num || 0);
}

function formatPercent(value: number | string): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return `${num >= 0 ? "+" : ""}${(num || 0).toFixed(2)}%`;
}

export function PortfolioPage() {
  const { data: portfolio } = usePortfolio();
  const refreshMutation = useRefreshPortfolio();
  const [showConfirm, setShowConfirm] = useState(false);

  const tickers = useMemo(
    () => portfolio?.holdings.map((h) => h.ticker) ?? [],
    [portfolio]
  );

  usePriceSocket(tickers);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold">Portfolio</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Based on equity owned as seen in the Groww brokerage app
          </p>
        </div>
        <div className="flex items-center gap-3">
          {portfolio && (
            <span className="text-xs text-muted-foreground">
              Last pulled: {new Date(portfolio.last_refreshed).toLocaleString([], {
                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
              })}
            </span>
          )}
          <button
            onClick={() => setShowConfirm(true)}
            disabled={refreshMutation.isPending}
            className="btn-ghost text-xs border"
          >
            {refreshMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
            ) : (
              <Wifi className="h-3.5 w-3.5 mr-1.5" />
            )}
            Pull from Broker
          </button>
        </div>
      </div>

      {/* Refresh confirmation */}
      {showConfirm && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4 animate-fade-in">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium">Refresh from broker API?</p>
              <p className="text-xs text-muted-foreground mt-1">
                Live call to Groww. Overwrites today's stored snapshot.
              </p>
              <div className="flex gap-2 mt-3">
                <button onClick={() => { setShowConfirm(false); refreshMutation.mutate(); }} className="btn-primary text-xs py-1.5">
                  Yes, pull fresh
                </button>
                <button onClick={() => setShowConfirm(false)} className="btn-ghost text-xs">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main layout: Left = charts/content, Right = summary cards + performers */}
      <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
        {/* LEFT COLUMN */}
        <div className="space-y-6">
          {/* Sector allocation + Diversification */}
          <SectorAllocationCard />

          {/* Fundamentals */}
          <FundamentalsPanel />

          {/* Holdings table */}
          <HoldingsTable />

          {/* Cross-market comparison */}
          <WhatIfSimulator />

          {/* Remittance tracker */}
          <RemittanceTracker />
        </div>

        {/* RIGHT COLUMN — summary stat cards + performers stacked */}
        <div className="space-y-3 lg:sticky lg:top-20 lg:self-start">
          <NetWorthCard />
          <SummaryCards />
          <TopPerformers />
        </div>
      </div>
    </div>
  );
}

// ============================================================
// SUMMARY CARDS (stacked vertically on right)
// ============================================================
function SummaryCards() {
  const { data: portfolio, isLoading } = usePortfolio();
  const { currencySymbol, locale } = useGeo();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bento-card h-20 skeleton-shimmer" />
        ))}
      </div>
    );
  }

  if (!portfolio) return null;

  const cards = [
    {
      label: "Market Value",
      value: formatCurrency(portfolio.total_value, currencySymbol, locale),
      sub: null,
      color: "",
    },
    {
      label: "Invested",
      value: formatCurrency(portfolio.total_invested, currencySymbol, locale),
      sub: null,
      color: "",
    },
    {
      label: "Total P&L",
      value: formatCurrency(portfolio.total_gain_loss, currencySymbol, locale),
      sub: formatPercent(portfolio.total_gain_loss_percent),
      color: Number(portfolio.total_gain_loss) >= 0 ? "text-emerald-500" : "text-red-500",
    },
  ];

  return (
    <div className="space-y-3 stagger-children">
      {cards.map((card) => (
        <div key={card.label} className="bento-card">
          <p className="text-[11px] text-muted-foreground uppercase tracking-wide">{card.label}</p>
          <p className={`text-lg font-bold mt-1 ${card.color}`}>{card.value}</p>
          {card.sub && (
            <p className={`text-xs font-medium mt-0.5 ${card.color}`}>{card.sub}</p>
          )}
        </div>
      ))}

      {/* Holdings count mini stat */}
      <div className="bento-card">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide">Holdings</p>
        <p className="text-lg font-bold mt-1">{portfolio.holdings.length}</p>
        <p className="text-xs text-muted-foreground mt-0.5">stocks tracked</p>
      </div>
    </div>
  );
}

// ============================================================
// SECTOR ALLOCATION with Diversification Score inside
// ============================================================
function SectorAllocationCard() {
  const { data: portfolio } = usePortfolio();

  const { sectorData, diversification } = useMemo(() => {
    if (!portfolio || portfolio.holdings.length === 0) {
      return { sectorData: [], diversification: null };
    }

    const total = Number(portfolio.total_value) || 0;
    if (total <= 0) return { sectorData: [], diversification: null };

    // Group by sector
    const sectorMap: Record<string, number> = {};
    for (const h of portfolio.holdings) {
      const sector = SECTOR_MAP[h.ticker] || "Other";
      sectorMap[sector] = (sectorMap[sector] || 0) + Number(h.current_value || 0);
    }

    const data = Object.entries(sectorMap)
      .map(([name, value]) => ({
        name,
        value: Math.round(value),
        percent: Math.round((value / total) * 100),
        color: SECTOR_COLORS[name] || SECTOR_COLORS.Other,
      }))
      .sort((a, b) => b.value - a.value);

    // Diversification score (HHI-based)
    const shares = portfolio.holdings.map((h) => Number(h.current_value || 0) / total);
    const hhi = shares.reduce((sum, s) => sum + s * s, 0);
    const minHHI = 1 / portfolio.holdings.length;
    const score = Math.min(100, Math.max(0, Math.round(((1 - hhi) / (1 - minHHI)) * 100) || 0));

    const uniqueSectors = Object.keys(sectorMap).length;

    return {
      sectorData: data,
      diversification: { score, sectors: uniqueSectors, holdings: portfolio.holdings.length },
    };
  }, [portfolio]);

  if (sectorData.length === 0) return null;

  const getScoreColor = (s: number) => s >= 70 ? "text-emerald-500" : s >= 40 ? "text-amber-500" : "text-red-500";
  const getScoreLabel = (s: number) => s >= 70 ? "Well Diversified" : s >= 40 ? "Moderate" : "Concentrated";

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <PieChartIcon className="h-4 w-4 text-purple-500" />
        Sector Allocation
      </h3>

      <div className="grid gap-6 md:grid-cols-[1fr_200px]">
        {/* Pie chart */}
        <div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={sectorData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={85}
                innerRadius={45}
                paddingAngle={2}
                label={({ name, percent }) => percent > 5 ? `${name} ${percent}%` : ""}
                labelLine={false}
              >
                {sectorData.map((entry, index) => (
                  <Cell key={index} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number) => `₹${value.toLocaleString()}`}
                contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "12px" }}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2 justify-center">
            {sectorData.map((s) => (
              <div key={s.name} className="flex items-center gap-1.5 text-xs">
                <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                <span className="text-muted-foreground">{s.name}</span>
                <span className="font-medium">{s.percent}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Diversification Score */}
        {diversification && (
          <div className="flex flex-col items-center justify-center p-4">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-2">Score</p>
            <div className="relative h-20 w-20">
              <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="hsl(var(--border))"
                  strokeWidth="3"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke={diversification.score >= 70 ? "#10b981" : diversification.score >= 40 ? "#f59e0b" : "#ef4444"}
                  strokeWidth="3"
                  strokeDasharray={`${diversification.score}, 100`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-xl font-bold ${getScoreColor(diversification.score)}`}>
                  {diversification.score}
                </span>
              </div>
            </div>
            <p className={`text-xs font-medium mt-2 ${getScoreColor(diversification.score)}`}>
              {getScoreLabel(diversification.score)}
            </p>
            <p className="text-[10px] text-muted-foreground mt-1">
              {diversification.sectors} sectors · {diversification.holdings} stocks
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
