import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPortfolio, refreshPortfolio } from "@/api/portfolio";
import { useActivePortfolio } from "@/contexts/PortfolioContext";

export function usePortfolio() {
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  return useQuery({
    queryKey: ["portfolio", portfolioId],
    queryFn: () => getPortfolio(portfolioId ?? undefined),
    enabled: !!portfolioId,
  });
}

export function useRefreshPortfolio() {
  const queryClient = useQueryClient();
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  return useMutation({
    mutationFn: () => refreshPortfolio(portfolioId ?? undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio", portfolioId] });
    },
  });
}
