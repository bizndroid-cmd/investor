import { useQuery, useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
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

async function fetchEarnings(): Promise<EarningsData> {
  return apiFetch("/portfolio/earnings");
}

export function EarningsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["earnings"],
    queryFn: fetchEarnings,
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

        {/* Trade History Import */}
        <TradeImportCard />

        {/* Dividend Stocks List */}
        <DividendListCard data={data} />
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
        label="Portfolio Value"
        value={`₹${Math.round(s.total_portfolio_value).toLocaleString()}`}
        sub={`₹${Math.round(s.total_invested).toLocaleString()} invested`}
        icon={PiggyBank}
        color="text-purple-500"
      />
      <StatCard
        label="Non-Paying Stocks"
        value={`${s.stocks_not_paying}`}
        sub="No dividend income"
        icon={BarChart3}
        color="text-muted-foreground"
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
      </div>
    </div>
  );
}

// ============================================================
// YIELD vs BENCHMARKS
// ============================================================
function YieldComparisonCard({ data }: { data: EarningsData }) {
  const yc = data.yield_comparison!;

  const benchmarks = [
    { label: "Your Portfolio", value: yc.portfolio_yield, color: "bg-emerald-500" },
    { label: "SBI FD (1yr)", value: yc.fd_rate, color: "bg-blue-500" },
    { label: "PPF", value: yc.ppf_rate, color: "bg-indigo-500" },
    { label: "Savings Account", value: yc.savings_rate, color: "bg-gray-400" },
    { label: "Nifty 50 Div Yield", value: yc.nifty_dividend_yield, color: "bg-amber-500" },
  ];

  const maxVal = Math.max(...benchmarks.map((b) => b.value));

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <Landmark className="h-4 w-4 text-blue-500" />
        Yield vs Alternatives
      </h3>

      <div className="space-y-3">
        {benchmarks.map((b) => (
          <div key={b.label}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">{b.label}</span>
              <span className="font-semibold">{b.value}%</span>
            </div>
            <div className="h-2.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${b.color} transition-all`}
                style={{ width: `${(b.value / maxVal) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="text-[10px] text-muted-foreground mt-3 pt-2 border-t border-border">
        Dividend yield is just one component. Total returns = capital gains + dividends.
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
                            since {new Date(s.purchase_date).toLocaleDateString([], { month: "short", year: "2-digit" })}
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
// TRADE HISTORY IMPORT
// ============================================================
function TradeImportCard() {
  const { data: tradeData, refetch: refetchTrades } = useQuery({
    queryKey: ["trade-history"],
    queryFn: () => apiFetch<any>("/telegram/trade-history"),
    staleTime: 60_000,
  });

  const [showProgress, setShowProgress] = useState(false);
  const [progressSteps, setProgressSteps] = useState<Array<{ text: string; done: boolean; error?: boolean }>>([]);
  const [syncResult, setSyncResult] = useState<string | null>(null);

  const pollMutation = useMutation({
    mutationFn: async () => {
      setShowProgress(true);
      setSyncResult(null);
      setProgressSteps([
        { text: "Connecting to Telegram bot...", done: false },
        { text: "Checking for new documents...", done: false },
        { text: "Parsing trade report...", done: false },
        { text: "Storing trades in database...", done: false },
      ]);

      // Step 1
      await new Promise((r) => setTimeout(r, 400));
      setProgressSteps((prev) => prev.map((s, i) => i === 0 ? { ...s, done: true } : s));

      // Step 2
      await new Promise((r) => setTimeout(r, 300));
      setProgressSteps((prev) => prev.map((s, i) => i <= 1 ? { ...s, done: true } : s));

      // Actual API call
      const result = await apiFetch<any>("/telegram/poll", { method: "POST" });

      if (result.processed > 0) {
        // Success
        setProgressSteps((prev) => prev.map((s) => ({ ...s, done: true })));
        setSyncResult(`✅ Imported ${result.processed} report(s) successfully`);
      } else {
        // No documents found
        setProgressSteps((prev) => prev.map((s, i) => {
          if (i <= 1) return { ...s, done: true };
          return { ...s, done: true, error: true, text: i === 2 ? "No new documents found in Telegram" : "Nothing to store" };
        }));
        setSyncResult("No documents found. Make sure you sent the file to the Telegram bot BEFORE clicking sync.");
      }

      await new Promise((r) => setTimeout(r, 300));
      return result;
    },
    onSuccess: (data) => {
      if (data.processed > 0) {
        refetchTrades();
      }
    },
    onError: (error: any) => {
      const msg = error?.body?.detail || error?.message || "Sync failed";
      setProgressSteps((prev) => prev.map((s) => {
        if (s.done) return s;
        return { ...s, done: true, error: true, text: "Failed" };
      }));
      setSyncResult(`❌ ${typeof msg === "string" ? msg : "Sync failed. Check your login session and try again."}`);
    },
  });

  const hasTradeData = tradeData?.has_data;

  return (
    <>
      {/* Progress overlay */}
      {showProgress && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-card border rounded-2xl p-6 w-full max-w-sm shadow-2xl animate-scale-in">
            <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
              <RefreshCw className={`h-4 w-4 text-primary ${pollMutation.isPending ? "animate-spin" : ""}`} />
              Syncing from Telegram
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

            {/* Result message */}
            {syncResult && (
              <div className={`mt-4 pt-3 border-t text-xs ${syncResult.startsWith("✅") ? "text-emerald-500" : "text-muted-foreground"}`}>
                {syncResult}
              </div>
            )}

            {!pollMutation.isPending && (
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

        {!hasTradeData ? (
          <div className="rounded-lg border border-dashed border-primary/30 bg-primary/5 p-5">
            <div className="flex items-start gap-4">
              <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Send className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">Upload your broker trade report via Telegram</p>
                <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                  This enables accurate lifetime dividend calculations using your actual purchase dates.
                </p>
                <ol className="text-xs text-muted-foreground mt-3 space-y-1.5 list-decimal list-inside">
                  <li>Download <strong>Order History</strong> from Groww (Profile → Reports → Order History → XLSX)</li>
                  <li>Send the file to your <strong>Telegram bot</strong> in the chat window</li>
                  <li>Click <strong>"Sync from Telegram"</strong> below to pull and parse it</li>
                </ol>
                <p className="text-[10px] text-muted-foreground mt-3 italic">
                  Supports: XLSX, CSV from any broker (Groww, Zerodha, Angel One, Upstox, etc.)
                </p>
              </div>
            </div>

            <button
              onClick={() => pollMutation.mutate()}
              disabled={pollMutation.isPending}
              className="btn-primary mt-4 text-xs"
            >
              <Send className="h-3.5 w-3.5 mr-1.5" />
              Sync from Telegram
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">
                {tradeData.tickers} stocks · {tradeData.total_trades} trades · via {tradeData.broker || "broker"}
              </span>
              <button
                onClick={() => pollMutation.mutate()}
                disabled={pollMutation.isPending}
                className="btn-ghost text-xs"
              >
                <RefreshCw className={`h-3 w-3 mr-1 ${pollMutation.isPending ? "animate-spin" : ""}`} />
                Re-sync
              </button>
            </div>

            {/* Show first purchase dates */}
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

            <p className="text-[10px] text-muted-foreground italic">
              Send updated reports to Telegram anytime to refresh. Dividend calculations use these dates.
            </p>
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
