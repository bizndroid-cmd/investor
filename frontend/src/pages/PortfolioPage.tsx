import { useMemo, useState } from "react";
import { Database, Wifi, Loader2, AlertTriangle } from "lucide-react";
import { PortfolioSummary } from "@/components/portfolio/PortfolioSummary";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { TopPerformers } from "@/components/portfolio/TopPerformers";
import { DiversificationScore } from "@/components/portfolio/DiversificationScore";
import { AllocationChart } from "@/components/charts/AllocationChart";
import { PortfolioTrendChart } from "@/components/charts/PortfolioTrendChart";
import { GainLossChart } from "@/components/charts/GainLossChart";
import { TimeRangeSelector } from "@/components/common/TimeRangeSelector";
import { usePortfolio, useRefreshPortfolio } from "@/hooks/usePortfolio";
import { usePriceSocket } from "@/hooks/usePriceSocket";

export function PortfolioPage() {
  const { data: portfolio } = usePortfolio();
  const refreshMutation = useRefreshPortfolio();
  const [showConfirm, setShowConfirm] = useState(false);

  const tickers = useMemo(
    () => portfolio?.holdings.map((h) => h.ticker) ?? [],
    [portfolio]
  );

  usePriceSocket(tickers);

  const handleRefreshClick = () => setShowConfirm(true);
  const handleConfirmRefresh = () => {
    setShowConfirm(false);
    refreshMutation.mutate();
  };
  const handleCancel = () => setShowConfirm(false);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-2xl font-bold">Portfolio</h2>
        <div className="flex items-center gap-3">
          {/* Data source + last refreshed */}
          {portfolio && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-xs text-emerald-700">
                <Database className="h-3 w-3" />
                Stored data
              </span>
              <span className="text-xs text-muted-foreground">
                Last pulled: {new Date(portfolio.last_refreshed).toLocaleString([], {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          )}
          {/* Refresh from broker button */}
          <button
            onClick={handleRefreshClick}
            disabled={refreshMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border hover:bg-accent transition-colors disabled:opacity-50"
          >
            {refreshMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Wifi className="h-3.5 w-3.5" />
            )}
            Pull from Broker
          </button>
        </div>
      </div>

      {/* Refresh confirmation */}
      {showConfirm && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800">
                Refresh portfolio from broker API?
              </p>
              <p className="text-xs text-amber-700 mt-1">
                This will make a live API call to your broker (Groww) to fetch the latest holdings and prices.
                Today's data is already stored — this will overwrite it with fresh data.
              </p>
              <div className="flex gap-2 mt-3">
                <button
                  onClick={handleConfirmRefresh}
                  className="inline-flex items-center gap-1 rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700"
                >
                  <Wifi className="h-3 w-3" />
                  Yes, pull fresh data
                </button>
                <button
                  onClick={handleCancel}
                  className="rounded-md border border-amber-300 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <PortfolioSummary />

      <div className="grid gap-6 lg:grid-cols-2">
        <AllocationChart />
        <PortfolioTrendChart />
      </div>

      <HoldingsTable />

      <div className="grid gap-6 lg:grid-cols-2">
        <TopPerformers />
        <DiversificationScore />
      </div>

      <GainLossChart />
    </div>
  );
}
