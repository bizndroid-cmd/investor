import { useEffect, useRef } from "react";
import { useAlerts } from "@/hooks/useAlerts";
import { showToast } from "@/components/common/Toast";

export function AlertNotification() {
  const { data: alerts } = useAlerts();
  const previousTriggeredRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!alerts) return;

    const triggered = alerts.filter((a) => a.status === "triggered");
    const previousIds = previousTriggeredRef.current;

    for (const alert of triggered) {
      if (!previousIds.has(alert.id)) {
        // New triggered alert
        showToast({
          title: "Alert Triggered",
          description: `${alert.ticker} went ${alert.condition} $${alert.target_price.toFixed(2)}`,
          variant: "default",
        });

        // Browser push notification opt-in
        if ("Notification" in window && Notification.permission === "granted") {
          new Notification("Price Alert Triggered", {
            body: `${alert.ticker} went ${alert.condition} $${alert.target_price.toFixed(2)}`,
          });
        }
      }
    }

    previousTriggeredRef.current = new Set(triggered.map((a) => a.id));
  }, [alerts]);

  // Request notification permission on mount
  useEffect(() => {
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  return null;
}
