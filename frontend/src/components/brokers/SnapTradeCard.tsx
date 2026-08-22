/**
 * SnapTrade US Broker Connection Card.
 * Handles: register, connect (OAuth), show connections.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/api/client";
import { Link2, ExternalLink, CheckCircle2, Loader2, Trash2 } from "lucide-react";

interface Connection {
  id: string;
  brokerage: string;
  status: string;
  created_at: string;
}

export function SnapTradeCard() {
  const queryClient = useQueryClient();
  const [connecting, setConnecting] = useState(false);

  const { data: connections } = useQuery({
    queryKey: ["snaptrade-connections"],
    queryFn: () => apiFetch<{ connections: Connection[] }>("/snaptrade/connections"),
    staleTime: 60_000,
  });

  const disconnectMutation = useMutation({
    mutationFn: () => apiFetch("/snaptrade/disconnect", { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["snaptrade-connections"] }),
  });

  const handleConnect = async (broker?: string) => {
    setConnecting(true);
    try {
      // Get connection URL directly (Personal keys don't need registration)
      const params = broker ? `?broker=${broker}` : "";
      const result = await apiFetch<{ connect_url: string }>(`/snaptrade/connect-url${params}`);

      if (result.connect_url) {
        window.open(result.connect_url, "_blank", "width=600,height=700");
      }
    } catch (e: any) {
      // If connect-url fails, try registering first then retry
      try {
        await apiFetch("/snaptrade/register", { method: "POST" });
        const params = broker ? `?broker=${broker}` : "";
        const result = await apiFetch<{ connect_url: string }>(`/snaptrade/connect-url${params}`);
        if (result.connect_url) {
          window.open(result.connect_url, "_blank", "width=600,height=700");
        }
      } catch (e2: any) {
        console.error("SnapTrade connect error:", e2);
      }
    } finally {
      setConnecting(false);
    }
  };

  const activeConnections = connections?.connections?.filter((c) => c.status !== "DISABLED") || [];
  const hasConnections = activeConnections.length > 0;

  return (
    <div className="rounded-2xl border bg-card p-5 sm:col-span-2">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-medium flex items-center gap-2">
            <Link2 className="h-4 w-4 text-purple-500" />
            US Brokers
          </h3>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            Connect Robinhood, Fidelity, E*Trade, Schwab via secure OAuth
          </p>
        </div>
        {hasConnections && (
          <span className="badge badge-success">
            <CheckCircle2 className="h-2.5 w-2.5 mr-1" />
            {activeConnections.length} connected
          </span>
        )}
      </div>

      {/* Active connections */}
      {hasConnections && (
        <div className="space-y-2 mb-4">
          {activeConnections.map((c) => (
            <div key={c.id} className="flex items-center justify-between py-2 px-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                <span className="text-xs font-medium">{c.brokerage || "US Broker"}</span>
              </div>
              <span className="text-[9px] text-muted-foreground">
                {c.created_at ? new Date(c.created_at).toLocaleDateString(undefined, { month: "short", year: "numeric" }) : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Connect buttons */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => handleConnect("ROBINHOOD")}
          disabled={connecting}
          className="flex items-center justify-center gap-2 p-3 rounded-xl border hover:border-purple-500/30 hover:bg-purple-500/5 transition-colors text-xs font-medium"
        >
          {connecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5 text-purple-500" />}
          Robinhood
        </button>
        <button
          onClick={() => handleConnect("FIDELITY")}
          disabled={connecting}
          className="flex items-center justify-center gap-2 p-3 rounded-xl border hover:border-blue-500/30 hover:bg-blue-500/5 transition-colors text-xs font-medium"
        >
          {connecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ExternalLink className="h-3.5 w-3.5 text-blue-500" />}
          Fidelity
        </button>
        <button
          onClick={() => handleConnect()}
          disabled={connecting}
          className="flex items-center justify-center gap-2 p-3 rounded-xl border hover:border-primary/30 hover:bg-primary/5 transition-colors text-xs font-medium col-span-2"
        >
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
          Other US Broker...
        </button>
      </div>

      {/* Disconnect */}
      {hasConnections && (
        <button
          onClick={() => disconnectMutation.mutate()}
          disabled={disconnectMutation.isPending}
          className="mt-3 text-[10px] text-destructive hover:underline"
        >
          <Trash2 className="h-2.5 w-2.5 inline mr-1" />
          Disconnect all US brokers
        </button>
      )}

      <p className="text-[9px] text-muted-foreground mt-3 pt-2 border-t border-border">
        Powered by SnapTrade. Your credentials are never shared with RuDo — authentication happens directly with your broker.
      </p>
    </div>
  );
}
