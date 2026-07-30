import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import {
  TrendingUp, TrendingDown, Search, Target,
  BarChart3, Activity, AlertTriangle, ChevronDown, ChevronUp,
  Crosshair, Gauge, DollarSign, Percent, Info,
} from "lucide-react";

interface ResearchData {
  ticker: string;
  error?: string;
  verdict?: {
    verdict: string;
    score: number;
    max_score: number;
    strengths: string[];
    weaknesses: string[];
  };
  technicals?: {
    current_price: number;
    day_change: number;
    day_change_pct: number;
    returns: { week: number | null; month: number | null; three_month: number | null };
    moving_averages: { sma20: number | null; sma50: number | null; sma200: number | null; trend: string };
    rsi: number | null;
    rsi_signal: string;
    macd: { macd: number; signal: number; histogram: number; trend: string } | null;
    bollinger: { upper: number; middle: number; lower: number; width: number; position: number; signal: string } | null;
    atr: number | null;
    support_resistance: { support: number | null; resistance: number | null; current_vs_support_pct: number | null; current_vs_resistance_pct: number | null };
    volume: { current: number; avg_20d: number | null; ratio: number | null; signal: string };
    week_52: { high: number; low: number; from_high_pct: number; from_low_pct: number };
  };
  fundamentals?: {
    ticker: string;
    market_cap: string | null;
    pe_ratio: string | null;
    roce: string | null;
    roe: string | null;
    dividend_yield: string | null;
    book_value: string | null;
    high_low: string | null;
    pros: string | null;
    cons: string | null;
  } | null;
  prediction_accuracy?: { mentions: number; correct_days: number; accuracy_pct: number } | null;
  holding?: { quantity: number; avg_buy_price: number; current_value: number; invested_value: number; gain_loss: number; gain_loss_pct: number } | null;
  risk_factors?: string[];
}

async function fetchResearch(ticker: string): Promise<ResearchData> {
  return apiFetch(`/portfolio/research/${ticker}`);
}

export function ResearchPage() {
  const [ticker, setTicker] = useState("");
  const [searchTicker, setSearchTicker] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["research", searchTicker],
    queryFn: () => fetchResearch(searchTicker),
    enabled: !!searchTicker,
  });

  const handleSearch = () => {
    if (ticker.trim()) setSearchTicker(ticker.trim().toUpperCase());
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Crosshair className="h-6 w-6 text-indigo-500" />
          Stock Research
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Per-stock equity report with technicals, fundamentals, and AI accuracy
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Enter NSE ticker (e.g. RELIANCE, TCS, HDFCBANK)"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="w-full pl-9 pr-4 py-2.5 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={!ticker.trim()}
          className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Analyze
        </button>
      </div>

      {/* Quick picker */}
      <QuickPicker onSelect={(t) => { setTicker(t); setSearchTicker(t); }} />

      {isLoading && <LoadingSkeleton />}
      {error && <div className="text-red-500 text-sm">Failed to fetch research data.</div>}
      {data && !data.error && <ResearchCard data={data} />}
      {data?.error && (
        <div className="rounded-xl border p-6 text-center text-muted-foreground">
          <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-amber-400" />
          <p>{data.error}</p>
        </div>
      )}
    </div>
  );
}

function QuickPicker({ onSelect }: { onSelect: (t: string) => void }) {
  const tickers = ["RELIANCE", "TCS", "HDFCBANK", "ITC", "WIPRO", "ADANIPORTS", "ONGC", "LT", "VEDL", "ASHOKLEY"];
  return (
    <div className="flex flex-wrap gap-1.5">
      {tickers.map((t) => (
        <button
          key={t}
          onClick={() => onSelect(t)}
          className="px-2.5 py-1 text-xs rounded-full border bg-muted hover:bg-indigo-100 hover:border-indigo-300 font-mono transition-colors"
        >
          {t}
        </button>
      ))}
    </div>
  );
}

function ResearchCard({ data }: { data: ResearchData }) {
  const { verdict, technicals, fundamentals, prediction_accuracy, holding, risk_factors } = data;
  if (!verdict || !technicals) return null;

  return (
    <div className="space-y-4">
      {/* Hero: Verdict */}
      <VerdictCard ticker={data.ticker} verdict={verdict} technicals={technicals} holding={holding} />

      {/* Grid: Technicals + Fundamentals */}
      <div className="grid gap-4 lg:grid-cols-2">
        <TechnicalsCard technicals={technicals} />
        <FundamentalsCard fundamentals={fundamentals} />
      </div>

      {/* Support/Resistance + Volume */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SupportResistanceCard technicals={technicals} />
        <VolumeCard technicals={technicals} />
      </div>

      {/* AI Accuracy + Risks */}
      <div className="grid gap-4 lg:grid-cols-2">
        <AIAccuracyCard accuracy={prediction_accuracy} ticker={data.ticker} />
        <RiskCard risks={risk_factors} />
      </div>

      {/* Strengths & Weaknesses */}
      <StrengthsWeaknesses verdict={verdict} />
    </div>
  );
}

// ============= VERDICT HERO =============
function VerdictCard({ ticker, verdict, technicals, holding }: {
  ticker: string;
  verdict: ResearchData["verdict"];
  technicals: ResearchData["technicals"];
  holding: ResearchData["holding"];
}) {
  if (!verdict || !technicals) return null;

  const verdictColor = verdict.verdict === "BUY" ? "text-green-600 bg-green-50 border-green-200"
    : verdict.verdict === "SELL" ? "text-red-600 bg-red-50 border-red-200"
    : "text-amber-600 bg-amber-50 border-amber-200";

  const scoreColor = verdict.score >= 7 ? "text-green-500" : verdict.score >= 5 ? "text-amber-500" : "text-red-500";

  return (
    <div className="rounded-xl border bg-card p-6">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-xl font-bold font-mono">{ticker}</h3>
          <div className="flex items-baseline gap-3 mt-1">
            <span className="text-2xl font-bold">₹{technicals.current_price.toLocaleString()}</span>
            <span className={`text-sm font-semibold ${technicals.day_change >= 0 ? "text-green-600" : "text-red-600"}`}>
              {technicals.day_change >= 0 ? "+" : ""}{technicals.day_change.toFixed(2)} ({technicals.day_change_pct.toFixed(2)}%)
            </span>
          </div>
          {/* Returns */}
          <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
            {technicals.returns.week != null && <span>1W: <ReturnBadge val={technicals.returns.week} /></span>}
            {technicals.returns.month != null && <span>1M: <ReturnBadge val={technicals.returns.month} /></span>}
            {technicals.returns.three_month != null && <span>3M: <ReturnBadge val={technicals.returns.three_month} /></span>}
          </div>
        </div>

        {/* Verdict badge */}
        <div className="text-center">
          <div className={`px-4 py-2 rounded-lg border-2 font-bold text-lg ${verdictColor}`}>
            {verdict.verdict}
          </div>
          <div className={`text-2xl font-bold mt-1 ${scoreColor}`}>
            {verdict.score}<span className="text-sm text-muted-foreground">/{verdict.max_score}</span>
          </div>
        </div>
      </div>

      {/* Holding info */}
      {holding && (
        <div className="mt-4 pt-4 border-t flex flex-wrap gap-4 text-xs">
          <span>Qty: <strong>{holding.quantity}</strong></span>
          <span>Avg: <strong>₹{holding.avg_buy_price.toFixed(2)}</strong></span>
          <span>Invested: <strong>₹{holding.invested_value.toLocaleString()}</strong></span>
          <span className={holding.gain_loss >= 0 ? "text-green-600" : "text-red-600"}>
            P&L: <strong>{holding.gain_loss >= 0 ? "+" : ""}₹{holding.gain_loss.toFixed(0)} ({holding.gain_loss_pct.toFixed(1)}%)</strong>
          </span>
        </div>
      )}
    </div>
  );
}

// ============= TECHNICALS =============

const INDICATOR_INFO: Record<string, string> = {
  "Trend": "Overall price direction based on SMA alignment. Price above SMA20 above SMA50 = strong uptrend. Opposite = strong downtrend.",
  "SMA 20": "Simple Moving Average over 20 days. Average closing price of last 20 trading sessions. Acts as short-term support/resistance.",
  "SMA 50": "Simple Moving Average over 50 days. Medium-term trend indicator. Institutional traders watch this level for entries/exits.",
  "SMA 200": "Simple Moving Average over 200 days. Long-term trend. Price above SMA200 = bull market, below = bear market.",
  "RSI (14)": "Relative Strength Index measures momentum on a 0-100 scale. Above 70 = overbought (potential pullback). Below 30 = oversold (potential bounce). Calculated using average gains vs losses over 14 periods.",
  "MACD": "Moving Average Convergence Divergence. Difference between 12-day and 26-day EMA. Positive histogram = bullish momentum. Negative = bearish. Signal line crossovers indicate trend changes.",
  "Bollinger": "Bollinger Bands plot 2 standard deviations above/below 20-day SMA. Position shows where price sits within bands. Near upper = overbought, near lower = oversold. Squeeze (narrow bands) precedes big moves.",
  "ATR (14)": "Average True Range over 14 days. Measures daily volatility in rupees. Higher ATR = more volatile stock. Used for stop-loss placement (e.g., 2x ATR below entry).",
};

function InfoTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onClick={() => setShow(!show)}
        className="inline-flex items-center justify-center h-4 w-4 rounded-full bg-muted hover:bg-blue-100 text-muted-foreground hover:text-blue-600 transition-colors"
        aria-label="More info"
      >
        <Info className="h-2.5 w-2.5" />
      </button>
      {show && (
        <div className="absolute z-50 bottom-full left-0 mb-2 w-64 p-2.5 rounded-lg bg-gray-900 text-white text-[11px] leading-relaxed shadow-lg">
          {text}
          <div className="absolute top-full left-4 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </span>
  );
}

function TechnicalsCard({ technicals }: { technicals: ResearchData["technicals"] }) {
  if (!technicals) return null;

  const trendLabel = {
    strong_bullish: "Strong Uptrend",
    bullish: "Uptrend",
    neutral: "Sideways",
    bearish: "Downtrend",
    strong_bearish: "Strong Downtrend",
  }[technicals.moving_averages.trend] || "Neutral";

  const trendColor = technicals.moving_averages.trend.includes("bullish") ? "text-green-600"
    : technicals.moving_averages.trend.includes("bearish") ? "text-red-600" : "text-gray-600";

  return (
    <div className="rounded-xl border bg-card p-5">
      <h4 className="text-sm font-bold flex items-center gap-2 mb-3">
        <Activity className="h-4 w-4 text-blue-500" />
        Technical Indicators
      </h4>
      <div className="space-y-3">
        {/* Trend */}
        <RowWithInfo label="Trend" info={INDICATOR_INFO["Trend"]} value={trendLabel} valueClass={trendColor} />

        {/* SMAs */}
        <RowWithInfo label="SMA 20" info={INDICATOR_INFO["SMA 20"]} value={technicals.moving_averages.sma20 ? `₹${technicals.moving_averages.sma20.toFixed(2)}` : "—"} />
        <RowWithInfo label="SMA 50" info={INDICATOR_INFO["SMA 50"]} value={technicals.moving_averages.sma50 ? `₹${technicals.moving_averages.sma50.toFixed(2)}` : "—"} />
        <RowWithInfo label="SMA 200" info={INDICATOR_INFO["SMA 200"]} value={technicals.moving_averages.sma200 ? `₹${technicals.moving_averages.sma200.toFixed(2)}` : "—"} />

        {/* RSI */}
        <RowWithInfo
          label="RSI (14)"
          info={INDICATOR_INFO["RSI (14)"]}
          value={technicals.rsi ? `${technicals.rsi}` : "—"}
          badge={technicals.rsi_signal !== "neutral" ? technicals.rsi_signal : undefined}
          badgeColor={technicals.rsi_signal === "overbought" ? "bg-red-100 text-red-700" : technicals.rsi_signal === "oversold" ? "bg-green-100 text-green-700" : ""}
        />

        {/* MACD */}
        {technicals.macd && (
          <RowWithInfo
            label="MACD"
            info={INDICATOR_INFO["MACD"]}
            value={`${technicals.macd.histogram > 0 ? "+" : ""}${technicals.macd.histogram}`}
            badge={technicals.macd.trend}
            badgeColor={technicals.macd.trend === "bullish" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}
          />
        )}

        {/* Bollinger */}
        {technicals.bollinger && (
          <RowWithInfo
            label="Bollinger"
            info={INDICATOR_INFO["Bollinger"]}
            value={`Position: ${(technicals.bollinger.position * 100).toFixed(0)}%`}
            badge={technicals.bollinger.signal !== "neutral" ? technicals.bollinger.signal : undefined}
            badgeColor={technicals.bollinger.signal === "overbought" ? "bg-red-100 text-red-700" : technicals.bollinger.signal === "oversold" ? "bg-green-100 text-green-700" : ""}
          />
        )}

        {/* ATR */}
        <RowWithInfo label="ATR (14)" info={INDICATOR_INFO["ATR (14)"]} value={technicals.atr ? `₹${technicals.atr}` : "—"} />
      </div>
    </div>
  );
}

// ============= FUNDAMENTALS =============
function FundamentalsCard({ fundamentals }: { fundamentals: ResearchData["fundamentals"] }) {
  if (!fundamentals) {
    return (
      <div className="rounded-xl border bg-card p-5">
        <h4 className="text-sm font-bold flex items-center gap-2 mb-3">
          <DollarSign className="h-4 w-4 text-emerald-500" />
          Fundamentals
        </h4>
        <p className="text-xs text-muted-foreground text-center py-4">
          No fundamental data available. Run fundamentals refresh from Portfolio page.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-5">
      <h4 className="text-sm font-bold flex items-center gap-2 mb-3">
        <DollarSign className="h-4 w-4 text-emerald-500" />
        Fundamentals
        <span className="text-xs font-normal text-muted-foreground">(screener.in)</span>
      </h4>
      <div className="space-y-3">
        <Row label="Market Cap" value={fundamentals.market_cap ? `₹${Number(fundamentals.market_cap).toLocaleString()} Cr` : "—"} />
        <Row label="P/E Ratio" value={fundamentals.pe_ratio || "—"} />
        <Row label="ROCE" value={fundamentals.roce ? `${fundamentals.roce}%` : "—"} />
        <Row label="ROE" value={fundamentals.roe ? `${fundamentals.roe}%` : "—"} />
        <Row label="Dividend Yield" value={fundamentals.dividend_yield ? `${fundamentals.dividend_yield}%` : "—"} />
        <Row label="Book Value" value={fundamentals.book_value ? `₹${fundamentals.book_value}` : "—"} />
        <Row label="52W High/Low" value={fundamentals.high_low ? `₹${fundamentals.high_low}` : "—"} />
      </div>

      {/* Pros / Cons */}
      {(fundamentals.pros || fundamentals.cons) && (
        <div className="mt-4 pt-3 border-t space-y-2">
          {fundamentals.pros && (
            <div>
              <span className="text-xs font-semibold text-green-700">Pros: </span>
              <span className="text-xs text-green-800">{fundamentals.pros}</span>
            </div>
          )}
          {fundamentals.cons && (
            <div>
              <span className="text-xs font-semibold text-red-700">Cons: </span>
              <span className="text-xs text-red-800">{fundamentals.cons}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============= SUPPORT/RESISTANCE =============
function SupportResistanceCard({ technicals }: { technicals: ResearchData["technicals"] }) {
  if (!technicals) return null;
  const sr = technicals.support_resistance;
  const w52 = technicals.week_52;

  return (
    <div className="rounded-xl border bg-card p-5">
      <h4 className="text-sm font-bold flex items-center gap-2 mb-3">
        <Target className="h-4 w-4 text-purple-500" />
        Support & Resistance
      </h4>
      <div className="space-y-3">
        <Row label="Support" value={sr.support ? `₹${sr.support}` : "—"} valueClass="text-green-600" />
        <Row label="Resistance" value={sr.resistance ? `₹${sr.resistance}` : "—"} valueClass="text-red-600" />
        {sr.current_vs_support_pct != null && (
          <Row label="Above Support" value={`${sr.current_vs_support_pct}%`} />
        )}
        {sr.current_vs_resistance_pct != null && (
          <Row label="Below Resistance" value={`${sr.current_vs_resistance_pct}%`} />
        )}
        <div className="pt-2 border-t">
          <Row label="52W High" value={`₹${w52.high}`} />
          <Row label="52W Low" value={`₹${w52.low}`} />
          <Row label="From 52W High" value={`${w52.from_high_pct}%`} valueClass={w52.from_high_pct > -10 ? "text-green-600" : "text-red-600"} />
        </div>
      </div>
    </div>
  );
}

// ============= VOLUME =============
function VolumeCard({ technicals }: { technicals: ResearchData["technicals"] }) {
  if (!technicals) return null;
  const vol = technicals.volume;

  return (
    <div className="rounded-xl border bg-card p-5">
      <h4 className="text-sm font-bold flex items-center gap-2 mb-3">
        <BarChart3 className="h-4 w-4 text-cyan-500" />
        Volume Analysis
      </h4>
      <div className="space-y-3">
        <Row label="Today's Volume" value={vol.current.toLocaleString()} />
        <Row label="20D Avg Volume" value={vol.avg_20d ? vol.avg_20d.toLocaleString() : "—"} />
        <Row
          label="Volume Ratio"
          value={vol.ratio ? `${vol.ratio}x` : "—"}
          badge={vol.signal !== "normal" ? vol.signal : undefined}
          badgeColor={vol.signal === "high" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"}
        />
      </div>

      {/* Visual bar */}
      {vol.ratio && (
        <div className="mt-4">
          <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${vol.ratio > 1.5 ? "bg-blue-500" : vol.ratio < 0.5 ? "bg-gray-300" : "bg-gray-400"}`}
              style={{ width: `${Math.min(vol.ratio * 50, 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-1">
            <span>Low</span>
            <span>Average</span>
            <span>High</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ============= AI ACCURACY =============
function AIAccuracyCard({ accuracy, ticker }: { accuracy: ResearchData["prediction_accuracy"]; ticker: string }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <h4 className="text-sm font-bold flex items-center gap-2 mb-3">
        <Gauge className="h-4 w-4 text-indigo-500" />
        AI Prediction Accuracy — {ticker}
      </h4>
      {!accuracy ? (
        <p className="text-xs text-muted-foreground text-center py-4">
          No AI predictions recorded for this ticker yet.
        </p>
      ) : (
        <div className="space-y-3">
          <Row label="Predictions Made" value={`${accuracy.mentions} days`} />
          <Row label="Correct Calls" value={`${accuracy.correct_days}/${accuracy.mentions}`} />
          <Row
            label="Accuracy"
            value={`${accuracy.accuracy_pct}%`}
            valueClass={accuracy.accuracy_pct >= 60 ? "text-green-600 font-bold" : accuracy.accuracy_pct >= 40 ? "text-amber-600" : "text-red-600"}
          />
          {/* Accuracy bar */}
          <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${accuracy.accuracy_pct >= 60 ? "bg-green-500" : accuracy.accuracy_pct >= 40 ? "bg-amber-400" : "bg-red-400"}`}
              style={{ width: `${accuracy.accuracy_pct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ============= RISK FACTORS =============
function RiskCard({ risks }: { risks?: string[] }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <h4 className="text-sm font-bold flex items-center gap-2 mb-3">
        <AlertTriangle className="h-4 w-4 text-amber-500" />
        Risk Factors
      </h4>
      {!risks || risks.length === 0 ? (
        <p className="text-xs text-muted-foreground text-center py-4">No notable risks identified.</p>
      ) : (
        <ul className="space-y-2">
          {risks.map((r, i) => (
            <li key={i} className="flex items-start gap-2 text-xs">
              <span className="text-amber-500 mt-0.5">•</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ============= STRENGTHS & WEAKNESSES =============
function StrengthsWeaknesses({ verdict }: { verdict: ResearchData["verdict"] }) {
  if (!verdict) return null;
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="rounded-xl border bg-card p-5">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between">
        <h4 className="text-sm font-bold flex items-center gap-2">
          <Percent className="h-4 w-4 text-gray-500" />
          Detailed Strengths & Weaknesses
        </h4>
        {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>

      {expanded && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div>
            <h5 className="text-xs font-semibold text-green-700 mb-2 flex items-center gap-1">
              <TrendingUp className="h-3 w-3" /> Strengths
            </h5>
            {verdict.strengths.length === 0 ? (
              <p className="text-xs text-muted-foreground">No notable strengths</p>
            ) : (
              <ul className="space-y-1.5">
                {verdict.strengths.map((s, i) => (
                  <li key={i} className="text-xs flex items-start gap-1.5">
                    <span className="text-green-500 mt-0.5">✓</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h5 className="text-xs font-semibold text-red-700 mb-2 flex items-center gap-1">
              <TrendingDown className="h-3 w-3" /> Weaknesses
            </h5>
            {verdict.weaknesses.length === 0 ? (
              <p className="text-xs text-muted-foreground">No notable weaknesses</p>
            ) : (
              <ul className="space-y-1.5">
                {verdict.weaknesses.map((w, i) => (
                  <li key={i} className="text-xs flex items-start gap-1.5">
                    <span className="text-red-500 mt-0.5">✗</span>
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ============= HELPERS =============
function Row({ label, value, valueClass, badge, badgeColor }: {
  label: string;
  value: string;
  valueClass?: string;
  badge?: string;
  badgeColor?: string;
}) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`font-medium ${valueClass || ""}`}>{value}</span>
        {badge && (
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${badgeColor}`}>
            {badge}
          </span>
        )}
      </div>
    </div>
  );
}

function RowWithInfo({ label, info, value, valueClass, badge, badgeColor }: {
  label: string;
  info: string;
  value: string;
  valueClass?: string;
  badge?: string;
  badgeColor?: string;
}) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground flex items-center gap-1.5">
        {label}
        <InfoTooltip text={info} />
      </span>
      <div className="flex items-center gap-2">
        <span className={`font-medium ${valueClass || ""}`}>{value}</span>
        {badge && (
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${badgeColor}`}>
            {badge}
          </span>
        )}
      </div>
    </div>
  );
}

function ReturnBadge({ val }: { val: number }) {
  const color = val >= 0 ? "text-green-600" : "text-red-600";
  return <span className={`font-semibold ${color}`}>{val >= 0 ? "+" : ""}{val.toFixed(1)}%</span>;
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="rounded-xl border bg-card p-6 h-32" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border bg-card p-5 h-64" />
        <div className="rounded-xl border bg-card p-5 h-64" />
      </div>
    </div>
  );
}
