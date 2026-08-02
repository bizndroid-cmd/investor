import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { useActivePortfolio } from "@/contexts/PortfolioContext";
import {
  Wallet, TrendingUp, PiggyBank, BarChart3,
  CircleDollarSign, ChevronDown, ChevronUp, Landmark,
  Upload, Send, CheckCircle2, RefreshCw,
} from "lucide-react";
import { useState } from "react";

interface EarningsData {
  has_data: boolean;
  snapshot_date?: string;
  summary?: {
    total_portfolio_value: number;
    total_invested: number;
    total_annual_dividends: number;
    total_monthly_dividends: number;
    effective_yield_pct: number;
    stocks_paying_dividends: number;
    stocks_not_paying: number;
  };
  cost_basis?: {
    total_invested: number;
    current_value: number;
    unrealized_gain: number;
    gain_pct: number;
    house_money_pct: number;
    original_capital_pct: number;
  };
  yield_comparison?: {
    portfolio_yield: number;
    fd_rate: number;
    savings_rate: number;
    nifty_dividend_yield: number;
    ppf_rate: number;
  };
  projection?: {
    annual_now: number;
    annual_3y: number;
    annual_5y: number;
    growth_assumption_pct: number;
  };
  dividend_stocks?: DividendStock[];
  non_paying_stocks?: DividendStock[];
}

interface DividendStock {
  ticker: string;
  quantity: number;
  current_value: number;
  invested_value: number;
  dividend_yield_pct: number;
  annual_dividend: number;
  monthly_dividend: number;
  yield_on_cost_pct: number;
  payout_frequency: string;
  total_earned_est?: number;
  purchase_date?: string | null;
}

async function fetchEarnings(portfolioId?: string): Promise<EarningsData> {
  const params = portfolioId ? `?portfolio_id=${portfolioId}` : "";
  return apiFetch(`/portfolio/earnings${params}`);
}

export function EarningsPage() {
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  const { data, isLoading } = useQuery({
    queryKey: ["earnings", portfolioId ?? "default"],
    queryFn: () => fetchEarnings(portfolioId ?? undefined),
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <LoadingSkeleton />;
  if (!data?.has_data) {
    return (
      <div className="space-y-6 animate-fade-in">
        <PageHeader />
        <div className="bento-card text-center py-12">
          <Wallet className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">No portfolio data available yet</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader />

      <div className="stagger-children space-y-5">
        {/* Top summary row */}
        <SummaryRow data={data} />

        {/* Cost Basis + Yield Comparison */}
        <div className="grid gap-5 lg:grid-cols-2">
          <CostBasisCard data={data} />
          <YieldComparisonCard data={data} />
        </div>

        {/* Income Projection */}
        <ProjectionCard data={data} />

        {/* Money Insights — additional spark metrics */}
        <MoneyInsightsCard data={data} />

        {/* Dividend Stocks List */}
        <DividendListCard data={data} />

        {/* Trade History Import */}
        <TradeImportCard />
      </div>
    </div>
  );
}

function PageHeader() {
  return (
    <div>
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <Wallet className="h-6 w-6 text-emerald-500" />
        Portfolio Earnings
      </h2>
      <p className="text-sm text-muted-foreground mt-1">
        What your equity holdings passively earn — dividends, yield, and income projections
      </p>
    </div>
  );
}

// ============================================================
// SUMMARY ROW
// ============================================================
function SummaryRow({ data }: { data: EarningsData }) {
  const s = data.summary!;
  return (
    <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
      <StatCard
        label="Annual Dividends"
        value={`₹${s.total_annual_dividends.toLocaleString()}`}
        sub={`₹${s.total_monthly_dividends.toLocaleString()}/month`}
        icon={CircleDollarSign}
        color="text-emerald-500"
      />
      <StatCard
        label="Portfolio Yield"
        value={`${s.effective_yield_pct}%`}
        sub={`${s.stocks_paying_dividends} stocks paying`}
        icon={TrendingUp}
        color="text-blue-500"
      />
      <StatCard
        label="Lifetime Dividend Earnings"
        value={`₹${((s as any).total_lifetime_dividends || 0).toLocaleString()}`}
        sub="Total received since purchase"
        icon={PiggyBank}
        color="text-purple-500"
      />
      <StatCard
        label="Investment Summary"
        value={`₹${Math.round(s.total_invested).toLocaleString()}`}
        sub={`Capital gains: ₹${((data.cost_basis?.unrealized_gain) || 0).toLocaleString()} while holding`}
        icon={BarChart3}
        color="text-emerald-500"
      />
    </div>
  );
}

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string; sub: string; icon: any; color: string;
}) {
  return (
    <div className="bento-card">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${color}`} />
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</span>
      </div>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
      <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>
    </div>
  );
}

// ============================================================
// COST BASIS BREAKDOWN
// ============================================================
function CostBasisCard({ data }: { data: EarningsData }) {
  const cb = data.cost_basis!;
  const gainColor = cb.unrealized_gain >= 0 ? "text-emerald-500" : "text-red-500";

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <PiggyBank className="h-4 w-4 text-purple-500" />
        Cost Basis Breakdown
      </h3>

      {/* Visual bar showing capital vs house money */}
      <div className="mb-4">
        <div className="h-4 rounded-full overflow-hidden flex bg-muted">
          <div
            className="h-full bg-blue-500 transition-all"
            style={{ width: `${cb.original_capital_pct}%` }}
          />
          <div
            className={`h-full ${cb.unrealized_gain >= 0 ? "bg-emerald-500" : "bg-red-500"} transition-all`}
            style={{ width: `${Math.abs(cb.house_money_pct)}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground mt-1.5">
          <span>Your Capital: {cb.original_capital_pct.toFixed(0)}%</span>
          <span className={gainColor}>
            {cb.unrealized_gain >= 0 ? "House Money" : "Unrealized Loss"}: {Math.abs(cb.house_money_pct).toFixed(0)}%
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <Row label="Total Invested" value={`₹${cb.total_invested.toLocaleString()}`} />
        <Row label="Current Value" value={`₹${cb.current_value.toLocaleString()}`} />
        <Row label="Unrealized Gain" value={`₹${cb.unrealized_gain.toLocaleString()} (${cb.gain_pct}%)`} valueClass={gainColor} />
        <Row label="Dividends Received" value={`₹${((data.summary as any)?.total_lifetime_dividends || 0).toLocaleString()}`} valueClass="text-emerald-500" />
        <div className="pt-2 border-t border-border">
          <Row
            label="Total Earnings (Gains + Dividends)"
            value={`₹${(cb.unrealized_gain + ((data.summary as any)?.total_lifetime_dividends || 0)).toLocaleString()}`}
            valueClass="text-emerald-500 font-bold"
          />
        </div>
      </div>
    </div>
  );
}

// ============================================================
// YIELD vs BENCHMARKS
// ============================================================
function YieldComparisonCard({ data }: { data: EarningsData }) {
  const s = data.summary!;
  const invested = s.total_invested;

  // Simulate 3-year returns on same invested amount across instruments
  // Using approximate annualized rates
  const alternatives = [
    { label: "Your Equity Portfolio", value: data.cost_basis!.current_value, rate: data.cost_basis!.gain_pct, color: "bg-emerald-500", highlight: true },
    { label: "SBI FD (7% compounded)", value: Math.round(invested * Math.pow(1.07, 3)), rate: 22.5, color: "bg-blue-500", highlight: false },
    { label: "PPF (7.1% compounded)", value: Math.round(invested * Math.pow(1.071, 3)), rate: 22.9, color: "bg-indigo-500", highlight: false },
    { label: "Savings Account (3.5%)", value: Math.round(invested * Math.pow(1.035, 3)), rate: 10.9, color: "bg-gray-400", highlight: false },
    { label: "Gold (12% avg 3yr)", value: Math.round(invested * Math.pow(1.12, 3)), rate: 40.5, color: "bg-amber-500", highlight: false },
    { label: "Nifty 50 Index (14% avg)", value: Math.round(invested * Math.pow(1.14, 3)), rate: 48.2, color: "bg-orange-500", highlight: false },
  ];

  const maxVal = Math.max(...alternatives.map((a) => a.value));

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-1">
        <Landmark className="h-4 w-4 text-blue-500" />
        What If You Invested ₹{Math.round(invested).toLocaleString()} Elsewhere?
      </h3>
      <p className="text-[10px] text-muted-foreground mb-4">
        Comparing 3-year hypothetical returns on same capital
      </p>

      <div className="space-y-3">
        {alternatives.map((a) => (
          <div key={a.label}>
            <div className="flex justify-between text-xs mb-1">
              <span className={a.highlight ? "font-semibold text-foreground" : "text-muted-foreground"}>
                {a.label}
              </span>
              <span className={`font-semibold ${a.highlight ? "text-emerald-500" : ""}`}>
                ₹{a.value.toLocaleString()}
              </span>
            </div>
            <div className="h-2.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${a.color} transition-all`}
                style={{ width: `${(a.value / maxVal) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-muted-foreground mt-3 pt-2 border-t border-border">
        Equity returns include unrealized capital gains. FD/PPF rates are pre-tax. Past performance ≠ future results.
      </p>
    </div>
  );
}

// ============================================================
// INCOME PROJECTION
// ============================================================
function ProjectionCard({ data }: { data: EarningsData }) {
  const p = data.projection!;

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <TrendingUp className="h-4 w-4 text-emerald-500" />
        Dividend Income Projection
        <span className="text-xs font-normal text-muted-foreground">
          (assuming {p.growth_assumption_pct}% annual dividend growth)
        </span>
      </h3>

      <div className="grid grid-cols-3 gap-4">
        <ProjectionTile label="This Year" value={p.annual_now} />
        <ProjectionTile label="In 3 Years" value={p.annual_3y} />
        <ProjectionTile label="In 5 Years" value={p.annual_5y} />
      </div>
    </div>
  );
}

function ProjectionTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center p-3 rounded-lg bg-secondary/30">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-lg font-bold text-emerald-500 mt-1">₹{Math.round(value).toLocaleString()}</p>
      <p className="text-[10px] text-muted-foreground">₹{Math.round(value / 12).toLocaleString()}/mo</p>
    </div>
  );
}

// ============================================================
// DIVIDEND STOCKS LIST
// ============================================================
function DividendListCard({ data }: { data: EarningsData }) {
  const [showNonPaying, setShowNonPaying] = useState(false);
  const paying = data.dividend_stocks || [];
  const nonPaying = data.non_paying_stocks || [];
  const hasTradeHistory = (data as any).has_trade_history;

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <CircleDollarSign className="h-4 w-4 text-emerald-500" />
        Dividend Earnings by Stock
      </h3>

      {!hasTradeHistory ? (
        <div className="text-center py-8">
          <Upload className="h-8 w-8 mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">Upload trade history to see dividend earnings</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            Send your broker order report via Telegram, then sync above
          </p>
        </div>
      ) : paying.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No dividend-paying stocks in trade history
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 font-medium text-muted-foreground">Stock</th>
                <th className="text-right py-2 font-medium text-muted-foreground">Yield</th>
                <th className="text-right py-2 font-medium text-muted-foreground">Annual ₹</th>
                <th className="text-right py-2 font-medium text-muted-foreground">Monthly ₹</th>
                <th className="text-right py-2 font-medium text-muted-foreground">Earned So Far</th>
                <th className="text-right py-2 font-medium text-muted-foreground">Yield on Cost</th>
                <th className="text-right py-2 font-medium text-muted-foreground">Payout</th>
              </tr>
            </thead>
            <tbody>
              {paying.map((s) => (
                <tr key={s.ticker} className="border-b border-border/50 hover:bg-secondary/20 transition-colors">
                  <td className="py-2.5">
                    <span className="font-mono font-semibold">{s.ticker}</span>
                    <span className="text-muted-foreground ml-1.5">×{s.quantity}</span>
                  </td>
                  <td className="text-right py-2.5 text-emerald-500 font-medium">{s.dividend_yield_pct}%</td>
                  <td className="text-right py-2.5 font-medium">₹{s.annual_dividend.toLocaleString()}</td>
                  <td className="text-right py-2.5 text-muted-foreground">₹{s.monthly_dividend}</td>
                  <td className="text-right py-2.5">
                    {s.total_earned_est && s.total_earned_est > 0 ? (
                      <div>
                        <span className="text-emerald-500 font-medium">₹{s.total_earned_est.toLocaleString()}</span>
                        {s.purchase_date && (
                          <p className="text-[9px] text-muted-foreground">
                            since {new Date(s.purchase_date).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })}
                          </p>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="text-right py-2.5">
                    <span className={s.yield_on_cost_pct > s.dividend_yield_pct ? "text-emerald-500" : ""}>
                      {s.yield_on_cost_pct}%
                    </span>
                  </td>
                  <td className="text-right py-2.5">
                    <span className="badge badge-info">{s.payout_frequency}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Non-paying stocks toggle */}
      {nonPaying.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border">
          <button
            onClick={() => setShowNonPaying(!showNonPaying)}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {showNonPaying ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {nonPaying.length} stocks not paying dividends
          </button>
          {showNonPaying && (
            <div className="flex flex-wrap gap-1.5 mt-2 animate-fade-in">
              {nonPaying.map((s) => (
                <span key={s.ticker} className="badge bg-muted text-muted-foreground font-mono">
                  {s.ticker}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================
// MONEY INSIGHTS — additional engaging metrics
// ============================================================
function MoneyInsightsCard({ data }: { data: EarningsData }) {
  const s = data.summary!;
  const cb = data.cost_basis!;
  const invested = s.total_invested;
  const currentVal = cb.current_value;
  const lifetimeDiv = (s as any).total_lifetime_dividends || 0;
  const totalReturn = cb.unrealized_gain + lifetimeDiv;
  const totalReturnPct = invested > 0 ? (totalReturn / invested * 100) : 0;

  // Rule of 72: years to double at current return rate
  const annualReturnPct = totalReturnPct / 3; // rough 3yr assumption
  const yearsToDouble = annualReturnPct > 0 ? Math.round(72 / annualReturnPct) : 0;

  // Daily earning rate
  const dailyEarning = totalReturn / (3 * 365); // over ~3 years

  // Dividend reinvestment: if you reinvested all dividends
  const reinvestedValue = lifetimeDiv > 0 ? lifetimeDiv * (1 + cb.gain_pct / 100) : 0;

  // Per-month SIP equivalent: what SIP gives same corpus
  const months = 36;
  // Per-month SIP equivalent
  const sipEquivalent = currentVal > 0 ? Math.round(currentVal / months) : 0;
  void sipEquivalent; // future use

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <TrendingUp className="h-4 w-4 text-amber-500" />
        Money Insights
      </h3>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <InsightTile
          label="Total Return (Gains + Dividends)"
          value={`₹${Math.round(totalReturn).toLocaleString()}`}
          sub={`${totalReturnPct.toFixed(1)}% on invested capital`}
          color="text-emerald-500"
        />
        <InsightTile
          label="Your Money Doubles In"
          value={yearsToDouble > 0 ? `~${yearsToDouble} years` : "—"}
          sub="At current growth rate (Rule of 72)"
          color="text-blue-500"
        />
        <InsightTile
          label="Daily Earning Rate"
          value={`₹${Math.round(dailyEarning).toLocaleString()}`}
          sub="Average daily wealth creation"
          color="text-purple-500"
        />
        <InsightTile
          label="If Dividends Were Reinvested"
          value={`₹${Math.round(reinvestedValue).toLocaleString()}`}
          sub="Extra gains from dividend compounding"
          color="text-amber-500"
        />
      </div>
    </div>
  );
}

function InsightTile({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) {
  return (
    <div className="rounded-lg bg-secondary/30 p-3">
      <p className="text-[10px] text-muted-foreground">{label}</p>
      <p className={`text-base font-bold mt-1 ${color}`}>{value}</p>
      <p className="text-[9px] text-muted-foreground mt-0.5">{sub}</p>
    </div>
  );
}

// ============================================================
// TRADE HISTORY IMPORT
// ============================================================
function TradeImportCard() {
  const queryClient = useQueryClient();
  const { data: tradeData, refetch: refetchTrades } = useQuery({
    queryKey: ["trade-history"],
    queryFn: () => apiFetch<any>("/telegram/trade-history"),
    staleTime: 60_000,
  });

  const { data: attachments } = useQuery({
    queryKey: ["attachments"],
    queryFn: () => apiFetch<any[]>("/telegram/attachments"),
    staleTime: 30_000,
  });

  const [showProgress, setShowProgress] = useState(false);
  const [progressSteps, setProgressSteps] = useState<Array<{ text: string; done: boolean; error?: boolean }>>([]);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  // Sync from Telegram (pull new docs)
  const syncMutation = useMutation({
    mutationFn: () => apiFetch<any>("/telegram/sync", { method: "POST" }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["attachments"] });
      if (data.new_attachments > 0) {
        setSyncResult(`Found ${data.new_attachments} new document(s). Select one to process.`);
        setShowPicker(true);
      } else {
        setSyncResult("No new documents in Telegram. Send a file to the bot first.");
      }
    },
  });

  // Process a specific attachment
  const processMutation = useMutation({
    mutationFn: async (attachmentId: string) => {
      setShowProgress(true);
      setSyncResult(null);
      setShowPicker(false);
      setProgressSteps([
        { text: "Downloading file from Telegram...", done: false },
        { text: "Parsing trade data...", done: false },
        { text: "Storing in database...", done: false },
        { text: "Updating dividend calculations...", done: false },
      ]);

      await new Promise((r) => setTimeout(r, 400));
      setProgressSteps((prev) => prev.map((s, i) => i === 0 ? { ...s, done: true } : s));

      const result = await apiFetch<any>(`/telegram/attachments/${attachmentId}/process`, { method: "POST" });

      if (result.status === "ok") {
        setProgressSteps((prev) => prev.map((s) => ({ ...s, done: true })));
        setSyncResult(`✅ Imported ${result.records_imported} trades (${result.buy_count} buys, ${result.tickers?.length} stocks)`);
      } else {
        setProgressSteps((prev) => prev.map((s) => s.done ? s : { ...s, done: true, error: true }));
        setSyncResult(`❌ ${result.message}`);
      }

      return result;
    },
    onSuccess: () => {
      refetchTrades();
      queryClient.invalidateQueries({ queryKey: ["attachments"] });
      queryClient.invalidateQueries({ queryKey: ["earnings"] });
    },
    onError: (error: any) => {
      setProgressSteps((prev) => prev.map((s) => s.done ? s : { ...s, done: true, error: true, text: "Failed" }));
      setSyncResult(`❌ ${error?.message || "Processing failed"}`);
    },
  });

  const hasTradeData = tradeData?.has_data;
  const pendingAttachments = (attachments || []).filter((a: any) => a.status === "pending");

  return (
    <>
      {/* Progress overlay */}
      {showProgress && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-card border rounded-2xl p-6 w-full max-w-sm shadow-2xl animate-scale-in">
            <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
              <RefreshCw className={`h-4 w-4 text-primary ${processMutation.isPending ? "animate-spin" : ""}`} />
              Processing Document
            </h4>
            <div className="space-y-3">
              {progressSteps.map((step, i) => (
                <div key={i} className="flex items-center gap-3">
                  {step.done && !step.error ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                  ) : step.done && step.error ? (
                    <div className="h-4 w-4 rounded-full bg-amber-500/20 flex items-center justify-center shrink-0">
                      <span className="text-[10px] text-amber-500">!</span>
                    </div>
                  ) : (
                    <div className="h-4 w-4 rounded-full border-2 border-primary/30 border-t-primary animate-spin shrink-0" />
                  )}
                  <span className={`text-xs ${step.error ? "text-amber-500" : step.done ? "text-foreground" : "text-muted-foreground"}`}>
                    {step.text}
                  </span>
                </div>
              ))}
            </div>
            {syncResult && (
              <div className={`mt-4 pt-3 border-t text-xs ${syncResult.startsWith("✅") ? "text-emerald-500" : "text-muted-foreground"}`}>
                {syncResult}
              </div>
            )}
            {!processMutation.isPending && (
              <button onClick={() => setShowProgress(false)} className="btn-ghost text-xs mt-4 w-full">
                Close
              </button>
            )}
          </div>
        </div>
      )}

      <div className="bento-card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold flex items-center gap-2">
            <Upload className="h-4 w-4 text-blue-500" />
            Trade History Import
          </h3>
          {hasTradeData && (
            <span className="badge badge-success">
              <CheckCircle2 className="h-2.5 w-2.5 mr-1" />
              {tradeData.total_trades} trades loaded
            </span>
          )}
        </div>

        {!hasTradeData && !showPicker && (
          <div className="rounded-lg border border-dashed border-primary/30 bg-primary/5 p-5">
            <div className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Send className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">Import trade report for accurate dividend calculations</p>
                <ol className="text-xs text-muted-foreground mt-3 space-y-1.5 list-decimal list-inside">
                  <li>Send your broker's Order History (XLSX/CSV) to Telegram bot</li>
                  <li>Click <strong>"Pull New Documents"</strong> to fetch it</li>
                  <li>Select the document to process</li>
                </ol>
              </div>
            </div>
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="btn-primary mt-4 text-xs"
            >
              <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${syncMutation.isPending ? "animate-spin" : ""}`} />
              Pull New Documents
            </button>
            {syncResult && !showPicker && (
              <p className="text-xs text-muted-foreground mt-2">{syncResult}</p>
            )}
          </div>
        )}

        {/* Document picker — show when pending attachments exist */}
        {pendingAttachments.length > 0 && (
          <div className="mt-3 space-y-2 animate-fade-in">
            <p className="text-xs font-medium">Select a document to process:</p>
            {pendingAttachments.map((a: any) => (
              <button
                key={a.id}
                onClick={() => processMutation.mutate(a.id)}
                disabled={processMutation.isPending}
                className="w-full flex items-center justify-between p-3 rounded-lg border hover:border-primary/30 hover:bg-primary/5 transition-colors text-left"
              >
                <div className="flex items-center gap-2">
                  <Upload className="h-4 w-4 text-primary" />
                  <div>
                    <p className="text-xs font-medium">{a.file_name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {a.file_size ? `${(a.file_size / 1024).toFixed(0)} KB` : ""} · Received {new Date(a.received_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <span className="text-[10px] text-primary font-medium">Process →</span>
              </button>
            ))}
          </div>
        )}

        {/* Has trade data — show summary + option to process more */}
        {hasTradeData && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                {tradeData.tickers} stocks · {tradeData.total_trades} trades · via {tradeData.broker || "broker"}
              </span>
              <button
                onClick={() => { syncMutation.mutate(); setShowPicker(true); }}
                disabled={syncMutation.isPending}
                className="btn-ghost text-xs"
              >
                <RefreshCw className={`h-3 w-3 mr-1 ${syncMutation.isPending ? "animate-spin" : ""}`} />
                Process New Doc
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {(tradeData.summary || []).slice(0, 8).map((s: any) => (
                <div key={s.ticker} className="rounded-lg bg-secondary/30 px-2.5 py-2 text-xs">
                  <span className="font-mono font-semibold">{s.ticker}</span>
                  {s.first_purchase && (
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      Since {new Date(s.first_purchase).toLocaleDateString([], { month: "short", year: "numeric" })}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* Show picker if pending docs exist */}
            {showPicker && pendingAttachments.length > 0 && (
              <div className="pt-3 border-t space-y-2 animate-fade-in">
                <p className="text-xs font-medium">New documents available:</p>
                {pendingAttachments.map((a: any) => (
                  <button
                    key={a.id}
                    onClick={() => processMutation.mutate(a.id)}
                    disabled={processMutation.isPending}
                    className="w-full flex items-center justify-between p-2.5 rounded-lg border hover:border-primary/30 transition-colors text-left"
                  >
                    <span className="text-xs">{a.file_name}</span>
                    <span className="text-[10px] text-primary font-medium">Process</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ============================================================
// HELPERS
// ============================================================
function Row({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-medium ${valueClass || ""}`}>{value}</span>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader />
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bento-card h-24 skeleton-shimmer" />
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="bento-card h-48 skeleton-shimmer" />
        <div className="bento-card h-48 skeleton-shimmer" />
      </div>
    </div>
  );
}
