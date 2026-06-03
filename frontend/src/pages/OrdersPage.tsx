import { OrderForm } from "@/components/orders/OrderForm";
import { TransactionHistory } from "@/components/orders/TransactionHistory";

export function OrdersPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Orders</h2>
      <OrderForm />
      <TransactionHistory />
    </div>
  );
}
