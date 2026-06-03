import { useMemo } from "react";
import { usePortfolio } from "@/hooks/usePortfolio";
import type { BrokerId, NormalizedHolding } from "@/api/types";

interface BrokerSummary {
  broker_id: BrokerId;
  totalValue: number;
  totalGainLoss: number;
  holdingsCount: number;
}

export function BrokerComparisonTable() {
  const { data: portfolio, isLoading } = usePortfolio();

  const brokerSummaries = useMemo((): BrokerSummary[] => {
    if (!portfolio) return [];
    const map = new Map<BrokerId, NormalizedHolding[]>();
    for (const h of portfolio.holdings) {
      const list = map.get(h.broker_id) || [];
      list.push(h);
      map.set(h.broker_id, list);
    }
    return Array.from(map.entries()).map(([broker_id, holdings]) => ({
      broker_id,
      totalValue: holdings.reduce((sum, h) => sum + h.current_value, 0),
      totalGainLoss: holdings.reduce((sum, h) => sum + h.gain_loss, 0),
      holdingsCount: holdings.length,
    }));
  }, [portfolio]);

  if (isLoading) {
    return <div className="animate-pulse h-40 bg-muted rounded-lg" aria-busy="true" />;
  }

  if (brokerSummaries.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground">
        No broker data to compare.
      </div>
    );
  }

  return (
    <div className="rounded-lg border overflow-x-auto">
      <table className="w-full text-sm" aria-label="Broker comparison">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Broker</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">Total Value</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">Gain/Loss</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">Holdings</th>
          </tr>
        </thead>
        <tbody>
          {brokerSummaries.map((b) => (
            <tr key={b.broker_id} className="border-b hover:bg-muted/50">
              <td className="px-3 py-2 font-medium capitalize">{b.broker_id}</td>
              <td className="px-3 py-2 text-right">
                {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(b.totalValue)}
              </td>
              <td
                className={`px-3 py-2 text-right font-medium ${
                  b.totalGainLoss >= 0 ? "text-green-600" : "text-red-600"
                }`}
              >
                {new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(b.totalGainLoss)}
              </td>
              <td className="px-3 py-2 text-right">{b.holdingsCount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
