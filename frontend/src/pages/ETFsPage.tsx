import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useActivePortfolio } from "@/contexts/PortfolioContext";
import {
  getETFs, addETF, deleteETF, getETFInsights, getETFDetails, getETFComparison,
  type ETFHolding, type ETFInsights, type AddETFBody,
} from "@/api/etfs";
import {
  Coins, Plus, Trash2, TrendingUp, TrendingDown, ChevronDown, ChevronUp,
  Info, PieChart, Target, Loader2, X, BarChart3,
} from "lucide-react";
import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

export function ETFsPage() {
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;
  const [showAddForm, setShowAddForm] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["etfs", portfolioId],
    queryFn: () => getETFs(portfolioId ?? undefined),
    staleTime: 5 * 60_000,
  });

  const { data: insights } = useQuery({
    queryKey: ["etf-insights", portfolioId],
    queryFn: () => getETFInsights(portfolioId ?? undefined),
    staleTime: 5 * 60_000,
  });

  if (isLoading) return <LoadingSkeleton />;

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader totalValueINR={data?.total_value_inr} totalValueUSD={data?.total_value_usd} onAdd={() => setShowAddForm(true)} />

      {showAddForm && (
        <AddETFForm onClose={() => setShowAddForm(false)} />
      )}

      <div className="stagger-children space-y-5">
        {insights?.has_data && <InsightsPanel insights={insights} />}

        {data?.has_data && <ComparisonChart portfolioId={portfolioId} />}

        {data?.has_data ? (
          <HoldingsTable holdings={data.holdings} />
        ) : (
          <EmptyState onAdd={() => setShowAddForm(true)} />
        )}

        <ETFExplainerCard />
      </div>
    </div>
  );
}

// ============================================================
// HEADER
// ============================================================
function PageHeader({ totalValueINR, totalValueUSD, onAdd }: { totalValueINR?: number; totalValueUSD?: number; onAdd: () => void }) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Coins className="h-6 w-6 text-amber-500" />
          ETF Holdings
          {totalValueINR != null && totalValueINR > 0 && (
            <span className="ml-2 text-sm font-medium bg-amber-500/10 text-amber-500 px-2.5 py-0.5 rounded-full">
              ₹{totalValueINR.toLocaleString("en-IN")}
            </span>
          )}
          {totalValueUSD != null && totalValueUSD > 0 && (
            <span className="ml-2 text-sm font-medium bg-blue-500/10 text-blue-500 px-2.5 py-0.5 rounded-full">
              ${totalValueUSD.toLocaleString("en-US")}
            </span>
          )}
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Track your ETF investments across India and US markets
        </p>
      </div>
      <button onClick={onAdd} className="btn-primary text-xs">
        <Plus className="h-3.5 w-3.5 mr-1.5" />
        Add ETF
      </button>
    </div>
  );
}

// ============================================================
// ADD ETF FORM
// ============================================================
function AddETFForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [buyPrice, setBuyPrice] = useState("");
  const [buyDate, setBuyDate] = useState("");
  const [geoId, setGeoId] = useState("IN");

  const mutation = useMutation({
    mutationFn: (body: AddETFBody) => addETF(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["etfs"] });
      queryClient.invalidateQueries({ queryKey: ["etf-insights"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker || !quantity || !buyPrice) return;
    mutation.mutate({
      ticker: ticker.toUpperCase(),
      quantity: parseFloat(quantity),
      buy_price: parseFloat(buyPrice),
      buy_date: buyDate || undefined,
      geo_id: geoId,
    });
  };

  return (
    <div className="bento-card animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold">Add ETF Holding</h3>
        <button onClick={onClose} className="btn-icon">
          <X className="h-4 w-4" />
        </button>
      </div>
      <form onSubmit={handleSubmit} className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <div>
          <label className="text-[10px] text-muted-foreground uppercase">Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="GOLDBEES"
            className="input-field w-full mt-1"
            required
          />
        </div>
        <div>
          <label className="text-[10px] text-muted-foreground uppercase">Quantity</label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="10"
            step="0.000001"
            className="input-field w-full mt-1"
            required
          />
        </div>
        <div>
          <label className="text-[10px] text-muted-foreground uppercase">Buy Price</label>
          <input
            type="number"
            value={buyPrice}
            onChange={(e) => setBuyPrice(e.target.value)}
            placeholder="52.50"
            step="0.01"
            className="input-field w-full mt-1"
            required
          />
        </div>
        <div>
          <label className="text-[10px] text-muted-foreground uppercase">Buy Date</label>
          <input
            type="date"
            value={buyDate}
            onChange={(e) => setBuyDate(e.target.value)}
            className="input-field w-full mt-1"
          />
        </div>
        <div>
          <label className="text-[10px] text-muted-foreground uppercase">Market</label>
          <select
            value={geoId}
            onChange={(e) => setGeoId(e.target.value)}
            className="input-field w-full mt-1"
          >
            <option value="IN">India (NSE)</option>
            <option value="US">US</option>
          </select>
        </div>
        <div className="flex items-end">
          <button type="submit" disabled={mutation.isPending} className="btn-primary w-full text-xs">
            {mutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Add"}
          </button>
        </div>
      </form>
      {mutation.isError && (
        <p className="text-xs text-red-500 mt-2">
          {(mutation.error as any)?.body?.detail || "Failed to add ETF"}
        </p>
      )}
    </div>
  );
}

// ============================================================
// HOLDINGS TABLE
// ============================================================
function HoldingsTable({ holdings }: { holdings: ETFHolding[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: deleteETF,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["etfs"] });
      queryClient.invalidateQueries({ queryKey: ["etf-insights"] });
    },
  });

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <Target className="h-4 w-4 text-blue-500" />
        Holdings
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2 font-medium text-muted-foreground">ETF</th>
              <th className="text-right py-2 font-medium text-muted-foreground">Qty</th>
              <th className="text-right py-2 font-medium text-muted-foreground">Buy Price</th>
              <th className="text-right py-2 font-medium text-muted-foreground">Current</th>
              <th className="text-right py-2 font-medium text-muted-foreground">Value</th>
              <th className="text-right py-2 font-medium text-muted-foreground">Gain/Loss</th>
              <th className="text-right py-2 font-medium text-muted-foreground">Day</th>
              <th className="text-right py-2 font-medium text-muted-foreground"></th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <HoldingRow
                key={h.id}
                holding={h}
                isExpanded={expandedId === h.id}
                onToggle={() => setExpandedId(expandedId === h.id ? null : h.id)}
                onDelete={() => deleteMutation.mutate(h.id)}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HoldingRow({
  holding: h,
  isExpanded,
  onToggle,
  onDelete,
}: {
  holding: ETFHolding;
  isExpanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const gainColor = h.gain_loss >= 0 ? "text-emerald-500" : "text-red-500";
  const dayColor = h.day_change >= 0 ? "text-emerald-500" : "text-red-500";
  const currency = h.currency === "INR" ? "₹" : "$";

  return (
    <>
      <tr className="border-b border-border/50 hover:bg-secondary/20 transition-colors">
        <td className="py-2.5">
          <button onClick={onToggle} className="flex items-center gap-1.5 text-left">
            {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            <div>
              <span className="font-mono font-semibold">{h.ticker}</span>
              <span className="ml-1.5 badge badge-info text-[9px]">{h.geo_id}</span>
              {h.name && <p className="text-[10px] text-muted-foreground truncate max-w-[140px]">{h.name}</p>}
            </div>
          </button>
        </td>
        <td className="text-right py-2.5">{h.quantity}</td>
        <td className="text-right py-2.5">{currency}{h.buy_price.toLocaleString()}</td>
        <td className="text-right py-2.5 font-medium">{currency}{h.current_price.toLocaleString()}</td>
        <td className="text-right py-2.5 font-medium">{currency}{h.current_value.toLocaleString()}</td>
        <td className={`text-right py-2.5 font-medium ${gainColor}`}>
          {h.gain_loss >= 0 ? "+" : ""}{h.gain_loss_pct.toFixed(1)}%
          <p className="text-[9px]">{currency}{h.gain_loss.toLocaleString()}</p>
        </td>
        <td className={`text-right py-2.5 ${dayColor}`}>
          {h.day_change >= 0 ? "+" : ""}{h.day_change_pct.toFixed(2)}%
        </td>
        <td className="text-right py-2.5">
          <button onClick={onDelete} className="btn-icon text-muted-foreground hover:text-red-500">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </td>
      </tr>
      {isExpanded && <ExpandedDetail holdingId={h.id} currency={currency} />}
    </>
  );
}

function ExpandedDetail({ holdingId, currency }: { holdingId: string; currency: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["etf-detail", holdingId],
    queryFn: () => getETFDetails(holdingId),
    staleTime: 10 * 60_000,
  });

  if (isLoading) {
    return (
      <tr>
        <td colSpan={8} className="py-4 text-center">
          <Loader2 className="h-4 w-4 animate-spin mx-auto text-muted-foreground" />
        </td>
      </tr>
    );
  }

  if (!data) return null;

  return (
    <tr className="bg-secondary/10">
      <td colSpan={8} className="py-4 px-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="text-[10px] text-muted-foreground uppercase">Category</span>
            <p className="font-medium mt-0.5">{data.category || "—"}</p>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground uppercase">Expense Ratio</span>
            <p className="font-medium mt-0.5">
              {data.expense_ratio != null ? `${(data.expense_ratio * 100).toFixed(2)}%` : "—"}
            </p>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground uppercase">Fund Family</span>
            <p className="font-medium mt-0.5">{data.fund_family || "—"}</p>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground uppercase">Total Assets</span>
            <p className="font-medium mt-0.5">
              {data.total_assets ? `${currency}${(data.total_assets / 1e9).toFixed(1)}B` : "—"}
            </p>
          </div>
        </div>

        {/* Returns */}
        {data.returns && Object.keys(data.returns).length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <span className="text-[10px] text-muted-foreground uppercase">CAGR Returns</span>
            <div className="flex gap-4 mt-1.5">
              {[
                { key: "return_1y", label: "1Y" },
                { key: "return_3y", label: "3Y" },
                { key: "return_5y", label: "5Y" },
              ].map(({ key, label }) => {
                const val = data.returns[key];
                if (val == null) return null;
                const color = val >= 0 ? "text-emerald-500" : "text-red-500";
                return (
                  <div key={key} className="text-center">
                    <p className="text-[10px] text-muted-foreground">{label}</p>
                    <p className={`font-semibold ${color}`}>{val.toFixed(1)}%</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Top Holdings */}
        {data.top_holdings && data.top_holdings.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/50">
            <span className="text-[10px] text-muted-foreground uppercase">Top Holdings</span>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {data.top_holdings.slice(0, 5).map((th) => (
                <span key={th.symbol} className="badge bg-muted text-muted-foreground">
                  {th.symbol || th.name} ({th.weight.toFixed(1)}%)
                </span>
              ))}
            </div>
          </div>
        )}
      </td>
    </tr>
  );
}

// ============================================================
// INSIGHTS PANEL
// ============================================================
function InsightsPanel({ insights }: { insights: ETFInsights }) {
  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        {insights.total_value_inr > 0 && (
          <StatCard
            label="Total Value (INR)"
            value={`₹${insights.total_value_inr.toLocaleString()}`}
            icon={Coins}
            color="text-amber-500"
          />
        )}
        {insights.total_value_usd > 0 && (
          <StatCard
            label="Total Value (USD)"
            value={`$${insights.total_value_usd.toLocaleString()}`}
            icon={Coins}
            color="text-blue-500"
          />
        )}
        {insights.best_performer && (
          <StatCard
            label="Best Performer"
            value={insights.best_performer.ticker}
            sub={`+${insights.best_performer.gain_loss_pct}%`}
            icon={TrendingUp}
            color="text-emerald-500"
          />
        )}
        {insights.worst_performer && (
          <StatCard
            label="Worst Performer"
            value={insights.worst_performer.ticker}
            sub={`${insights.worst_performer.gain_loss_pct}%`}
            icon={TrendingDown}
            color="text-red-500"
          />
        )}
      </div>

      {/* Allocation + Projections */}
      <div className="grid gap-5 lg:grid-cols-2">
        <AllocationCard allocation={insights.allocation} />
        <ProjectionsCard projections={insights.projections} />
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string; sub?: string; icon: any; color: string;
}) {
  return (
    <div className="bento-card">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${color}`} />
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</span>
      </div>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

function AllocationCard({ allocation }: { allocation: ETFInsights["allocation"] }) {
  const colors = ["bg-amber-500", "bg-slate-400", "bg-blue-500", "bg-emerald-500", "bg-purple-500"];

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <PieChart className="h-4 w-4 text-amber-500" />
        Allocation
      </h3>
      <div className="space-y-3">
        {allocation.map((a, i) => (
          <div key={a.category}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted-foreground">{a.category}</span>
              <span className="font-medium">{a.percentage}%</span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${colors[i % colors.length]} transition-all`}
                style={{ width: `${a.percentage}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProjectionsCard({ projections }: { projections: ETFInsights["projections"] }) {
  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <TrendingUp className="h-4 w-4 text-emerald-500" />
        5Y Projection (Historical CAGR)
      </h3>
      <div className="grid grid-cols-3 gap-3">
        <ProjectionTile label="1 Year" value={projections.projected_1y} cagr={projections.cagr_1y} />
        <ProjectionTile label="3 Years" value={projections.projected_3y} cagr={projections.cagr_3y} />
        <ProjectionTile label="5 Years" value={projections.projected_5y} cagr={projections.cagr_5y} />
      </div>
      <p className="text-[9px] text-muted-foreground mt-3 pt-2 border-t border-border">
        Based on historical CAGR. Past performance does not guarantee future returns.
      </p>
    </div>
  );
}

function ProjectionTile({ label, value, cagr }: { label: string; value: number | null; cagr: number }) {
  return (
    <div className="text-center p-3 rounded-lg bg-secondary/30">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-base font-bold text-emerald-500 mt-1">
        {value != null ? `${Math.round(value).toLocaleString()}` : "—"}
      </p>
      <p className="text-[10px] text-muted-foreground">CAGR: {cagr.toFixed(1)}%</p>
    </div>
  );
}

// ============================================================
// ETF EXPLAINER
// ============================================================
function ETFExplainerCard() {
  const [open, setOpen] = useState(false);

  return (
    <div className="bento-card">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full text-left">
        <Info className="h-4 w-4 text-blue-500" />
        <span className="font-medium">What is an ETF?</span>
        {open ? <ChevronUp className="h-3 w-3 ml-auto" /> : <ChevronDown className="h-3 w-3 ml-auto" />}
      </button>
      {open && (
        <div className="mt-3 pt-3 border-t border-border text-xs text-muted-foreground space-y-2 animate-fade-in">
          <p>
            An <strong className="text-foreground">Exchange-Traded Fund (ETF)</strong> is a basket of securities
            (stocks, bonds, commodities) that trades on an exchange like a regular stock.
          </p>
          <p>
            ETFs offer diversification at low cost. For example, a Gold ETF tracks gold prices,
            while a Nifty 50 ETF holds all 50 Nifty stocks proportionally.
          </p>
          <p>
            Key benefits: low expense ratios, intraday trading, no lock-in period,
            transparent holdings, and tax efficiency compared to mutual funds.
          </p>
        </div>
      )}
    </div>
  );
}

// ============================================================
// COMPARISON CHART
// ============================================================
const CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4", "#ec4899"];

function ComparisonChart({ portfolioId }: { portfolioId?: string }) {
  const [mockTicker, setMockTicker] = useState("");
  const [mockGeo, setMockGeo] = useState("IN");
  const [activeMock, setActiveMock] = useState<{ ticker: string; geo: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["etf-comparison", portfolioId, activeMock?.ticker, activeMock?.geo],
    queryFn: () => getETFComparison(
      portfolioId ?? undefined,
      activeMock?.ticker,
      activeMock?.geo,
    ),
    staleTime: 10 * 60_000,
  });

  const handleAddMock = () => {
    if (!mockTicker.trim()) return;
    setActiveMock({ ticker: mockTicker.trim().toUpperCase(), geo: mockGeo });
  };

  const handleRemoveMock = () => {
    setActiveMock(null);
  };

  return (
    <div className="bento-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-blue-500" />
          Performance Comparison
          <span className="text-[10px] text-muted-foreground font-normal">(normalized to 100)</span>
        </h3>
      </div>

      {/* Mock ETF simulator */}
      <div className="flex flex-wrap items-end gap-2 mb-4 p-3 rounded-lg bg-secondary/30">
        <div>
          <label className="text-[10px] text-muted-foreground uppercase block mb-1">Compare with</label>
          <input
            type="text"
            value={mockTicker}
            onChange={(e) => setMockTicker(e.target.value)}
            placeholder="e.g. NIFTYBEES, SPY"
            className="rounded-md border px-2.5 py-1.5 text-xs bg-background w-36 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onKeyDown={(e) => e.key === "Enter" && handleAddMock()}
          />
        </div>
        <div>
          <label className="text-[10px] text-muted-foreground uppercase block mb-1">Market</label>
          <select
            value={mockGeo}
            onChange={(e) => setMockGeo(e.target.value)}
            className="rounded-md border px-2.5 py-1.5 text-xs bg-background"
          >
            <option value="IN">India</option>
            <option value="US">US</option>
          </select>
        </div>
        <button
          onClick={handleAddMock}
          disabled={!mockTicker.trim()}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          Simulate
        </button>
        {activeMock && (
          <div className="flex items-center gap-1.5 rounded-full bg-purple-500/10 text-purple-500 px-2.5 py-1 text-xs font-medium">
            <span>{activeMock.ticker} ({activeMock.geo})</span>
            <button onClick={handleRemoveMock} className="hover:text-purple-700">
              <X className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>

      {/* Chart */}
      {isLoading ? (
        <div className="h-64 flex items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : data?.has_data && data.chart_data.length > 0 ? (
        <div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data.chart_data}>
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => {
                  const d = new Date(v);
                  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
                }}
                interval="preserveStartEnd"
                minTickGap={60}
              />
              <YAxis
                tick={{ fontSize: 10 }}
                domain={["auto", "auto"]}
                tickFormatter={(v) => `${v}`}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "8px",
                  fontSize: "11px",
                }}
                labelFormatter={(v) => new Date(v).toLocaleDateString()}
                formatter={(value: number, name: string) => [`${value.toFixed(1)}`, name]}
              />
              <Legend wrapperStyle={{ fontSize: "11px" }} />
              {data.tickers.map((t, i) => (
                <Line
                  key={t.ticker}
                  type="monotone"
                  dataKey={t.ticker}
                  stroke={t.is_mock ? "#8b5cf6" : CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={t.is_mock ? 2.5 : 1.5}
                  strokeDasharray={t.is_mock ? "6 3" : undefined}
                  dot={false}
                  name={`${t.ticker} (${t.geo_id})${t.is_mock ? " ⟵ simulated" : ""}`}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          <p className="text-[9px] text-muted-foreground mt-2 text-center">
            All series normalized to 100 at start. Shows relative growth, not absolute price.
          </p>
        </div>
      ) : (
        <div className="h-48 flex items-center justify-center text-xs text-muted-foreground">
          No historical data available. Add ETFs with buy dates to see comparison.
        </div>
      )}
    </div>
  );
}

// ============================================================
// EMPTY + LOADING STATES
// ============================================================
function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="bento-card text-center py-12">
      <Coins className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
      <p className="text-sm text-muted-foreground">No ETF holdings tracked yet</p>
      <p className="text-xs text-muted-foreground/70 mt-1">Add your first ETF to start tracking</p>
      <button onClick={onAdd} className="btn-primary text-xs mt-4">
        <Plus className="h-3.5 w-3.5 mr-1.5" />
        Add ETF
      </button>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="h-8 w-48 rounded bg-muted animate-pulse" />
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bento-card h-24 animate-pulse bg-muted/50" />
        ))}
      </div>
      <div className="bento-card h-64 animate-pulse bg-muted/50" />
    </div>
  );
}
