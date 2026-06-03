import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getPortfolio, refreshPortfolio } from "@/api/portfolio";

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: getPortfolio,
  });
}

export function useRefreshPortfolio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: refreshPortfolio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}
