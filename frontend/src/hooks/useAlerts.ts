import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAlerts, createAlert, updateAlert, deleteAlert } from "@/api/alerts";
import type { CreateAlertRequest, UpdateAlertRequest } from "@/api/types";

export function useAlerts() {
  return useQuery({
    queryKey: ["alerts"],
    queryFn: getAlerts,
  });
}

export function useCreateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: CreateAlertRequest) => createAlert(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useUpdateAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, update }: { id: string; update: UpdateAlertRequest }) =>
      updateAlert(id, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}

export function useDeleteAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
