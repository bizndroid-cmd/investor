import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getBrokers, connectBroker, disconnectBroker } from "@/api/brokers";
import { BrokerStatusBadge } from "@/components/portfolio/BrokerStatusBadge";
import { showToast } from "@/components/common/Toast";
import type { BrokerId } from "@/api/types";
import { Link2, Unlink } from "lucide-react";

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

  const connectMutation = useMutation({
    mutationFn: connectBroker,
    onSuccess: (data) => {
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
    },
    onError: () => {
      showToast({ title: "Failed to connect broker", variant: "error" });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectBroker,
    onSuccess: () => {
      showToast({ title: "Broker disconnected", variant: "default" });
      queryClient.invalidateQueries({ queryKey: ["brokers"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
    onError: () => {
      showToast({ title: "Failed to disconnect broker", variant: "error" });
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

        return (
          <div key={brokerId} className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium">{BROKER_LABELS[brokerId]}</h3>
              <BrokerStatusBadge status={broker?.status || "disconnected"} />
            </div>

            {broker?.last_successful_fetch && (
              <p className="text-xs text-muted-foreground mb-3">
                Last sync: {new Date(broker.last_successful_fetch).toLocaleString()}
              </p>
            )}

            {broker?.error_message && (
              <p className="text-xs text-destructive mb-3">{broker.error_message}</p>
            )}

            <div className="flex gap-2">
              {isConnected ? (
                <button
                  onClick={() => disconnectMutation.mutate(brokerId)}
                  disabled={disconnectMutation.isPending}
                  aria-label={`Disconnect ${BROKER_LABELS[brokerId]}`}
                  className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm text-destructive hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  <Unlink className="h-3 w-3" aria-hidden="true" />
                  Disconnect
                </button>
              ) : (
                <button
                  onClick={() => connectMutation.mutate(brokerId)}
                  disabled={connectMutation.isPending}
                  aria-label={`Connect ${BROKER_LABELS[brokerId]}`}
                  className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  <Link2 className="h-3 w-3" aria-hidden="true" />
                  Connect
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
