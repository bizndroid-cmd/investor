import { BrokerComparisonTable } from "@/components/brokers/BrokerComparisonTable";
import { TopPerformers } from "@/components/portfolio/TopPerformers";
import { DiversificationScore } from "@/components/portfolio/DiversificationScore";
import { PriceHistoryChart } from "@/components/charts/PriceHistoryChart";
import { TimeRangeSelector } from "@/components/common/TimeRangeSelector";
import { useState } from "react";

export function ComparisonPage() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-2xl font-bold">Broker Comparison</h2>
        <TimeRangeSelector />
      </div>

      <BrokerComparisonTable />

      <div className="grid gap-6 lg:grid-cols-2">
        <TopPerformers />
        <DiversificationScore />
      </div>

      <div>
        <div className="mb-2">
          <label htmlFor="compare-ticker" className="block text-sm font-medium mb-1">
            Compare Stock Price History
          </label>
          <input
            id="compare-ticker"
            type="text"
            placeholder="Enter ticker (e.g. AAPL)"
            className="rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onChange={(e) => setSelectedTicker(e.target.value.toUpperCase() || null)}
          />
        </div>
        <PriceHistoryChart ticker={selectedTicker} />
      </div>
    </div>
  );
}
