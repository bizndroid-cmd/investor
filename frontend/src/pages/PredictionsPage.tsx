import { useQuery } from "@tanstack/react-query";
import { getPredictionHistory, getPredictionAverage } from "@/api/predictions";
import { TrendingUp, TrendingDown, Minus, Trophy, Target, Flame, Brain } from "lucide-react";

export function PredictionsPage() {
  const { data: history } = useQuery({
    queryKey: ["predictions-history"],
    queryFn: () => getPredictionHistory(60),
  });

  const { data: average } = useQuery({
    queryKey: ["predictions-average"],
    queryFn: () => getPredictionAverage(30),
  });

  const scoredEntries = history?.filter((e) => e.scored) ?? [];
  const streak = computeStreak(scoredEntries);
  const grade = getGrade(average?.average_score);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Brain className="h-6 w-6 text-purple-600" />
          AI Prediction Accuracy
        </h2>
        <span className="text-xs text-muted-foreground">
          How well does the AI predict market movements?
        </span>
      </div>

      {/* Hero Stats Row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <ScoreCard
          label="Confidence Score"
          value={average?.average_score != null ? `${average.average_score}%` : "—"}
          subtitle="30-day average"
          icon={<Target className="h-5 w-5 text-blue-600" />}
          color="blue"
        />
        <ScoreCard
          label="AI Grade"
          value={grade.letter}
          subtitle={grade.label}
          icon={<Trophy className="h-5 w-5 text-amber-500" />}
          color="amber"
        />
        <ScoreCard
          label="Prediction Streak"
          value={streak > 0 ? `${streak} 🔥` : "—"}
          subtitle={streak > 0 ? `${streak} days above 60%` : "Build your streak"}
          icon={<Flame className="h-5 w-5 text-orange-500" />}
          color="orange"
        />
        <ScoreCard
          label="Total Predictions"
          value={String(average?.total_predictions ?? 0)}
          subtitle={`${average?.scored_predictions ?? 0} scored`}
          icon={<Brain className="h-5 w-5 text-purple-500" />}
          color="purple"
        />
      </div>

      {/* Confidence Explanation */}
      <div className="rounded-lg border bg-gradient-to-r from-purple-50 to-blue-50 p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-2">How does this work?</h3>
        <p className="text-xs text-gray-600 leading-relaxed">
          Every time the AI generates a briefing, it predicts the <strong>market mood</strong> (bullish/bearish/neutral) 
          and <strong>per-ticker direction</strong> (up/down/flat) for each stock in your portfolio. The next trading day, 
          we compare those predictions against <strong>actual price movements</strong> from your portfolio snapshots.
        </p>
        <div className="grid grid-cols-3 gap-2 mt-3 text-center">
          <div className="rounded-md bg-white/80 p-2">
            <p className="text-lg font-bold text-green-600">70-100%</p>
            <p className="text-xs text-gray-500">Strong signal</p>
          </div>
          <div className="rounded-md bg-white/80 p-2">
            <p className="text-lg font-bold text-amber-600">40-69%</p>
            <p className="text-xs text-gray-500">Mixed results</p>
          </div>
          <div className="rounded-md bg-white/80 p-2">
            <p className="text-lg font-bold text-red-500">0-39%</p>
            <p className="text-xs text-gray-500">Unreliable</p>
          </div>
        </div>
      </div>

      {/* Score History */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-semibold mb-4">Score History</h3>
        {scoredEntries.length === 0 ? (
          <div className="text-center py-8">
            <Brain className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
            <p className="text-sm text-muted-foreground">No scored predictions yet.</p>
            <p className="text-xs text-muted-foreground mt-1">
              Generate a briefing today, and the score will be computed tomorrow once market data is available.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Visual bar chart */}
            <div className="flex items-end gap-1 h-32 border-b pb-2">
              {scoredEntries.slice(0, 30).reverse().map((entry, i) => {
                const score = entry.confidence_score ?? 0;
                const height = Math.max(4, (score / 100) * 100);
                const color = score >= 70 ? "bg-green-500" : score >= 40 ? "bg-amber-400" : "bg-red-400";
                return (
                  <div
                    key={i}
                    className="flex-1 flex flex-col items-center justify-end"
                    title={`${entry.prediction_date}: ${score}%`}
                  >
                    <div
                      className={`w-full rounded-t ${color} transition-all hover:opacity-80`}
                      style={{ height: `${height}%` }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>30 days ago</span>
              <span>Today</span>
            </div>
          </div>
        )}
      </div>

      {/* Detailed History Table */}
      {history && history.length > 0 && (
        <div className="rounded-lg border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Date</th>
                <th className="px-4 py-2 text-left font-medium">Mood Predicted</th>
                <th className="px-4 py-2 text-center font-medium">Score</th>
                <th className="px-4 py-2 text-center font-medium">Mood Acc.</th>
                <th className="px-4 py-2 text-center font-medium">Ticker Acc.</th>
                <th className="px-4 py-2 text-right font-medium">Model</th>
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 15).map((entry) => (
                <tr key={entry.prediction_date} className="border-b last:border-0 hover:bg-muted/30">
                  <td className="px-4 py-2 font-mono text-xs">
                    {new Date(entry.prediction_date).toLocaleDateString([], { month: "short", day: "numeric" })}
                  </td>
                  <td className="px-4 py-2">
                    <MoodBadge mood={entry.market_mood} />
                  </td>
                  <td className="px-4 py-2 text-center">
                    {entry.scored ? (
                      <ConfidenceBadge score={entry.confidence_score!} />
                    ) : (
                      <span className="text-xs text-muted-foreground">Pending</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-center text-xs font-mono">
                    {entry.mood_accuracy != null ? `${entry.mood_accuracy}%` : "—"}
                  </td>
                  <td className="px-4 py-2 text-center text-xs font-mono">
                    {entry.ticker_accuracy != null ? `${entry.ticker_accuracy}%` : "—"}
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-muted-foreground font-mono">
                    {entry.model}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ScoreCard({
  label,
  value,
  subtitle,
  icon,
  color,
}: {
  label: string;
  value: string;
  subtitle: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
    </div>
  );
}

function MoodBadge({ mood }: { mood: string }) {
  const config = {
    bullish: { icon: <TrendingUp className="h-3 w-3" />, bg: "bg-green-100 text-green-700" },
    bearish: { icon: <TrendingDown className="h-3 w-3" />, bg: "bg-red-100 text-red-700" },
    neutral: { icon: <Minus className="h-3 w-3" />, bg: "bg-gray-100 text-gray-700" },
  }[mood] || { icon: <Minus className="h-3 w-3" />, bg: "bg-gray-100 text-gray-700" };

  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${config.bg}`}>
      {config.icon}
      {mood}
    </span>
  );
}

function ConfidenceBadge({ score }: { score: number }) {
  const color = score >= 70 ? "text-green-700 bg-green-100" : score >= 40 ? "text-amber-700 bg-amber-100" : "text-red-700 bg-red-100";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-bold ${color}`}>
      {score}%
    </span>
  );
}

function getGrade(score: number | null | undefined): { letter: string; label: string } {
  if (score == null) return { letter: "—", label: "Not enough data" };
  if (score >= 85) return { letter: "A+", label: "Exceptional" };
  if (score >= 75) return { letter: "A", label: "Excellent" };
  if (score >= 65) return { letter: "B+", label: "Good" };
  if (score >= 55) return { letter: "B", label: "Above Average" };
  if (score >= 45) return { letter: "C", label: "Average" };
  if (score >= 35) return { letter: "D", label: "Below Average" };
  return { letter: "F", label: "Unreliable" };
}

function computeStreak(entries: { confidence_score: number | null }[]): number {
  let streak = 0;
  for (const entry of entries) {
    if (entry.confidence_score != null && entry.confidence_score >= 60) {
      streak++;
    } else {
      break;
    }
  }
  return streak;
}
