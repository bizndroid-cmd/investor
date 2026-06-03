import { BrokerConnectionCard } from "@/components/brokers/BrokerConnectionCard";

export function BrokersPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Broker Connections</h2>
      <BrokerConnectionCard />
    </div>
  );
}
