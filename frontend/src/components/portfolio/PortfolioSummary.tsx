import { usePortfolio } from "@/hooks/usePortfolio";

function formatCurrency(value: number | string): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(num || 0);
}

function formatPercent(value: number | string): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return `${num >= 0 ? "+" : ""}${(num || 0).toFixed(2)}%`;
}

export function PortfolioSummary() {
  const { data: portfolio, isLoading, error } = usePortfolio();

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card p-4 animate-pulse">
            <div className="h-4 w-24 bg-muted rounded mb-2" />
            <div className="h-6 w-32 bg-muted rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (error || !portfolio) {
    return (
      <div className="rounded-lg border bg-card p-4 text-destructive" role="alert">
        Failed to load portfolio data.
      </div>
    );
  }

  const cards = [
    { label: "Current Market Value", value: formatCurrency(portfolio.total_value) },
    { label: "Total Invested", value: formatCurrency(portfolio.total_invested) },
    {
      label: "Total Gain/Loss",
      value: `${formatCurrency(portfolio.total_gain_loss)} (${formatPercent(portfolio.total_gain_loss_percent)})`,
      color: Number(portfolio.total_gain_loss) >= 0 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Day Change",
      value: `${formatCurrency(portfolio.day_change)} (${formatPercent(portfolio.day_change_percent)})`,
      color: Number(portfolio.day_change) >= 0 ? "text-green-600" : "text-red-600",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Portfolio summary">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">{card.label}</p>
          <p className={`text-xl font-semibold mt-1 ${card.color || ""}`}>
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}
