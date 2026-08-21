/**
 * Cross-market "What If" comparison tool.
 * "If I'd put my ₹50k in AAPL instead of RELIANCE, what would I have today?"
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Loader2, Shuffle } from "lucide-react";

interface WhatIfResult {
  source: { ticker: string; geo: string; buy_price: number; current_price: number; units: number; invested: number; current_value: number; return_pct: number };
  alternative: { ticker: string; geo: string; buy_price: number; current_price: number; units: number; invested: number; current_value: number; return_pct: number };
  difference: { value_diff: number; return_diff_pct: number; winner: string };
  chart_data: Record<string, any>[];
  currency: string;
  error?: string;
}

export function WhatIfSimulator() {
  const [amount, setAmount] = useState("50000");
  const [sourceTicker, setSourceTicker] = useState("");
  const [sourceGeo, setSourceGeo] = useState("IN");
  const [altTicker, setAltTicker] = useState("");
  const [altGeo, setAltGeo] = useState("US");
  const [buyDate, setBuyDate] = useState("2024-01-01");
  const [submitted, setSubmitted] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["what-if", sourceTicker, sourceGeo, altTicker, altGeo, amount, buyDate],
    queryFn: () => apiFetch<WhatIfResult>(
      `/market/what-if?amount=${amount}&source_ticker=${sourceTicker}&source_geo=${sourceGeo}&alt_ticker=${altTicker}&alt_geo=${altGeo}&buy_date=${buyDate}`
    ),
    enabled: submitted && !!sourceTicker && !!altTicker,
    staleTime: 10 * 60_000,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  const currency = sourceGeo === "IN" ? "₹" : "$";

  return (
    <div className="bento-card">
      <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
        <Shuffle className="h-4 w-4 text-purple-500" />
        What If? — Cross-Market Comparison
      </h3>
      <p className="text-xs text-muted-foreground mb-4">
        Compare what your investment would be worth in a different stock or market.
      </p>

      {/* Input form */}
      <form onSubmit={handleSubmit} className="grid grid-cols-2 md:grid-cols-7 gap-2 mb-4">
        <div>
          <label className="text-[9px] text-muted-foreground uppercase block mb-0.5">Amount</label>
          <input type="number" value={amount} onChange={(e) => { setAmount(e.target.value); setSubmitted(false); }} className="input-field text-xs" placeholder="50000" />
        </div>
        <div>
          <label className="text-[9px] text-muted-foreground uppercase block mb-0.5">You Bought</label>
          <input type="text" value={sourceTicker} onChange={(e) => { setSourceTicker(e.target.value.toUpperCase()); setSubmitted(false); }} className="input-field text-xs" placeholder="RELIANCE" />
        </div>
        <div>
          <label className="text-[9px] text-muted-foreground uppercase block mb-0.5">Market</label>
          <select value={sourceGeo} onChange={(e) => { setSourceGeo(e.target.value); setSubmitted(false); }} className="input-field text-xs">
            <option value="IN">India</option>
            <option value="US">US</option>
          </select>
        </div>
        <div>
          <label className="text-[9px] text-muted-foreground uppercase block mb-0.5">Instead Of</label>
          <input type="text" value={altTicker} onChange={(e) => { setAltTicker(e.target.value.toUpperCase()); setSubmitted(false); }} className="input-field text-xs" placeholder="AAPL" />
        </div>
        <div>
          <label className="text-[9px] text-muted-foreground uppercase block mb-0.5">Market</label>
          <select value={altGeo} onChange={(e) => { setAltGeo(e.target.value); setSubmitted(false); }} className="input-field text-xs">
            <option value="US">US</option>
            <option value="IN">India</option>
          </select>
        </div>
        <div>
          <label className="text-[9px] text-muted-foreground uppercase block mb-0.5">Since</label>
          <input type="date" value={buyDate} onChange={(e) => { setBuyDate(e.target.value); setSubmitted(false); }} className="input-field text-xs" />
        </div>
        <div className="flex items-end">
          <button type="submit" disabled={!sourceTicker || !altTicker || isLoading} className="btn-primary text-xs w-full">
            {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Compare"}
          </button>
        </div>
      </form>

      {/* Results */}
      {data && !data.error && (
        <div className="animate-fade-in">
          {/* Winner banner */}
          <div className={`rounded-xl p-4 mb-4 ${
            data.difference.return_diff_pct > 0
              ? "bg-purple-500/5 border border-purple-500/20"
              : "bg-blue-500/5 border border-blue-500/20"
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold">{data.difference.winner}</span>
                <span className="text-xs text-muted-foreground">wins by</span>
                <span className={`text-sm font-bold ${data.difference.return_diff_pct > 0 ? "text-purple-500" : "text-blue-500"}`}>
                  {Math.abs(data.difference.return_diff_pct).toFixed(1)}%
                </span>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">Value difference</p>
                <p className="text-sm font-bold">{currency}{Math.abs(data.difference.value_diff).toLocaleString()}</p>
              </div>
            </div>
          </div>

          {/* Side by side cards */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <ComparisonCard label="Your Pick" data={data.source} currency={currency} isWinner={data.difference.winner === data.source.ticker} />
            <ComparisonCard label="Alternative" data={data.alternative} currency={currency} isWinner={data.difference.winner === data.alternative.ticker} />
          </div>

          {/* Chart */}
          {data.chart_data.length > 0 && (
            <div>
              <p className="text-[9px] text-muted-foreground uppercase mb-2">Performance (normalized to 100)</p>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data.chart_data}>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 9 }}
                    tickFormatter={(v) => new Date(v).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}
                    interval="preserveStartEnd"
                    minTickGap={60}
                  />
                  <YAxis tick={{ fontSize: 9 }} domain={["auto", "auto"]} />
                  <Tooltip
                    contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px", fontSize: "10px" }}
                    labelFormatter={(v) => new Date(v).toLocaleDateString()}
                  />
                  <Legend wrapperStyle={{ fontSize: "10px" }} />
                  <Line type="monotone" dataKey={data.source.ticker} stroke="#3b82f6" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey={data.alternative.ticker} stroke="#8b5cf6" strokeWidth={2} dot={false} strokeDasharray="4 2" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {data?.error && (
        <p className="text-xs text-destructive mt-2">{data.error}</p>
      )}
    </div>
  );
}

function ComparisonCard({ label, data, currency, isWinner }: {
  label: string;
  data: WhatIfResult["source"];
  currency: string;
  isWinner: boolean;
}) {
  const returnColor = data.return_pct >= 0 ? "text-emerald-500" : "text-red-500";

  return (
    <div className={`rounded-xl border p-3 ${isWinner ? "border-primary/30 bg-primary/5" : ""}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[9px] text-muted-foreground uppercase">{label}</span>
        {isWinner && <span className="text-[8px] font-bold text-primary bg-primary/10 rounded-full px-1.5 py-0.5">WINNER</span>}
      </div>
      <p className="text-sm font-bold">{data.ticker} <span className="text-[9px] text-muted-foreground">({data.geo})</span></p>
      <div className="grid grid-cols-2 gap-2 mt-2 text-[10px]">
        <div>
          <span className="text-muted-foreground">Invested</span>
          <p className="font-medium">{currency}{data.invested.toLocaleString()}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Now worth</span>
          <p className="font-bold">{currency}{Math.round(data.current_value).toLocaleString()}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Return</span>
          <p className={`font-bold ${returnColor}`}>{data.return_pct >= 0 ? "+" : ""}{data.return_pct.toFixed(1)}%</p>
        </div>
        <div>
          <span className="text-muted-foreground">Units</span>
          <p className="font-medium">{data.units.toFixed(2)}</p>
        </div>
      </div>
    </div>
  );
}
