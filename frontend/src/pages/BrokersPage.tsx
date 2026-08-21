import { BrokerConnectionCard } from "@/components/brokers/BrokerConnectionCard";
import { SnapTradeCard } from "@/components/brokers/SnapTradeCard";

export function BrokersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Broker Connections</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Connect your brokerage accounts to sync portfolio data automatically
        </p>
      </div>

      {/* US Brokers via SnapTrade (OAuth) */}
      <SnapTradeCard />

      {/* India Brokers (manual token) */}
      <BrokerConnectionCard />
    </div>
  );
}
