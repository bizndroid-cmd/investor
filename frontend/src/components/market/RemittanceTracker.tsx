/**
 * Remittance Tracker — record and analyze cross-border transfers.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { ArrowLeftRight, Trash2, Loader2, X } from "lucide-react";

interface Transfer {
  id: string;
  direction: string;
  source_amount: number;
  source_currency: string;
  target_amount: number;
  target_currency: string;
  exchange_rate: number;
  provider: string | null;
  purpose: string | null;
  transfer_date: string;
}

interface Summary {
  has_data: boolean;
  ytd?: {
    total_transfers: number;
    inr_to_usd: { count: number; total_inr_sent: number; total_usd_received: number; avg_rate: number };
    usd_to_inr: { count: number; total_usd_sent: number; total_inr_received: number; avg_rate: number };
  };
  rates?: { best: number; worst: number; current_spot: number };
  providers_used?: string[];
}

export function RemittanceTracker() {
  const queryClient = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: transfers } = useQuery({
    queryKey: ["remittances"],
    queryFn: () => apiFetch<{ transfers: Transfer[]; count: number }>("/remittances"),
    staleTime: 60_000,
  });

  const { data: summary } = useQuery({
    queryKey: ["remittances-summary"],
    queryFn: () => apiFetch<Summary>("/remittances/summary"),
    staleTime: 60_000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiFetch(`/remittances/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["remittances"] });
      queryClient.invalidateQueries({ queryKey: ["remittances-summary"] });
    },
  });

  return (
    <div className="bento-card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          <ArrowLeftRight className="h-4 w-4 text-blue-500" />
          Remittance Tracker
        </h3>
        <button onClick={() => setShowAdd(!showAdd)} className="text-[10px] text-primary font-medium hover:underline">
          {showAdd ? "Cancel" : "+ Record Transfer"}
        </button>
      </div>

      {showAdd && <AddForm onClose={() => setShowAdd(false)} />}

      {/* YTD Summary */}
      {summary?.has_data && summary.ytd && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="text-center p-2.5 rounded-xl bg-secondary/30">
            <p className="text-[9px] text-muted-foreground uppercase">Transfers YTD</p>
            <p className="text-lg font-bold">{summary.ytd.total_transfers}</p>
          </div>
          <div className="text-center p-2.5 rounded-xl bg-secondary/30">
            <p className="text-[9px] text-muted-foreground uppercase">Avg Rate</p>
            <p className="text-lg font-bold tabular-nums">
              ₹{(summary.ytd.usd_to_inr.avg_rate || summary.ytd.inr_to_usd.avg_rate || 0).toFixed(1)}
            </p>
          </div>
          <div className="text-center p-2.5 rounded-xl bg-secondary/30">
            <p className="text-[9px] text-muted-foreground uppercase">Spot Now</p>
            <p className="text-lg font-bold tabular-nums text-primary">₹{summary.rates?.current_spot}</p>
          </div>
        </div>
      )}

      {/* Transfer list */}
      {transfers && transfers.transfers.length > 0 ? (
        <div className="space-y-1.5 max-h-48 overflow-y-auto">
          {transfers.transfers.slice(0, 10).map((t) => (
            <div key={t.id} className="flex items-center justify-between text-xs py-2 px-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
              <div className="flex items-center gap-2">
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                  t.direction === "inr_to_usd" ? "bg-blue-500/10 text-blue-500" : "bg-emerald-500/10 text-emerald-500"
                }`}>
                  {t.direction === "inr_to_usd" ? "₹→$" : "$→₹"}
                </span>
                <div>
                  <span className="font-medium">
                    {t.source_currency === "INR" ? "₹" : "$"}{t.source_amount.toLocaleString()}
                  </span>
                  <span className="text-muted-foreground mx-1">→</span>
                  <span className="font-medium">
                    {t.target_currency === "INR" ? "₹" : "$"}{Math.round(t.target_amount).toLocaleString()}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[9px] text-muted-foreground">@{t.exchange_rate}</span>
                <span className="text-[9px] text-muted-foreground">{new Date(t.transfer_date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
                <button onClick={() => deleteMut.mutate(t.id)} className="text-muted-foreground hover:text-red-500">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : !showAdd ? (
        <p className="text-xs text-muted-foreground text-center py-4">No transfers recorded. Track your cross-border money movement.</p>
      ) : null}
    </div>
  );
}

function AddForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [direction, setDirection] = useState("inr_to_usd");
  const [amount, setAmount] = useState("");
  const [rate, setRate] = useState("");
  const [provider, setProvider] = useState("");
  const [transferDate, setTransferDate] = useState(new Date().toISOString().split("T")[0]);

  const mutation = useMutation({
    mutationFn: (body: any) => apiFetch("/remittances", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["remittances"] });
      queryClient.invalidateQueries({ queryKey: ["remittances-summary"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!amount || !rate) return;
    mutation.mutate({
      direction,
      source_amount: parseFloat(amount),
      exchange_rate: parseFloat(rate),
      provider: provider || null,
      purpose: "investment",
      transfer_date: transferDate,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4 p-3 rounded-xl border bg-muted/10 animate-fade-in">
      <select value={direction} onChange={(e) => setDirection(e.target.value)} className="input-field text-xs">
        <option value="inr_to_usd">₹ → $ (Send to US)</option>
        <option value="usd_to_inr">$ → ₹ (Send to India)</option>
      </select>
      <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={direction === "inr_to_usd" ? "₹ Amount" : "$ Amount"} className="input-field text-xs" required />
      <input type="number" value={rate} onChange={(e) => setRate(e.target.value)} placeholder="Rate (e.g. 83.5)" step="0.01" className="input-field text-xs" required />
      <input type="text" value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="Wise, HDFC..." className="input-field text-xs" />
      <div className="flex gap-1">
        <input type="date" value={transferDate} onChange={(e) => setTransferDate(e.target.value)} className="input-field text-xs w-28" />
        <button type="submit" disabled={mutation.isPending} className="btn-primary text-xs flex-1">
          {mutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add"}
        </button>
        <button type="button" onClick={onClose} className="btn-ghost text-xs px-2"><X className="h-3 w-3" /></button>
      </div>
    </form>
  );
}
