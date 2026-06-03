import { apiFetch } from "./client";
import type { BrokerInfo, BrokerId } from "./types";

export interface TokenInfo {
  broker_id: string;
  status: "connected" | "disconnected" | "expired";
  connected_at?: string | null;
  expires_at?: string | null;
  token_preview?: string | null;
}

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

export async function submitBrokerToken(
  brokerId: BrokerId,
  accessToken: string
): Promise<TokenInfo> {
  return apiFetch<TokenInfo>(`/brokers/${brokerId}/token`, {
    method: "POST",
    body: JSON.stringify({ access_token: accessToken }),
  });
}

export async function getBrokerTokenInfo(brokerId: BrokerId): Promise<TokenInfo> {
  return apiFetch<TokenInfo>(`/brokers/${brokerId}/token-info`);
}
