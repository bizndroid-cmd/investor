import { useAlerts, useDeleteAlert, useUpdateAlert } from "@/hooks/useAlerts";
import { showToast } from "@/components/common/Toast";
import { Trash2, Bell, BellOff } from "lucide-react";

export function AlertList() {
  const { data: alerts, isLoading } = useAlerts();
  const deleteAlert = useDeleteAlert();
  const updateAlert = useUpdateAlert();

  if (isLoading) {
    return <div className="animate-pulse h-40 bg-muted rounded-lg" aria-busy="true" />;
  }

  if (!alerts || alerts.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground">
        No alerts configured.
      </div>
    );
  }

  const handleDelete = (id: string) => {
    deleteAlert.mutate(id, {
      onSuccess: () => showToast({ title: "Alert deleted", variant: "default" }),
    });
  };

  const handleToggle = (id: string, currentStatus: string) => {
    const newStatus = currentStatus === "active" ? "triggered" : "active";
    updateAlert.mutate(
      { id, update: { status: newStatus as "active" | "triggered" } },
      {
        onSuccess: () =>
          showToast({ title: `Alert ${newStatus === "active" ? "reactivated" : "paused"}` }),
      }
    );
  };

  return (
    <div className="rounded-lg border overflow-x-auto">
      <table className="w-full text-sm" aria-label="Price alerts">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Ticker</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Condition</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">Target</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Status</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">Actions</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((alert) => (
            <tr key={alert.id} className="border-b hover:bg-muted/50">
              <td className="px-3 py-2 font-medium">{alert.ticker}</td>
              <td className="px-3 py-2 capitalize">{alert.condition}</td>
              <td className="px-3 py-2 text-right">
                ${alert.target_price.toFixed(2)}
              </td>
              <td className="px-3 py-2">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    alert.status === "active"
                      ? "bg-green-100 text-green-800"
                      : "bg-yellow-100 text-yellow-800"
                  }`}
                >
                  {alert.status}
                </span>
              </td>
              <td className="px-3 py-2 text-right">
                <div className="inline-flex gap-1">
                  <button
                    onClick={() => handleToggle(alert.id, alert.status)}
                    aria-label={alert.status === "active" ? "Pause alert" : "Reactivate alert"}
                    className="p-1 rounded hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {alert.status === "active" ? (
                      <BellOff className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <Bell className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(alert.id)}
                    aria-label="Delete alert"
                    className="p-1 rounded hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
