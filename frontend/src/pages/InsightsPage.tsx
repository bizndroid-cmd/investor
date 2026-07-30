import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import {
  AlertTriangle, TrendingUp, TrendingDown, Shield, BarChart3,
  Lightbulb, Target, ChevronDown, ChevronUp, Eye, Sparkles,
} from "lucide-react";

// API calls
async function getRisks(): Promise<any[]> {
  return apiFetch("/predictions/risks");
}
async function getPatterns(ticker: string): Promise<any[]> {
  return apiFetch(`/predictions/patterns/${ticker}`);
}
async function getFundamentals(): Promise<any[]> {
  return apiFetch("/portfolio/fundamentals");
}
async function getHistory(): Promise<any[]> {
  return apiFetch("/predictions/history?days=30");
}

export function InsightsPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Lightbulb className="h-6 w-6 text-yellow-500" />
          Smart Insights
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Data-driven intelligence from your portfolio history, market patterns, and AI accuracy
        </p>
      </div>

      <div className="stagger-children space-y-5">
        <RiskAlertsSection />
        <RebalancingSuggestions />
        <PatternDetectionSection />
        <AILensSection />
      </div>
    </div>
  );
}

// ============================================================
// 1. CONCENTRATION & CORRELATION RISKS
// ============================================================
function RiskAlertsSection() {
  const { data: risks, isLoading } = useQuery({
    queryKey: ["portfolio-risks"],
    queryFn: getRisks,
  });

  if (isLoading) return <SectionSkeleton />;

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <Shield className="h-4 w-4 text-red-500" />
        Concentration & Correlation Risks
      </h3>

      {(!risks || risks.length === 0) ? (
        <div className="text-center py-6 text-sm text-muted-foreground">
          <Shield className="h-8 w-8 mx-auto mb-2 text-emerald-400 opacity-60" />
          <p>No major concentration risks detected</p>
          <p className="text-xs mt-1 text-muted-foreground/70">Portfolio diversification looks healthy</p>
        </div>
      ) : (
        <div className="space-y-3">
          {risks.map((risk: any, i: number) => (
            <div
              key={i}
              className={`p-4 rounded-lg border transition-colors ${
                risk.severity === "high"
                  ? "bg-red-500/5 border-red-500/20"
                  : "bg-amber-500/5 border-amber-500/20"
              }`}
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className={`h-4 w-4 shrink-0 mt-0.5 ${
                  risk.severity === "high" ? "text-red-500" : "text-amber-500"
                }`} />
                <div className="flex-1">
                  <p className="text-sm font-semibold">
                    {risk.sector.charAt(0).toUpperCase() + risk.sector.slice(1)} Sector — {risk.exposure_pct}% Exposure
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">{risk.risk}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {risk.affected_tickers.map((t: string) => (
                      <span key={t} className="badge badge-info font-mono">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// 2. REBALANCING SUGGESTIONS
// ============================================================
function RebalancingSuggestions() {
  const { data: risks } = useQuery({
    queryKey: ["portfolio-risks"],
    queryFn: getRisks,
  });
  const { data: fundamentals } = useQuery({
    queryKey: ["fundamentals"],
    queryFn: getFundamentals,
  });

  const suggestions = generateRebalancingSuggestions(risks, fundamentals);

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <TrendingUp className="h-4 w-4 text-emerald-500" />
        Rebalancing Suggestions
      </h3>

      {suggestions.length === 0 ? (
        <div className="text-center py-6 text-sm text-muted-foreground">
          <TrendingUp className="h-8 w-8 mx-auto mb-2 text-emerald-400 opacity-60" />
          <p>Portfolio allocation looks balanced</p>
          <p className="text-xs mt-1 text-muted-foreground/70">No immediate rebalancing needed</p>
        </div>
      ) : (
        <div className="space-y-2">
          {suggestions.map((s, i) => (
            <div key={i} className={`p-3 rounded-lg border transition-colors ${
              s.type === "reduce" ? "bg-red-500/5 border-red-500/20" : "bg-emerald-500/5 border-emerald-500/20"
            }`}>
              <div className="flex items-center gap-2">
                {s.type === "reduce" ? (
                  <TrendingDown className="h-4 w-4 text-red-500" />
                ) : (
                  <TrendingUp className="h-4 w-4 text-emerald-500" />
                )}
                <p className="text-sm font-medium">{s.action}</p>
              </div>
              <p className="text-xs text-muted-foreground mt-1 ml-6">{s.reason}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// 3. HISTORICAL PATTERN DETECTION (refined)
// ============================================================
function PatternDetectionSection() {
  const [selectedTicker, setSelectedTicker] = useState("RELIANCE");
  const { data: patterns, isLoading } = useQuery({
    queryKey: ["patterns", selectedTicker],
    queryFn: () => getPatterns(selectedTicker),
  });

  const tickers = ["RELIANCE", "TCS", "HDFCBANK", "ADANIPORTS", "ITC", "WIPRO", "ONGC", "LT"];

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-1">
        <BarChart3 className="h-4 w-4 text-blue-500" />
        Historical Pattern Detection
      </h3>
      <p className="text-xs text-muted-foreground mb-4">
        Correlates past news sentiment with actual price movements to identify repeating patterns
      </p>

      {/* Ticker selector */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {tickers.map((t) => (
          <button
            key={t}
            onClick={() => setSelectedTicker(t)}
            className={`px-2.5 py-1 text-xs rounded-full font-medium transition-all duration-150 ${
              selectedTicker === t
                ? "bg-primary text-primary-foreground scale-105"
                : "bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="h-24 skeleton-shimmer rounded-lg" />
      ) : !patterns || patterns.length === 0 ? (
        <div className="text-center py-8 text-sm text-muted-foreground">
          <BarChart3 className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p>No significant patterns for <span className="font-mono font-semibold">{selectedTicker}</span></p>
          <p className="text-xs mt-1.5 text-muted-foreground/70 max-w-sm mx-auto">
            Patterns emerge when we have enough news + price data overlap (typically 30+ days of daily news matching price movements).
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {patterns.map((p: any, i: number) => (
            <div key={i} className="p-4 rounded-lg bg-blue-500/5 border border-blue-500/20">
              <div className="flex items-start gap-3">
                <Target className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-semibold">{p.pattern}</p>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    <div className="text-xs">
                      <span className="text-muted-foreground">What happened: </span>
                      <span className="font-medium">{p.historical_outcome}</span>
                    </div>
                    <div className="text-xs">
                      <span className="text-muted-foreground">Recurrence: </span>
                      <span className={`font-semibold ${
                        p.current_probability === "high" ? "text-red-500" : "text-amber-500"
                      }`}>{p.current_probability} probability</span>
                    </div>
                  </div>
                  <div className="mt-2 pt-2 border-t border-blue-500/10">
                    <p className="text-xs font-medium text-primary">
                      Suggested action: {p.suggested_action}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// 4. AI LENS — repurposed from multi-persona (shows actual AI performance)
// ============================================================
function AILensSection() {
  const [expanded, setExpanded] = useState(true);
  const { data: history } = useQuery({
    queryKey: ["prediction-history"],
    queryFn: getHistory,
  });

  // Compute per-lens stats from prediction history
  const scored = (history || []).filter((h: any) => h.scored);
  const totalPredictions = scored.length;
  const avgScore = totalPredictions > 0
    ? Math.round(scored.reduce((sum: number, h: any) => sum + (h.confidence_score || 0), 0) / totalPredictions)
    : 0;

  const bullishCalls = scored.filter((h: any) => h.market_mood === "bullish").length;
  const bearishCalls = scored.filter((h: any) => h.market_mood === "bearish").length;
  const neutralCalls = scored.filter((h: any) => h.market_mood === "neutral").length;

  // Determine dominant style
  const dominantBias = bullishCalls > bearishCalls ? "Bullish-leaning" : bearishCalls > bullishCalls ? "Cautious-leaning" : "Balanced";

  const lenses = [
    {
      name: "Value Lens",
      emoji: "🔍",
      description: "Screens P/E < 18, ROCE > 20%, dividend yield. Finds undervalued picks.",
      insight: "Feeds screener.in fundamentals into every prediction. Low P/E + high ROCE stocks get bullish bias.",
      active: true,
    },
    {
      name: "Momentum Lens",
      emoji: "⚡",
      description: "Tracks SMA crossovers, RSI extremes, volume spikes. Rides trends.",
      insight: "Technical analysis from Stock Research feeds back into daily briefings. Strong trend = higher conviction.",
      active: true,
    },
    {
      name: "Risk Lens",
      emoji: "🛡️",
      description: "Monitors sector concentration, correlation, drawdown. Preserves capital.",
      insight: "Concentration alerts above directly influence prediction caution levels. High exposure = hedging suggestions.",
      active: true,
    },
  ];

  return (
    <div className="bento-card">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <h3 className="text-sm font-bold flex items-center gap-2">
          <Eye className="h-4 w-4 text-purple-500" />
          AI Analysis Lenses
          <span className="text-xs font-normal text-muted-foreground">
            How the AI evaluates your portfolio from multiple angles
          </span>
        </h3>
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {expanded && (
        <div className="mt-4 space-y-4">
          {/* AI Performance Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatBox label="Predictions Scored" value={totalPredictions.toString()} />
            <StatBox label="Avg Accuracy" value={`${avgScore}%`} color={avgScore >= 60 ? "text-emerald-500" : avgScore >= 40 ? "text-amber-500" : "text-red-500"} />
            <StatBox label="Dominant Bias" value={dominantBias} />
            <StatBox label="Bull / Bear / Neutral" value={`${bullishCalls}/${bearishCalls}/${neutralCalls}`} />
          </div>

          {/* Lens cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {lenses.map((lens) => (
              <div key={lens.name} className="p-4 rounded-lg border bg-secondary/30 transition-colors hover:bg-secondary/50">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xl">{lens.emoji}</span>
                  <h4 className="font-semibold text-sm">{lens.name}</h4>
                  {lens.active && <Sparkles className="h-3 w-3 text-primary ml-auto" />}
                </div>
                <p className="text-xs text-muted-foreground">{lens.description}</p>
                <p className="text-xs mt-2 text-foreground/80 border-t border-border/50 pt-2">
                  {lens.insight}
                </p>
              </div>
            ))}
          </div>

          <p className="text-[11px] text-muted-foreground/70 text-center">
            All three lenses are active in every daily briefing. The AI weighs each perspective based on current market conditions.
          </p>
        </div>
      )}
    </div>
  );
}

// ============================================================
// HELPERS
// ============================================================

function SectionSkeleton() {
  return (
    <div className="bento-card">
      <div className="h-5 w-40 skeleton rounded mb-4" />
      <div className="h-24 skeleton-shimmer rounded-lg" />
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg border bg-background/50 p-3 text-center">
      <p className={`text-lg font-bold tabular-nums ${color || ""}`}>{value}</p>
      <p className="text-[10px] text-muted-foreground mt-0.5">{label}</p>
    </div>
  );
}

function generateRebalancingSuggestions(risks: any[] | undefined, fundamentals: any[] | undefined): Array<{type: string; action: string; reason: string}> {
  const suggestions: Array<{type: string; action: string; reason: string}> = [];

  if (risks) {
    for (const risk of risks) {
      if (risk.exposure_pct > 30) {
        suggestions.push({
          type: "reduce",
          action: `Reduce ${risk.sector} exposure from ${risk.exposure_pct}% to under 25%`,
          reason: `High concentration in ${risk.affected_tickers.join(", ")}. A sector-specific event could impact ${risk.exposure_pct}% of your portfolio.`,
        });
      }
    }
  }

  if (fundamentals) {
    const overvalued = fundamentals.filter((f: any) => parseFloat(f.pe_ratio || "0") > 40 && parseFloat(f.roe || "0") < 10);
    const undervalued = fundamentals.filter((f: any) => parseFloat(f.pe_ratio || "0") < 18 && parseFloat(f.roce || "0") > 20);

    for (const stock of overvalued.slice(0, 2)) {
      suggestions.push({
        type: "reduce",
        action: `Consider reducing ${stock.ticker} (P/E: ${stock.pe_ratio}, ROE: ${stock.roe}%)`,
        reason: "High valuation with low returns — risk of mean reversion",
      });
    }

    for (const stock of undervalued.slice(0, 2)) {
      suggestions.push({
        type: "add",
        action: `${stock.ticker} looks undervalued (P/E: ${stock.pe_ratio}, ROCE: ${stock.roce}%)`,
        reason: "Strong fundamentals at reasonable valuation — potential upside",
      });
    }
  }

  return suggestions;
}
