import type { NormalizedHolding } from "@/api/types";
import { PriceChange } from "@/components/common/PriceChange";

interface HoldingRowProps {
  holding: NormalizedHolding;
}

function formatCurrency(value: number | string): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(num || 0);
}

function toNum(v: number | string): number {
  return typeof v === "string" ? parseFloat(v) || 0 : v || 0;
}

export function HoldingRow({ holding }: HoldingRowProps) {
  const glp = toNum(holding.gain_loss_percent);
  return (
    <tr className="border-b transition-colors hover:bg-muted/50">
      <td className="px-3 py-2 font-medium">{holding.ticker}</td>
      <td className="px-3 py-2 text-muted-foreground">{holding.company_name}</td>
      <td className="px-3 py-2 capitalize">{holding.broker_id}</td>
      <td className="px-3 py-2 text-right">{toNum(holding.quantity)}</td>
      <td className="px-3 py-2 text-right">{formatCurrency(holding.avg_buy_price)}</td>
      <td className="px-3 py-2 text-right">
        <PriceChange price={toNum(holding.current_price)} change={toNum(holding.gain_loss)} />
      </td>
      <td className="px-3 py-2 text-right">{formatCurrency(holding.current_value)}</td>
      <td
        className={`px-3 py-2 text-right font-medium ${
          glp >= 0 ? "text-green-600" : "text-red-600"
        }`}
      >
        {glp >= 0 ? "+" : ""}{glp.toFixed(2)}%
      </td>
    </tr>
  );
}
