import { apiFetch } from "./client";
import type { Alert, CreateAlertRequest, UpdateAlertRequest } from "./types";

export async function getAlerts(): Promise<Alert[]> {
  return apiFetch<Alert[]>("/alerts");
}

export async function createAlert(request: CreateAlertRequest): Promise<Alert> {
  return apiFetch<Alert>("/alerts", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function updateAlert(
  id: string,
  update: UpdateAlertRequest
): Promise<Alert> {
  return apiFetch<Alert>(`/alerts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(update),
  });
}

export async function deleteAlert(id: string): Promise<void> {
  return apiFetch<void>(`/alerts/${id}`, { method: "DELETE" });
}
