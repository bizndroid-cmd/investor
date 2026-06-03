import { useQuery } from "@tanstack/react-query";
import { getHistoricalData } from "@/api/portfolio";
import type { TimeRange } from "@/api/types";

export function useMarketData(ticker: string | null, range: TimeRange) {
  return useQuery({
    queryKey: ["marketData", ticker, range],
    queryFn: () => getHistoricalData(ticker!, range),
    enabled: !!ticker,
  });
}
