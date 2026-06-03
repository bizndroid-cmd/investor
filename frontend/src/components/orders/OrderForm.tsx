import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { placeOrder } from "@/api/orders";
import { showToast } from "@/components/common/Toast";
import type { BrokerId, OrderSide, OrderType, OrderRequest } from "@/api/types";

export function OrderForm() {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const [brokerId, setBrokerId] = useState<BrokerId>("robinhood");
  const [side, setSide] = useState<OrderSide>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [quantity, setQuantity] = useState("");
  const [limitPrice, setLimitPrice] = useState("");

  const mutation = useMutation({
    mutationFn: placeOrder,
    onSuccess: (order) => {
      showToast({
        title: "Order Placed",
        description: `${order.side.toUpperCase()} ${order.quantity} ${order.ticker} @ ${
          order.execution_price ? `$${order.execution_price}` : "market"
        }`,
        variant: "success",
      });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      resetForm();
    },
    onError: (error) => {
      showToast({
        title: "Order Failed",
        description: error instanceof Error ? error.message : "Unknown error",
        variant: "error",
      });
    },
  });

  const resetForm = () => {
    setTicker("");
    setQuantity("");
    setLimitPrice("");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const request: OrderRequest = {
      broker_id: brokerId,
      ticker: ticker.toUpperCase(),
      side,
      order_type: orderType,
      quantity: parseFloat(quantity),
      limit_price: orderType === "limit" ? parseFloat(limitPrice) : null,
    };
    mutation.mutate(request);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border bg-card p-4 space-y-4"
      aria-label="Place order form"
    >
      <h3 className="text-sm font-medium">Place Order</h3>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="order-ticker" className="block text-sm font-medium mb-1">
            Ticker
          </label>
          <input
            id="order-ticker"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            required
            placeholder="AAPL"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div>
          <label htmlFor="order-broker" className="block text-sm font-medium mb-1">
            Broker
          </label>
          <select
            id="order-broker"
            value={brokerId}
            onChange={(e) => setBrokerId(e.target.value as BrokerId)}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="robinhood">Robinhood</option>
            <option value="groww">Groww</option>
            <option value="zerodha">Zerodha</option>
            <option value="fidelity">Fidelity</option>
          </select>
        </div>

        <div>
          <fieldset>
            <legend className="block text-sm font-medium mb-1">Side</legend>
            <div className="inline-flex rounded-md border" role="group">
              <button
                type="button"
                onClick={() => setSide("buy")}
                aria-pressed={side === "buy"}
                className={`px-3 py-1.5 text-sm rounded-l-md ${
                  side === "buy" ? "bg-green-600 text-white" : "bg-background"
                }`}
              >
                Buy
              </button>
              <button
                type="button"
                onClick={() => setSide("sell")}
                aria-pressed={side === "sell"}
                className={`px-3 py-1.5 text-sm rounded-r-md ${
                  side === "sell" ? "bg-red-600 text-white" : "bg-background"
                }`}
              >
                Sell
              </button>
            </div>
          </fieldset>
        </div>

        <div>
          <fieldset>
            <legend className="block text-sm font-medium mb-1">Type</legend>
            <div className="inline-flex rounded-md border" role="group">
              <button
                type="button"
                onClick={() => setOrderType("market")}
                aria-pressed={orderType === "market"}
                className={`px-3 py-1.5 text-sm rounded-l-md ${
                  orderType === "market" ? "bg-primary text-primary-foreground" : "bg-background"
                }`}
              >
                Market
              </button>
              <button
                type="button"
                onClick={() => setOrderType("limit")}
                aria-pressed={orderType === "limit"}
                className={`px-3 py-1.5 text-sm rounded-r-md ${
                  orderType === "limit" ? "bg-primary text-primary-foreground" : "bg-background"
                }`}
              >
                Limit
              </button>
            </div>
          </fieldset>
        </div>

        <div>
          <label htmlFor="order-quantity" className="block text-sm font-medium mb-1">
            Quantity
          </label>
          <input
            id="order-quantity"
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
            min="0.000001"
            step="any"
            placeholder="10"
            className="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        {orderType === "limit" && (
          <div>
            <label htmlFor="order-limit-price" className="block text-sm font-medium mb-1">
              Limit Price
            </label>
            <input
              id="order-limit-price"
              type="number"
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              required
              min="0.01"
              step="any"
              placeholder="150.00"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        {mutation.isPending ? "Placing Order…" : `${side === "buy" ? "Buy" : "Sell"} ${ticker.toUpperCase() || "Stock"}`}
      </button>
    </form>
  );
}
