import { useQuery } from "@tanstack/react-query";
import { getOrders } from "@/api/orders";
import { OrderStatusBadge } from "./OrderStatusBadge";

export function TransactionHistory() {
  const { data: orders, isLoading } = useQuery({
    queryKey: ["orders"],
    queryFn: () => getOrders(),
  });

  if (isLoading) {
    return <div className="animate-pulse h-40 bg-muted rounded-lg" aria-busy="true" />;
  }

  if (!orders || orders.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground">
        No orders yet.
      </div>
    );
  }

  return (
    <div className="rounded-lg border overflow-x-auto">
      <table className="w-full text-sm" aria-label="Transaction history">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Date</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Ticker</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Side</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Type</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">Qty</th>
            <th className="px-3 py-2 text-right font-medium text-muted-foreground">Price</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Broker</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Status</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id} className="border-b hover:bg-muted/50">
              <td className="px-3 py-2 text-muted-foreground">
                {new Date(order.placed_at).toLocaleDateString()}
              </td>
              <td className="px-3 py-2 font-medium">{order.ticker}</td>
              <td className={`px-3 py-2 capitalize ${order.side === "buy" ? "text-green-600" : "text-red-600"}`}>
                {order.side}
              </td>
              <td className="px-3 py-2 capitalize">{order.order_type}</td>
              <td className="px-3 py-2 text-right">{order.quantity}</td>
              <td className="px-3 py-2 text-right">
                {order.execution_price
                  ? `$${order.execution_price.toFixed(2)}`
                  : order.limit_price
                  ? `$${order.limit_price.toFixed(2)} (limit)`
                  : "Market"}
              </td>
              <td className="px-3 py-2 capitalize">{order.broker_id}</td>
              <td className="px-3 py-2">
                <OrderStatusBadge status={order.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
