import type { BrokerConnectionStatus } from "@/api/types";

interface BrokerStatusBadgeProps {
  status: BrokerConnectionStatus;
}

const statusConfig: Record<BrokerConnectionStatus, { label: string; className: string }> = {
  connected: { label: "Connected", className: "bg-green-100 text-green-800" },
  disconnected: { label: "Disconnected", className: "bg-gray-100 text-gray-800" },
  error: { label: "Error", className: "bg-red-100 text-red-800" },
};

export function BrokerStatusBadge({ status }: BrokerStatusBadgeProps) {
  const config = statusConfig[status];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${config.className}`}
      aria-label={`Broker status: ${config.label}`}
    >
      {config.label}
    </span>
  );
}
