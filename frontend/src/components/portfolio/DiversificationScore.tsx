import { useMemo } from "react";
import { usePortfolio } from "@/hooks/usePortfolio";

export function DiversificationScore() {
  const { data: portfolio } = usePortfolio();

  const score = useMemo(() => {
    if (!portfolio || portfolio.holdings.length === 0) return null;

    // Simple diversification score based on number of unique tickers and brokers
    const uniqueTickers = new Set(portfolio.holdings.map((h) => h.ticker)).size;
    const uniqueBrokers = new Set(portfolio.holdings.map((h) => h.broker_id)).size;

    // Herfindahl-Hirschman Index (HHI) based on allocation
    const total = portfolio.total_value;
    if (total === 0) return null;

    const shares = portfolio.holdings.map((h) => h.current_value / total);
    const hhi = shares.reduce((sum, s) => sum + s * s, 0);

    // Convert HHI to a 0-100 score (lower HHI = more diversified = higher score)
    // HHI ranges from 1/n (perfectly diversified) to 1 (single stock)
    const minHHI = 1 / portfolio.holdings.length;
    const normalizedScore = Math.round(((1 - hhi) / (1 - minHHI)) * 100) || 0;

    return {
      score: Math.min(100, Math.max(0, normalizedScore)),
      uniqueTickers,
      uniqueBrokers,
    };
  }, [portfolio]);

  if (!score) {
    return (
      <div className="rounded-lg border bg-card p-4 text-center text-muted-foreground">
        No diversification data available.
      </div>
    );
  }

  const getScoreColor = (s: number) => {
    if (s >= 70) return "text-green-600";
    if (s >= 40) return "text-yellow-600";
    return "text-red-600";
  };

  const getScoreLabel = (s: number) => {
    if (s >= 70) return "Well Diversified";
    if (s >= 40) return "Moderately Diversified";
    return "Concentrated";
  };

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-medium mb-3">Diversification Score</h3>
      <div className="flex items-center gap-4">
        <div className={`text-3xl font-bold ${getScoreColor(score.score)}`}>
          {score.score}
        </div>
        <div className="text-sm text-muted-foreground">
          <p className={getScoreColor(score.score)}>{getScoreLabel(score.score)}</p>
          <p>{score.uniqueTickers} stocks across {score.uniqueBrokers} brokers</p>
        </div>
      </div>
    </div>
  );
}
