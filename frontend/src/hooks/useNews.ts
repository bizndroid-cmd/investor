import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getNewsFeed, triggerRefresh, getPortfolioBriefing, getLLMStatus } from "@/api/news";
import { useActivePortfolio } from "@/contexts/PortfolioContext";
import type { NewsFeedParams } from "@/api/news";

export function useNews(filters: NewsFeedParams = {}) {
  return useQuery({
    queryKey: ["news", filters],
    queryFn: () => getNewsFeed(filters),
  });
}

export function useRefreshNews() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (source?: string) => triggerRefresh(source),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["news"] });
    },
  });
}

export function useBriefing() {
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  return useQuery({
    queryKey: ["briefing", portfolioId],
    queryFn: () => getPortfolioBriefing(portfolioId ?? undefined),
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 30 * 60 * 1000, // Keep in cache for 30 minutes
  });
}

export function useLLMStatus() {
  return useQuery({
    queryKey: ["llm-status"],
    queryFn: getLLMStatus,
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 15000,
  });
}
