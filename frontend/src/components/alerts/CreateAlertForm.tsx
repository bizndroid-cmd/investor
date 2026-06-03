import { useState } from "react";
import { useCreateAlert } from "@/hooks/useAlerts";
import { showToast } from "@/components/common/Toast";
import type { AlertCondition } from "@/api/types";

export function CreateAlertForm() {
  const [ticker, setTicker] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [condition, setCondition] = useState<AlertCondition>("above");

  const createAlert = useCreateAlert();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createAlert.mutate(
      {
        ticker: ticker.toUpperCase(),
        target_price: parseFloat(targetPrice),
        condition,
      },
      {
        onSuccess: () => {
          showToast({ title: "Alert Created", variant: "success" });
          setTicker("");
          setTargetPrice("");
        },
        onError: () => {
          showToast({ title: "Failed to create alert", variant: "error" });
        },
      }
    );
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border bg-card p-4 space-y-4"
      aria-label="Create price alert form"
    >
      <h3 className="text-sm font-medium">Create Price Alert</h3>

      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="alert-ticker" className="block text-sm font-medium mb-1">
            Ticker
          </label>
          <input
            id="alert-ticker"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            required
            placeholder="AAPL"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div>
          <label htmlFor="alert-condition" className="block text-sm font-medium mb-1">
            Condition
          </label>
          <select
            id="alert-condition"
            value={condition}
            onChange={(e) => setCondition(e.target.value as AlertCondition)}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="above">Price goes above</option>
            <option value="below">Price goes below</option>
          </select>
        </div>

        <div>
          <label htmlFor="alert-target-price" className="block text-sm font-medium mb-1">
            Target Price
          </label>
          <input
            id="alert-target-price"
            type="number"
            value={targetPrice}
            onChange={(e) => setTargetPrice(e.target.value)}
            required
            min="0.01"
            step="any"
            placeholder="200.00"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={createAlert.isPending}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        {createAlert.isPending ? "Creating…" : "Create Alert"}
      </button>
    </form>
  );
}
