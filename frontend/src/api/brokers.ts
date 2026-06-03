import { apiFetch } from "./client";
import type { BrokerInfo, BrokerId } from "./types";

export async function getBrokers(): Promise<BrokerInfo[]> {
  const data = await apiFetch<{ brokers: BrokerInfo[] }>("/brokers");
  return data.brokers;
}

export async function connectBroker(
  brokerId: BrokerId
): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>(
    `/brokers/${brokerId}/connect`,
    { method: "POST" }
  );
}

export async function disconnectBroker(brokerId: BrokerId): Promise<void> {
  return apiFetch<void>(`/brokers/${brokerId}`, { method: "DELETE" });
}
