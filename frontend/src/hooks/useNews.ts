import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getNewsFeed, triggerRefresh, getPortfolioBriefing, getLLMStatus } from "@/api/news";
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
    mutationFn: triggerRefresh,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["news"] });
    },
  });
}

export function useBriefing() {
  return useQuery({
    queryKey: ["briefing"],
    queryFn: getPortfolioBriefing,
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: false, // Only fetch when manually triggered via refetch
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
