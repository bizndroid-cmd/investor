import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPredictionHistory, getPredictionAverage, computePredictionScore,
  getTodayPrediction, getPortfolioImpact, getMoodCalendar,
} from "@/api/predictions";
import type { CalendarEntry } from "@/api/predictions";
import {
  TrendingUp, TrendingDown, Minus, Flame, Brain,
  RefreshCw, Zap, ChevronDown, ChevronUp, Info, Award, BarChart3,
} from "lucide-react";

export function PredictionsPage() {
  const queryClient = useQueryClient();
  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ["predictions-history"],
    queryFn: () => getPredictionHistory(60),
  });

  const { data: average } = useQuery({
    queryKey: ["predictions-average"],
    queryFn: () => getPredictionAverage(30),
  });

  const { data: todayPred } = useQuery({
    queryKey: ["predictions-today"],
    queryFn: getTodayPrediction,
  });

  const { data: impact } = useQuery({
    queryKey: ["predictions-impact"],
    queryFn: getPortfolioImpact,
  });

  const { data: calendar } = useQuery({
    queryKey: ["predictions-calendar"],
    queryFn: () => getMoodCalendar(30),
  });

  const scorePendingMutation = useMutation({
    mutationFn: async () => {
      const pending = history?.filter((e) => !e.scored) ?? [];
      for (const p of pending) {
        await computePredictionScore(p.prediction_date);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["predictions-history"] });
      queryClient.invalidateQueries({ queryKey: ["predictions-average"] });
    },
  });

  const scoredEntries = history?.filter((e) => e.scored) ?? [];
  const pendingEntries = history?.filter((e) => !e.scored) ?? [];
  const streak = computeStreak(scoredEntries);
  const grade = getGrade(average?.average_score);
  const trend = computeTrend(scoredEntries);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="h-6 w-6 text-purple-600" />
            AI Prediction Accuracy
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Tracking how well the AI reads the market for your portfolio
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pendingEntries.length > 0 && (
            <button
              onClick={() => scorePendingMutation.mutate()}
              disabled={scorePendingMutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-md bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-700 disabled:opacity-50 transition-all hover:scale-105"
            >
              <Zap className="h-3.5 w-3.5" />
              {scorePendingMutation.isPending ? "Scoring..." : `Score ${pendingEntries.length} Pending`}
            </button>
          )}
          <button
            onClick={() => refetchHistory()}
            className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Hero Score Card */}
      <div className="rounded-xl border-2 border-purple-200 bg-gradient-to-br from-purple-50 via-white to-blue-50 p-6 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Main Score */}
          <div className="flex flex-col items-center justify-center">
            <div className="relative">
              <svg className="w-28 h-28" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="#e5e7eb" strokeWidth="8" />
                <circle
                  cx="50" cy="50" r="42"
                  fill="none"
                  stroke={getScoreColor(average?.average_score)}
                  strokeWidth="8"
                  strokeDasharray={`${(average?.average_score ?? 0) * 2.64} 264`}
                  strokeLinecap="round"
                  transform="rotate(-90 50 50)"
                  className="transition-all duration-1000"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold">{average?.average_score ?? "—"}%</span>
                <span className="text-xs text-muted-foreground">accuracy</span>
              </div>
            </div>
          </div>

          {/* Grade */}
          <div className="flex flex-col items-center justify-center">
            <Award className={`h-8 w-8 mb-1 ${grade.color}`} />
            <span className={`text-3xl font-black ${grade.color}`}>{grade.letter}</span>
            <span className="text-xs text-muted-foreground mt-1">{grade.label}</span>
          </div>

          {/* Streak */}
          <div className="flex flex-col items-center justify-center">
            <Flame className={`h-8 w-8 mb-1 ${streak > 0 ? "text-orange-500" : "text-gray-300"}`} />
            <span className="text-3xl font-bold">{streak > 0 ? streak : "—"}</span>
            <span className="text-xs text-muted-foreground mt-1">
              {streak > 0 ? `day streak (>60%)` : "Build your streak"}
            </span>
          </div>

          {/* Trend */}
          <div className="flex flex-col items-center justify-center">
            {trend === "improving" ? (
              <TrendingUp className="h-8 w-8 mb-1 text-green-500" />
            ) : trend === "declining" ? (
              <TrendingDown className="h-8 w-8 mb-1 text-red-500" />
            ) : (
              <BarChart3 className="h-8 w-8 mb-1 text-gray-400" />
            )}
            <span className="text-sm font-semibold capitalize">{trend}</span>
            <span className="text-xs text-muted-foreground mt-1">recent trend</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MiniStat label="Total Predictions" value={String(history?.length ?? 0)} icon="🧠" />
        <MiniStat label="Scored" value={String(scoredEntries.length)} icon="✅" />
        <MiniStat label="Best Score" value={average?.highest_score ? `${average.highest_score}%` : "—"} icon="🏆" />
        <MiniStat label="Worst Score" value={average?.lowest_score ? `${average.lowest_score}%` : "—"} icon="📉" />
      </div>

      {/* TODAY'S PREDICTION - Hero Card */}
      {todayPred?.has_prediction && (
        <div className="rounded-xl border-2 border-indigo-200 bg-gradient-to-r from-indigo-50 to-purple-50 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-indigo-800 flex items-center gap-2">
              🔮 Today's AI Prediction
              <span className="text-xs font-normal text-indigo-500">({todayPred.prediction_date})</span>
            </h3>
            <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
              {todayPred.provider}/{todayPred.model}
            </span>
          </div>
          
          <div className="flex items-center gap-4 mb-3">
            <div className={`text-3xl font-black ${todayPred.market_mood === "bullish" ? "text-green-600" : todayPred.market_mood === "bearish" ? "text-red-600" : "text-gray-600"}`}>
              {todayPred.market_mood === "bullish" ? "📈 BULLISH" : todayPred.market_mood === "bearish" ? "📉 BEARISH" : "➡️ NEUTRAL"}
            </div>
          </div>
          
          {todayPred.market_mood_reason && (
            <p className="text-sm text-indigo-700 mb-3 italic">"{todayPred.market_mood_reason}"</p>
          )}

          {/* Ticker predictions */}
          {todayPred.ticker_predictions && todayPred.ticker_predictions.length > 0 && (
            <div className="mt-3 pt-3 border-t border-indigo-200">
              <p className="text-xs font-semibold text-indigo-600 mb-2">Per-Stock Predictions:</p>
              <div className="flex flex-wrap gap-1.5">
                {todayPred.ticker_predictions.filter(t => t.expected_direction !== "flat").slice(0, 12).map((t) => (
                  <span
                    key={t.ticker}
                    className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
                      t.expected_direction === "up" ? "bg-emerald-500/10 text-emerald-500" :
                      t.expected_direction === "down" ? "bg-red-500/10 text-red-500" :
                      "bg-muted text-muted-foreground"
                    }`}
                  >
                    {t.expected_direction === "up" ? "↑" : t.expected_direction === "down" ? "↓" : "→"}
                    {t.ticker}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* PORTFOLIO IMPACT CALCULATOR */}
      {impact?.has_data && (
        <div className="rounded-xl border bg-card p-5">
          <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
            💰 AI Impact Calculator
            <span className="text-xs font-normal text-muted-foreground">Last {impact.period_days} days</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-3 rounded-lg bg-blue-50 border border-blue-200">
              <p className="text-xs text-blue-600 mb-1">Actual Portfolio Change</p>
              <p className={`text-xl font-bold ${(impact.actual_change ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                {(impact.actual_change ?? 0) >= 0 ? "+" : ""}₹{Math.abs(impact.actual_change ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">{(impact.actual_change_pct ?? 0) >= 0 ? "+" : ""}{impact.actual_change_pct}%</p>
            </div>
            <div className="text-center p-3 rounded-lg bg-purple-50 border border-purple-200">
              <p className="text-xs text-purple-600 mb-1">If You Followed AI</p>
              <p className={`text-xl font-bold ${(impact.hypothetical_change ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                {(impact.hypothetical_change ?? 0) >= 0 ? "+" : ""}₹{Math.abs(impact.hypothetical_change ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">{(impact.hypothetical_change_pct ?? 0) >= 0 ? "+" : ""}{impact.hypothetical_change_pct}%</p>
            </div>
            <div className="text-center p-3 rounded-lg bg-emerald-50 border border-emerald-200">
              <p className="text-xs text-emerald-600 mb-1">AI Edge</p>
              <p className={`text-xl font-bold ${(impact.ai_edge ?? 0) >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                {(impact.ai_edge ?? 0) >= 0 ? "+" : ""}₹{Math.abs(impact.ai_edge ?? 0).toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">
                {impact.correct_calls}/{impact.total_calls} correct calls ({impact.accuracy_rate}%)
              </p>
            </div>
          </div>

          {/* What AI actually suggested */}
          {todayPred?.has_prediction && todayPred.ticker_predictions && todayPred.ticker_predictions.length > 0 && (
            <div className="mt-4 pt-4 border-t">
              <p className="text-xs font-semibold text-muted-foreground mb-2">📋 What the AI suggested (latest):</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {todayPred.ticker_predictions
                  .filter(t => t.expected_direction !== "flat")
                  .slice(0, 8)
                  .map((t) => (
                    <div
                      key={t.ticker}
                      className={`text-xs p-2 rounded-md border ${
                        t.expected_direction === "up"
                          ? "bg-green-50 border-green-200 text-green-700"
                          : "bg-red-50 border-red-200 text-red-700"
                      }`}
                    >
                      <span className="font-bold">{t.expected_direction === "up" ? "↑" : "↓"} {t.ticker}</span>
                      <p className="text-xs opacity-75 mt-0.5 truncate">{t.reason}</p>
                    </div>
                  ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2 italic">
                These are the AI's directional calls. Correct calls amplify the hypothetical returns above.
              </p>
            </div>
          )}
        </div>
      )}

      {/* MOOD CALENDAR HEATMAP */}
      {calendar && calendar.length > 0 && (
        <div className="rounded-xl border bg-card p-5">
          <h3 className="text-sm font-bold mb-3 flex items-center gap-2">
            📅 Mood Calendar
            <span className="text-xs font-normal text-muted-foreground">Last 30 days</span>
          </h3>
          <div className="max-w-sm mx-auto">
            <div className="grid grid-cols-7 gap-1 mb-1">
              {["M","T","W","T","F","S","S"].map((d, i) => (
                <div key={i} className="text-center text-[10px] text-muted-foreground font-medium py-0.5">{d}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {generateCalendarGrid(calendar).map((cell, i) => (
                <div
                  key={i}
                  className={`w-full aspect-square rounded-sm flex items-center justify-center text-[9px] font-bold cursor-default transition-all hover:scale-125 hover:z-10 hover:shadow-md ${
                    cell === null ? "bg-muted/30" :
                    cell.mood === "bullish" ? (cell.scored ? "bg-green-500 text-white" : "bg-emerald-500/20 text-emerald-500") :
                    cell.mood === "bearish" ? (cell.scored ? "bg-red-500 text-white" : "bg-red-500/20 text-red-500") :
                    cell.scored ? "bg-muted-foreground text-white" : "bg-muted text-muted-foreground"
                  }`}
                  title={cell ? `${cell.date}: ${cell.mood}${cell.score ? ` (${cell.score}%)` : " (pending)"}` : "No data"}
                >
                  {cell?.score ? Math.round(cell.score) : cell ? (cell.mood === "bullish" ? "↑" : cell.mood === "bearish" ? "↓" : "·") : ""}
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-center gap-4 mt-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-green-500 rounded-sm" /> Bullish</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-red-500 rounded-sm" /> Bearish</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-muted-foreground rounded-sm" /> Neutral</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-green-200 rounded-sm" /> Pending</span>
          </div>
        </div>
      )}

      {/* How Scoring Works - Collapsible */}
      <HowItWorks />

      {/* Score Timeline */}
      {scoredEntries.length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-purple-500" />
            Score Timeline
          </h3>
          <div className="flex items-end gap-1.5 h-36 border-b pb-2">
            {scoredEntries.slice(0, 20).reverse().map((entry, i) => {
              const score = entry.confidence_score ?? 0;
              const height = Math.max(8, (score / 100) * 100);
              const color = score >= 70 ? "bg-green-500" : score >= 50 ? "bg-amber-400" : score >= 30 ? "bg-orange-400" : "bg-red-400";
              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col items-center justify-end group relative"
                >
                  <div className="absolute -top-8 bg-popover text-popover-foreground text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
                    {entry.prediction_date}: {score}%
                  </div>
                  <div
                    className={`w-full rounded-t ${color} transition-all hover:opacity-80 cursor-pointer`}
                    style={{ height: `${height}%` }}
                  />
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-2">
            <span>Oldest</span>
            <span>Latest →</span>
          </div>
        </div>
      )}

      {/* Detailed Predictions List */}
      {history && history.length > 0 && (
        <div className="rounded-lg border bg-card">
          <div className="p-4 border-b">
            <h3 className="text-sm font-semibold">Prediction Log</h3>
          </div>
          <div className="divide-y">
            {history.map((entry) => (
              <PredictionRow key={entry.prediction_date} entry={entry} />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {(!history || history.length === 0) && (
        <div className="rounded-lg border bg-card p-12 text-center">
          <Brain className="h-12 w-12 text-purple-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">No predictions yet</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Generate a portfolio briefing from the News page. Each briefing creates a prediction 
            that gets scored the next trading day when market data comes in.
          </p>
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="rounded-lg border bg-card p-3 text-center">
      <span className="text-lg">{icon}</span>
      <p className="text-xl font-bold mt-1">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </div>
  );
}

function PredictionRow({ entry }: { entry: any }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="px-4 py-3 hover:bg-muted/30 cursor-pointer" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-muted-foreground w-16">
            {new Date(entry.prediction_date).toLocaleDateString([], { month: "short", day: "numeric" })}
          </span>
          <MoodBadge mood={entry.market_mood} />
        </div>
        <div className="flex items-center gap-3">
          {entry.scored ? (
            <div className="flex items-center gap-2">
              <ScoreRing score={entry.confidence_score} size={32} />
              <div className="text-right">
                <p className="text-sm font-bold">{entry.confidence_score}%</p>
                <p className="text-xs text-muted-foreground">
                  M:{entry.mood_accuracy}% · T:{entry.ticker_accuracy}%
                </p>
              </div>
            </div>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded-full">
              <span className="w-1.5 h-1.5 bg-amber-400 rounded-full animate-pulse" />
              Pending
            </span>
          )}
          {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </div>
      </div>
      {expanded && (
        <div className="mt-3 pl-20 text-xs text-muted-foreground space-y-1 border-t pt-2">
          <p><strong>Model:</strong> {entry.provider}/{entry.model}</p>
          {entry.scored && (
            <>
              <p><strong>Mood Accuracy:</strong> {entry.mood_accuracy}% — AI predicted "{entry.market_mood}", portfolio {entry.mood_accuracy === 100 ? "moved in that direction ✓" : entry.mood_accuracy === 50 ? "was flat (partial credit)" : "moved opposite ✗"}</p>
              <p><strong>Ticker Accuracy:</strong> {entry.ticker_accuracy}% — per-stock direction predictions vs actual price changes</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ScoreRing({ score, size = 32 }: { score: number; size?: number }) {
  const r = (size - 6) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (score / 100) * circumference;

  return (
    <svg width={size} height={size} className="shrink-0">
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e5e7eb" strokeWidth="3" />
      <circle
        cx={size/2} cy={size/2} r={r}
        fill="none"
        stroke={getScoreColor(score)}
        strokeWidth="3"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
      />
    </svg>
  );
}

function HowItWorks() {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/30"
      >
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 text-blue-500" />
          <span className="text-sm font-medium">How does scoring work?</span>
        </div>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && (
        <div className="px-4 pb-4 text-xs text-muted-foreground space-y-3 border-t pt-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <p className="font-semibold text-foreground">📊 Mood Accuracy (40% weight)</p>
              <p>Did the AI correctly predict whether your portfolio would go UP (bullish), DOWN (bearish), or stay FLAT (neutral)?</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Correct direction → 100 points</li>
                <li>Predicted neutral OR actual was flat → 50 points</li>
                <li>Completely wrong direction → 0 points</li>
              </ul>
            </div>
            <div className="space-y-2">
              <p className="font-semibold text-foreground">📈 Ticker Accuracy (60% weight)</p>
              <p>For each stock, did the AI correctly predict UP/DOWN/FLAT?</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Correct direction → full credit</li>
                <li>One side is neutral → half credit</li>
                <li>Wrong direction → no credit</li>
                <li>Score = (correct / total tickers) × 100</li>
              </ul>
            </div>
          </div>
          <div className="mt-3 p-3 bg-purple-50 rounded-md">
            <p className="font-semibold text-purple-800">Formula:</p>
            <p className="font-mono text-purple-700 mt-1">Confidence = (Mood × 40%) + (Ticker × 60%)</p>
          </div>
        </div>
      )}
    </div>
  );
}

function MoodBadge({ mood }: { mood: string }) {
  const config = {
    bullish: { icon: <TrendingUp className="h-3 w-3" />, bg: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" },
    bearish: { icon: <TrendingDown className="h-3 w-3" />, bg: "bg-red-500/10 text-red-500 border-red-500/20" },
    neutral: { icon: <Minus className="h-3 w-3" />, bg: "bg-muted text-muted-foreground border-border" },
  }[mood] || { icon: <Minus className="h-3 w-3" />, bg: "bg-muted text-muted-foreground border-border" };

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${config.bg}`}>
      {config.icon}
      {mood}
    </span>
  );
}

// Helpers
function getScoreColor(score: number | null | undefined): string {
  if (score == null) return "#d1d5db";
  if (score >= 70) return "#22c55e";
  if (score >= 50) return "#f59e0b";
  if (score >= 30) return "#f97316";
  return "#ef4444";
}

function getGrade(score: number | null | undefined): { letter: string; label: string; color: string } {
  if (score == null) return { letter: "—", label: "Not enough data", color: "text-gray-400" };
  if (score >= 85) return { letter: "A+", label: "Exceptional", color: "text-green-600" };
  if (score >= 75) return { letter: "A", label: "Excellent", color: "text-green-600" };
  if (score >= 65) return { letter: "B+", label: "Good", color: "text-blue-600" };
  if (score >= 55) return { letter: "B", label: "Above Average", color: "text-blue-600" };
  if (score >= 45) return { letter: "C", label: "Average", color: "text-amber-600" };
  if (score >= 35) return { letter: "D", label: "Below Average", color: "text-orange-600" };
  return { letter: "F", label: "Unreliable", color: "text-red-600" };
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

function computeTrend(entries: { confidence_score: number | null }[]): string {
  const recent = entries.slice(0, 3).filter(e => e.confidence_score != null);
  const older = entries.slice(3, 6).filter(e => e.confidence_score != null);

  if (recent.length < 2 || older.length < 1) return "building";

  const recentAvg = recent.reduce((s, e) => s + (e.confidence_score ?? 0), 0) / recent.length;
  const olderAvg = older.reduce((s, e) => s + (e.confidence_score ?? 0), 0) / older.length;

  if (recentAvg > olderAvg + 5) return "improving";
  if (recentAvg < olderAvg - 5) return "declining";
  return "stable";
}

function generateCalendarGrid(calendar: CalendarEntry[]): (CalendarEntry | null)[] {
  if (!calendar.length) return [];

  // Build a 5-week grid (35 cells)
  const grid: (CalendarEntry | null)[] = [];
  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - 34); // 5 weeks back

  // Align to Monday
  const dayOfWeek = startDate.getDay();
  const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  startDate.setDate(startDate.getDate() + mondayOffset);

  const calendarMap = new Map(calendar.map(c => [c.date, c]));

  for (let i = 0; i < 35; i++) {
    const d = new Date(startDate);
    d.setDate(d.getDate() + i);
    const dateStr = d.toISOString().split("T")[0];
    const entry = calendarMap.get(dateStr);

    if (d > today) {
      grid.push(null);
    } else if (entry) {
      grid.push(entry);
    } else {
      grid.push(null);
    }
  }

  return grid;
}
