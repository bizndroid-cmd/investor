import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getBrokers, connectBroker, disconnectBroker, submitBrokerToken, getBrokerTokenInfo } from "@/api/brokers";
import type { TokenInfo } from "@/api/brokers";
import { BrokerStatusBadge } from "@/components/portfolio/BrokerStatusBadge";
import { showToast } from "@/components/common/Toast";
import type { BrokerId } from "@/api/types";
import { Link2, Unlink, Key, Clock, CheckCircle2, AlertTriangle } from "lucide-react";

const BROKER_LABELS: Record<BrokerId, string> = {
  groww: "Groww",
  zerodha: "Zerodha",
  fidelity: "Fidelity",
  robinhood: "Robinhood",
};

export function BrokerConnectionCard() {
  const queryClient = useQueryClient();
  const { data: brokers, isLoading } = useQuery({
    queryKey: ["brokers"],
    queryFn: getBrokers,
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectBroker,
    onSuccess: () => {
      showToast({ title: "Broker disconnected", variant: "default" });
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["groww-token-info"] });
    },
  });

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2" aria-busy="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="animate-pulse h-32 bg-muted rounded-lg" />
        ))}
      </div>
    );
  }

  const allBrokers: BrokerId[] = ["groww", "zerodha", "fidelity", "robinhood"];

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {allBrokers.map((brokerId) => {
        const broker = brokers?.find((b) => b.broker_id === brokerId);
        const isConnected = broker?.status === "connected";

        if (brokerId === "groww") {
          return (
            <GrowwConnectionCard
              key={brokerId}
              isConnected={isConnected}
              broker={broker}
              onDisconnect={() => disconnectMutation.mutate(brokerId)}
              disconnecting={disconnectMutation.isPending}
            />
          );
        }

        return (
          <div key={brokerId} className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium">{BROKER_LABELS[brokerId]}</h3>
              <BrokerStatusBadge status={broker?.status || "disconnected"} />
            </div>
            <p className="text-xs text-muted-foreground mb-3">Coming soon</p>
          </div>
        );
      })}
    </div>
  );
}

function GrowwConnectionCard({
  isConnected,
  broker,
  onDisconnect,
  disconnecting,
}: {
  isConnected: boolean;
  broker: any;
  onDisconnect: () => void;
  disconnecting: boolean;
}) {
  const [token, setToken] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const queryClient = useQueryClient();

  const { data: tokenInfo } = useQuery({
    queryKey: ["groww-token-info"],
    queryFn: () => getBrokerTokenInfo("groww"),
    enabled: isConnected,
    refetchInterval: 60000, // Check every minute for expiry
  });

  const handleSubmitToken = async () => {
    if (!token.trim() || token.length < 20) {
      showToast({ title: "Please paste a valid access token", variant: "error" });
      return;
    }
    setSubmitting(true);
    try {
      await submitBrokerToken("groww", token.trim());
      showToast({ title: "Groww connected successfully!", variant: "default" });
      setToken("");
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
      queryClient.invalidateQueries({ queryKey: ["groww-token-info"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    } catch (e: any) {
      showToast({ title: e?.message || "Failed to connect", variant: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const isExpired = tokenInfo?.status === "expired";
  const expiresAt = tokenInfo?.expires_at ? new Date(tokenInfo.expires_at) : null;
  const connectedAt = tokenInfo?.connected_at ? new Date(tokenInfo.connected_at) : null;

  return (
    <div className="rounded-lg border bg-card p-4 sm:col-span-2">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium">Groww</h3>
        <BrokerStatusBadge status={isExpired ? "error" : (broker?.status || "disconnected")} />
      </div>

      {/* Connected state — show details */}
      {isConnected && !isExpired && (
        <div className="space-y-2 mb-3">
          <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 rounded-md p-2 border border-emerald-200">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Connected to Groww Trading API</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            {connectedAt && (
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Connected: {connectedAt.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
              </div>
            )}
            {expiresAt && (
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Expires: {expiresAt.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
              </div>
            )}
          </div>
          <button
            onClick={onDisconnect}
            disabled={disconnecting}
            className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
          >
            <Unlink className="h-3 w-3" />
            Disconnect
          </button>
        </div>
      )}

      {/* Expired state — prompt to re-enter token */}
      {isConnected && isExpired && (
        <div className="mb-3">
          <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 rounded-md p-2 border border-amber-200 mb-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Token expired! Paste a new access token from Groww to reconnect.</span>
          </div>
        </div>
      )}

      {/* Token input — shown when disconnected or expired */}
      {(!isConnected || isExpired) && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Paste your Groww access token below. Get it from{" "}
            <a
              href="https://groww.in/trade-api/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              Groww Trade API
            </a>
            . Tokens expire daily at 6 AM IST.
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste access token here..."
              className="flex-1 rounded-md border px-3 py-1.5 text-xs bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <button
              onClick={handleSubmitToken}
              disabled={submitting || !token.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              <Key className="h-3 w-3" />
              {submitting ? "Connecting..." : "Connect"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
