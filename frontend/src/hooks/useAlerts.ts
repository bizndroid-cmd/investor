import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAlerts, createAlert, updateAlert, deleteAlert } from "@/api/alerts";
import { useActivePortfolio } from "@/contexts/PortfolioContext";
import type { CreateAlertRequest, UpdateAlertRequest } from "@/api/types";

export function useAlerts() {
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  return useQuery({
    queryKey: ["alerts", portfolioId],
    queryFn: () => getAlerts(portfolioId ?? undefined),
  });
}

export function useCreateAlert() {
  const queryClient = useQueryClient();
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  return useMutation({
    mutationFn: (request: CreateAlertRequest) => createAlert(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts", portfolioId] });
    },
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  return useMutation({
    mutationFn: ({ id, update }: { id: string; update: UpdateAlertRequest }) =>
      updateAlert(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts", portfolioId] });
    },
  });
}

export function useDeleteAlert() {
  const queryClient = useQueryClient();
  const { activePortfolio } = useActivePortfolio();
  const portfolioId = activePortfolio?.id;

  return useMutation({
    mutationFn: (id: string) => deleteAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts", portfolioId] });
    },
  });
}
