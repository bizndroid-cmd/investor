import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import {
  AlertTriangle, TrendingUp, TrendingDown, Shield, BarChart3,
  Lightbulb, Target, Users, ChevronDown, ChevronUp,
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

export function InsightsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Lightbulb className="h-6 w-6 text-yellow-500" />
          Smart Insights
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          AI-powered intelligence based on your portfolio's historical data
        </p>
      </div>

      <RiskAlertsSection />
      <PatternDetectionSection />
      <RebalancingSuggestions />
      <PersonaAnalysis />
    </div>
  );
}

// ============================================================
// #8: RISK ALERTS
// ============================================================
function RiskAlertsSection() {
  const { data: risks, isLoading } = useQuery({
    queryKey: ["portfolio-risks"],
    queryFn: getRisks,
  });

  if (isLoading) return <SectionSkeleton title="Risk Alerts" />;

  return (
    <div className="rounded-xl border bg-card p-5">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <Shield className="h-4 w-4 text-red-500" />
        Concentration & Correlation Risks
      </h3>

      {(!risks || risks.length === 0) ? (
        <div className="text-center py-6 text-sm text-muted-foreground">
          <Shield className="h-8 w-8 mx-auto mb-2 text-green-400" />
          <p>No major concentration risks detected ✓</p>
          <p className="text-xs mt-1">Your portfolio is reasonably diversified</p>
        </div>
      ) : (
        <div className="space-y-3">
          {risks.map((risk: any, i: number) => (
            <div
              key={i}
              className={`p-4 rounded-lg border ${
                risk.severity === "high" ? "bg-red-50 border-red-200" : "bg-amber-50 border-amber-200"
              }`}
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className={`h-5 w-5 shrink-0 mt-0.5 ${
                  risk.severity === "high" ? "text-red-500" : "text-amber-500"
                }`} />
                <div className="flex-1">
                  <p className={`text-sm font-semibold ${
                    risk.severity === "high" ? "text-red-800" : "text-amber-800"
                  }`}>
                    {risk.sector.charAt(0).toUpperCase() + risk.sector.slice(1)} Sector — {risk.exposure_pct}% Exposure
                  </p>
                  <p className="text-xs text-gray-600 mt-1">{risk.risk}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {risk.affected_tickers.map((t: string) => (
                      <span key={t} className="text-xs bg-white/80 border rounded px-1.5 py-0.5 font-mono">
                        {t}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs mt-2 italic text-gray-500">
                    💡 Consider diversifying into other sectors to reduce single-event risk
                  </p>
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
// #4: PATTERN DETECTION
// ============================================================
function PatternDetectionSection() {
  const [selectedTicker, setSelectedTicker] = useState("RELIANCE");
  const { data: patterns, isLoading } = useQuery({
    queryKey: ["patterns", selectedTicker],
    queryFn: () => getPatterns(selectedTicker),
  });

  const tickers = ["RELIANCE", "TCS", "HDFCBANK", "ADANIPORTS", "ITC", "WIPRO", "ONGC", "LT"];

  return (
    <div className="rounded-xl border bg-card p-5">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <BarChart3 className="h-4 w-4 text-blue-500" />
        Historical Pattern Detection
        <span className="text-xs font-normal text-muted-foreground">
          "When this happened before, the stock did X"
        </span>
      </h3>

      {/* Ticker selector */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {tickers.map((t) => (
          <button
            key={t}
            onClick={() => setSelectedTicker(t)}
            className={`px-2.5 py-1 text-xs rounded-full font-medium transition-colors ${
              selectedTicker === t
                ? "bg-blue-600 text-white"
                : "bg-muted text-muted-foreground hover:bg-blue-100"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="h-20 animate-pulse bg-muted rounded-lg" />
      ) : !patterns || patterns.length === 0 ? (
        <div className="text-center py-6 text-sm text-muted-foreground">
          <BarChart3 className="h-8 w-8 mx-auto mb-2 text-gray-300" />
          <p>No significant patterns detected for {selectedTicker}</p>
          <p className="text-xs mt-1">Need more data points — patterns emerge over time</p>
        </div>
      ) : (
        <div className="space-y-3">
          {patterns.map((p: any, i: number) => (
            <div key={i} className="p-3 rounded-lg bg-blue-50 border border-blue-200">
              <div className="flex items-start gap-2">
                <Target className="h-4 w-4 text-blue-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-blue-800">{p.pattern}</p>
                  <p className="text-xs text-blue-700 mt-1">
                    📊 Historical outcome: <strong>{p.historical_outcome}</strong>
                  </p>
                  <p className="text-xs text-blue-600 mt-1">
                    🎯 Probability: <strong>{p.current_probability}</strong>
                  </p>
                  <p className="text-xs text-blue-800 mt-2 font-medium">
                    💡 {p.suggested_action}
                  </p>
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
// #5: REBALANCING SUGGESTIONS
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

  // Generate suggestions based on concentration + fundamentals
  const suggestions = generateRebalancingSuggestions(risks, fundamentals);

  return (
    <div className="rounded-xl border bg-card p-5">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <TrendingUp className="h-4 w-4 text-emerald-500" />
        Rebalancing Suggestions
      </h3>

      {suggestions.length === 0 ? (
        <div className="text-center py-6 text-sm text-muted-foreground">
          <TrendingUp className="h-8 w-8 mx-auto mb-2 text-emerald-300" />
          <p>Portfolio looks balanced ✓</p>
          <p className="text-xs mt-1">No immediate rebalancing needed</p>
        </div>
      ) : (
        <div className="space-y-2">
          {suggestions.map((s, i) => (
            <div key={i} className={`p-3 rounded-lg border ${s.type === "reduce" ? "bg-red-50 border-red-200" : "bg-green-50 border-green-200"}`}>
              <div className="flex items-center gap-2">
                {s.type === "reduce" ? (
                  <TrendingDown className="h-4 w-4 text-red-500" />
                ) : (
                  <TrendingUp className="h-4 w-4 text-green-500" />
                )}
                <p className={`text-sm font-medium ${s.type === "reduce" ? "text-red-800" : "text-green-800"}`}>
                  {s.action}
                </p>
              </div>
              <p className="text-xs text-gray-600 mt-1 ml-6">{s.reason}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// #7: MULTIPLE AI PERSONAS
// ============================================================
function PersonaAnalysis() {
  const [expanded, setExpanded] = useState(false);

  const personas = [
    {
      name: "Value Investor",
      emoji: "🧓",
      style: "Warren Buffett approach",
      focus: "Low P/E, high ROCE, debt-free, consistent dividends",
      color: "blue",
    },
    {
      name: "Momentum Trader",
      emoji: "⚡",
      style: "Ride the trend",
      focus: "Price action, news catalyst, sector rotation, volume breakouts",
      color: "purple",
    },
    {
      name: "Risk Manager",
      emoji: "🛡️",
      style: "Capital preservation",
      focus: "Diversification, stop-losses, correlation, max drawdown",
      color: "amber",
    },
  ];

  return (
    <div className="rounded-xl border bg-card p-5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between"
      >
        <h3 className="text-sm font-bold flex items-center gap-2">
          <Users className="h-4 w-4 text-purple-500" />
          Multi-Persona Analysis
          <span className="text-xs font-normal text-muted-foreground">
            Three perspectives on your portfolio
          </span>
        </h3>
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {expanded && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          {personas.map((p) => (
            <div key={p.name} className={`p-4 rounded-lg border bg-${p.color}-50 border-${p.color}-200`}>
              <div className="text-2xl mb-2">{p.emoji}</div>
              <h4 className="font-bold text-sm">{p.name}</h4>
              <p className="text-xs text-muted-foreground italic">{p.style}</p>
              <p className="text-xs mt-2"><strong>Looks at:</strong> {p.focus}</p>
              <p className="text-xs mt-2 text-muted-foreground">
                The AI briefing already incorporates this perspective. Future update: separate reports per persona.
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// HELPERS
// ============================================================

function SectionSkeleton({}: { title: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 animate-pulse">
      <div className="h-5 w-40 bg-muted rounded mb-4" />
      <div className="h-20 bg-muted rounded" />
    </div>
  );
}

function generateRebalancingSuggestions(risks: any[] | undefined, fundamentals: any[] | undefined): Array<{type: string; action: string; reason: string}> {
  const suggestions: Array<{type: string; action: string; reason: string}> = [];

  // Based on concentration risks
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

  // Based on fundamentals
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
