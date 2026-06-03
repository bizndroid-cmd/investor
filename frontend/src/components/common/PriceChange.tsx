import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";

interface PriceChangeProps {
  price: number;
  change: number;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(value);
}

export function PriceChange({ price, change }: PriceChangeProps) {
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    setFlash(true);
    const timer = setTimeout(() => setFlash(false), 3000);
    return () => clearTimeout(timer);
  }, [price]);

  const isPositive = change >= 0;

  return (
    <span
      className={`inline-flex items-center gap-1 transition-colors duration-300 ${
        flash
          ? isPositive
            ? "text-green-600 bg-green-50 rounded px-1"
            : "text-red-600 bg-red-50 rounded px-1"
          : ""
      }`}
      aria-live="polite"
      aria-label={`Price ${formatCurrency(price)}, ${isPositive ? "up" : "down"}`}
    >
      {isPositive ? (
        <TrendingUp className="h-3 w-3" aria-hidden="true" />
      ) : (
        <TrendingDown className="h-3 w-3" aria-hidden="true" />
      )}
      {formatCurrency(price)}
    </span>
  );
}
