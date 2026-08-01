import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getBrokers, disconnectBroker, submitBrokerToken, getBrokerTokenInfo } from "@/api/brokers";
import { BrokerStatusBadge } from "@/components/portfolio/BrokerStatusBadge";
import { showToast } from "@/components/common/Toast";
import type { BrokerId } from "@/api/types";
import { Unlink, Key, Clock, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";

const BROKER_LABELS: Record<BrokerId, string> = {
  groww: "Groww",
  zerodha: "Zerodha",
  fidelity: "Fidelity",
  robinhood: "Robinhood",
};

const BROKER_GEOS: Record<BrokerId, string> = {
  groww: "India (NSE/BSE)",
  zerodha: "India (NSE/BSE)",
  fidelity: "United States",
  robinhood: "United States",
};

export function BrokerConnectionCard() {
  const queryClient = useQueryClient();
  const { data: brokers, isLoading } = useQuery({
    queryKey: ["brokers"],
    queryFn: getBrokers,
    staleTime: 30_000,
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectBroker,
    onSuccess: () => {
      showToast({ title: "Broker disconnected", variant: "default" });
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
    },
  });

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2" aria-busy="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-36 bg-muted/50 rounded-lg animate-pulse" />
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

        if (brokerId === "robinhood") {
          return (
            <RobinhoodConnectionCard
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
              <div>
                <h3 className="font-medium">{BROKER_LABELS[brokerId]}</h3>
                <p className="text-[10px] text-muted-foreground">{BROKER_GEOS[brokerId]}</p>
              </div>
              <BrokerStatusBadge status={broker?.status || "disconnected"} />
            </div>
            <p className="text-xs text-muted-foreground">Coming soon</p>
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
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const handleSubmitToken = async () => {
    if (!token.trim() || token.length < 20) {
      showToast({ title: "Please paste a valid access token", variant: "error" });
      return;
    }
    setSubmitting(true);
    try {
      await submitBrokerToken("groww", token.trim());
      showToast({ title: "Groww connected!", variant: "default" });
      setToken("");
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
      queryClient.invalidateQueries({ queryKey: ["groww-token-info"] });
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
        <div>
          <h3 className="font-medium">Groww</h3>
          <p className="text-[10px] text-muted-foreground">India (NSE/BSE) · Daily token</p>
        </div>
        <BrokerStatusBadge status={isExpired ? "error" : (broker?.status || "disconnected")} />
      </div>

      {isConnected && !isExpired && (
        <div className="space-y-2 mb-3">
          <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-400 rounded-md p-2 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            <span>Connected to Groww Trading API</span>
          </div>
          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
            {connectedAt && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Connected {connectedAt.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
            {expiresAt && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Expires {expiresAt.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
          </div>
          <button
            onClick={onDisconnect}
            disabled={disconnecting}
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50 transition-colors"
          >
            <Unlink className="h-3 w-3" />
            Disconnect
          </button>
        </div>
      )}

      {isConnected && isExpired && (
        <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 dark:bg-amber-950/30 dark:text-amber-400 rounded-md p-2 border border-amber-200 dark:border-amber-800 mb-3">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <span>Token expired. Paste new token to reconnect.</span>
        </div>
      )}

      {(!isConnected || isExpired) && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Paste your Groww access token. Get from{" "}
            <a href="https://groww.in/trade-api/docs" target="_blank" rel="noopener noreferrer" className="text-primary underline">
              Groww Trade API
            </a>
            . Expires daily at 6 AM IST.
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste access token..."
              className="flex-1 rounded-md border px-3 py-1.5 text-xs bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onKeyDown={(e) => e.key === "Enter" && handleSubmitToken()}
            />
            <button
              onClick={handleSubmitToken}
              disabled={submitting || !token.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {submitting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Key className="h-3 w-3" />}
              {submitting ? "..." : "Connect"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function RobinhoodConnectionCard({
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
    queryKey: ["robinhood-token-info"],
    queryFn: () => getBrokerTokenInfo("robinhood"),
    enabled: isConnected,
    staleTime: 30_000,
  });

  const handleSubmitToken = async () => {
    if (!token.trim() || token.length < 10) {
      showToast({ title: "Please paste a valid Robinhood access token", variant: "error" });
      return;
    }
    setSubmitting(true);
    try {
      await submitBrokerToken("robinhood", token.trim());
      showToast({ title: "Robinhood connected!", variant: "default" });
      setToken("");
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
      queryClient.invalidateQueries({ queryKey: ["robinhood-token-info"] });
    } catch (e: any) {
      showToast({ title: e?.message || "Failed to connect", variant: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  const isExpired = tokenInfo?.status === "expired";

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-medium">Robinhood</h3>
          <p className="text-[10px] text-muted-foreground">United States (NYSE/NASDAQ)</p>
        </div>
        <BrokerStatusBadge status={isExpired ? "error" : (broker?.status || "disconnected")} />
      </div>

      {isConnected && !isExpired && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-400 rounded-md p-2 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            <span>Connected</span>
          </div>
          <button
            onClick={onDisconnect}
            disabled={disconnecting}
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50 transition-colors"
          >
            <Unlink className="h-3 w-3" />
            Disconnect
          </button>
        </div>
      )}

      {(!isConnected || isExpired) && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Paste a Robinhood access token (from robin_stocks session or API).
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Robinhood token..."
              className="flex-1 rounded-md border px-3 py-1.5 text-xs bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onKeyDown={(e) => e.key === "Enter" && handleSubmitToken()}
            />
            <button
              onClick={handleSubmitToken}
              disabled={submitting || !token.trim()}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {submitting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Key className="h-3 w-3" />}
              {submitting ? "..." : "Connect"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
