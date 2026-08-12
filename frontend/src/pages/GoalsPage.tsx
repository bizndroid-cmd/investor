import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getGoals, createGoal, deleteGoal, addEntry, getGoalEntries, deleteEntry, getWealthSummary,
  type GoalProgress, type CreateGoalBody, type AddEntryBody, type WealthSummary,
} from "@/api/goals";
import {
  Target, Plus, Trash2, PiggyBank, Home, Car, Shield,
  Loader2, ChevronDown, ChevronUp, Coins, X, Compass, Flame, Trophy, Sparkles,
} from "lucide-react";

const GOAL_ICONS: Record<string, any> = {
  target: Target, retirement: PiggyBank, home: Home, car: Car, emergency: Shield, coins: Coins,
};

const GOAL_COLORS: Record<string, string> = {
  blue: "text-blue-500", green: "text-emerald-500", amber: "text-amber-500",
  purple: "text-purple-500", red: "text-red-500", pink: "text-pink-500",
};

const GOAL_BG: Record<string, string> = {
  blue: "from-blue-500/10 to-blue-500/0",
  green: "from-emerald-500/10 to-emerald-500/0",
  amber: "from-amber-500/10 to-amber-500/0",
  purple: "from-purple-500/10 to-purple-500/0",
  red: "from-red-500/10 to-red-500/0",
  pink: "from-pink-500/10 to-pink-500/0",
};

const CATEGORY_LABELS: Record<string, string> = {
  savings: "Savings", fd: "Fixed Deposit", real_estate: "Real Estate",
  crypto: "Crypto", gold_physical: "Physical Gold", ppf: "PPF", nps: "NPS", other: "Other",
};

export function GoalsPage() {
  const [showCreateGoal, setShowCreateGoal] = useState(false);
  const { data: goals, isLoading } = useQuery({ queryKey: ["goals"], queryFn: getGoals });
  const { data: summary } = useQuery({ queryKey: ["wealth-summary"], queryFn: getWealthSummary });

  if (isLoading) return <LoadingSkeleton />;

  const activeGoals = goals?.filter((g) => g.is_active) || [];
  const totalProgress = activeGoals.length > 0
    ? activeGoals.reduce((sum, g) => sum + g.progress_pct, 0) / activeGoals.length
    : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-blue-500/5 via-card to-emerald-500/5 p-6 md:p-8">
        <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-blue-500/5 to-transparent rounded-full -translate-y-1/2 translate-x-1/2" />
        <div className="relative">
          <div className="flex items-center gap-2 mb-1">
            <Compass className="h-5 w-5 text-blue-500" />
            <span className="text-xs font-medium text-blue-500 uppercase tracking-wider">Your Blueprint</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-bold mt-2">
            {activeGoals.length === 0 ? "Start your financial journey" : `${activeGoals.length} active goal${activeGoals.length > 1 ? "s" : ""}`}
          </h1>
          {activeGoals.length > 0 && (
            <div className="flex items-center gap-4 mt-4">
              <div className="flex-1 max-w-xs">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-muted-foreground">Overall progress</span>
                  <span className="font-bold text-blue-500">{totalProgress.toFixed(0)}%</span>
                </div>
                <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all duration-1000"
                    style={{ width: `${Math.min(100, totalProgress)}%` }}
                  />
                </div>
              </div>
              {totalProgress >= 50 && (
                <div className="flex items-center gap-1.5 text-amber-500">
                  <Flame className="h-4 w-4" />
                  <span className="text-xs font-medium">On fire!</span>
                </div>
              )}
            </div>
          )}
          <button onClick={() => setShowCreateGoal(true)} className="btn-primary text-xs mt-5">
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            New Goal
          </button>
        </div>
      </div>

      {showCreateGoal && <CreateGoalForm onClose={() => setShowCreateGoal(false)} />}

      {/* Wealth Snapshot */}
      {summary && <WealthSnapshot summary={summary} />}

      {/* Goals Grid */}
      {activeGoals.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {activeGoals.map((g) => <GoalCard key={g.id} goal={g} />)}
        </div>
      ) : (
        <EmptyState onAdd={() => setShowCreateGoal(true)} />
      )}
    </div>
  );
}

// ============================================================
// WEALTH SNAPSHOT
// ============================================================
function WealthSnapshot({ summary }: { summary: WealthSummary }) {
  const formatCompact = (v: number) => {
    if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(2)} Cr`;
    if (v >= 100_000) return `₹${(v / 100_000).toFixed(1)}L`;
    return `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
  };

  const total = summary.total_wealth_inr;
  const parts = [
    { label: "Stocks", value: summary.breakdown.stocks_inr, color: "bg-blue-500" },
    { label: "ETFs", value: summary.breakdown.etf_inr, color: "bg-emerald-500" },
    { label: "Others", value: summary.breakdown.manual_inr, color: "bg-amber-500" },
  ].filter((p) => p.value > 0);

  return (
    <div className="bento-card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Total Wealth</p>
          <p className="text-2xl font-bold mt-0.5">{formatCompact(total)}</p>
        </div>
        <div className="h-12 w-12 rounded-full bg-gradient-to-br from-blue-500/20 to-emerald-500/20 flex items-center justify-center">
          <Trophy className="h-5 w-5 text-amber-500" />
        </div>
      </div>
      {/* Stacked bar */}
      <div className="h-3 rounded-full bg-muted overflow-hidden flex">
        {parts.map((p) => (
          <div
            key={p.label}
            className={`h-full ${p.color} transition-all`}
            style={{ width: `${total > 0 ? (p.value / total) * 100 : 0}%` }}
          />
        ))}
      </div>
      <div className="flex gap-4 mt-3">
        {parts.map((p) => (
          <div key={p.label} className="flex items-center gap-1.5 text-xs">
            <div className={`h-2 w-2 rounded-full ${p.color}`} />
            <span className="text-muted-foreground">{p.label}</span>
            <span className="font-medium">{formatCompact(p.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// GOAL CARD
// ============================================================
function GoalCard({ goal }: { goal: GoalProgress }) {
  const [expanded, setExpanded] = useState(false);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const queryClient = useQueryClient();
  const IconComp = GOAL_ICONS[goal.icon] || Target;
  const colorClass = GOAL_COLORS[goal.color] || "text-blue-500";
  const bgGradient = GOAL_BG[goal.color] || GOAL_BG.blue;
  const currency = goal.target_currency === "INR" ? "₹" : "$";
  const locale = goal.target_currency === "INR" ? "en-IN" : "en-US";

  const deleteMut = useMutation({
    mutationFn: () => deleteGoal(goal.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });

  const formatAmount = (v: number) => `${currency}${v.toLocaleString(locale, { maximumFractionDigits: 0 })}`;
  const remaining = Math.max(0, goal.target_amount - goal.current_total);

  return (
    <div className={`bento-card bg-gradient-to-br ${bgGradient} relative overflow-hidden`}>
      {/* Achievement badge */}
      {goal.progress_pct >= 100 && (
        <div className="absolute top-3 right-3 flex items-center gap-1 text-amber-500 bg-amber-500/10 rounded-full px-2 py-0.5">
          <Sparkles className="h-3 w-3" />
          <span className="text-[10px] font-bold">ACHIEVED</span>
        </div>
      )}

      <div className="flex items-start gap-3">
        <div className={`h-11 w-11 rounded-xl flex items-center justify-center ${colorClass} bg-current/10 shrink-0`}>
          <IconComp className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold truncate">{goal.name}</h3>
            <div className="flex items-center gap-1 shrink-0 ml-2">
              <button onClick={() => setExpanded(!expanded)} className="btn-icon h-6 w-6">
                {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              </button>
              <button onClick={() => deleteMut.mutate()} className="btn-icon h-6 w-6 text-muted-foreground hover:text-red-500">
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          </div>

          {/* Amount progress */}
          <div className="mt-2">
            <div className="flex items-baseline gap-1.5">
              <span className={`text-lg font-bold ${colorClass}`}>{formatAmount(goal.current_total)}</span>
              <span className="text-xs text-muted-foreground">/ {formatAmount(goal.target_amount)}</span>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-3">
            <div className="h-2.5 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${
                  goal.color === "green" ? "bg-emerald-500" :
                  goal.color === "amber" ? "bg-amber-500" :
                  goal.color === "purple" ? "bg-purple-500" :
                  goal.color === "red" ? "bg-red-500" : "bg-blue-500"
                }`}
                style={{ width: `${Math.min(100, goal.progress_pct)}%` }}
              />
            </div>
            <div className="flex justify-between mt-1.5 text-[10px]">
              <span className={`font-bold ${colorClass}`}>{goal.progress_pct.toFixed(0)}%</span>
              <span className="text-muted-foreground">
                {goal.months_to_goal
                  ? goal.months_to_goal < 12
                    ? `~${Math.round(goal.months_to_goal)} mo to go`
                    : `~${(goal.months_to_goal / 12).toFixed(1)} yr to go`
                  : remaining > 0
                    ? `${formatAmount(remaining)} remaining`
                    : ""
                }
              </span>
            </div>
          </div>

          {/* Source breakdown pills */}
          <div className="flex flex-wrap gap-1.5 mt-3">
            {goal.stocks_value > 0 && (
              <span className="text-[9px] font-medium bg-blue-500/10 text-blue-500 rounded-full px-2 py-0.5">
                Stocks {formatAmount(goal.stocks_value)}
              </span>
            )}
            {goal.etf_value > 0 && (
              <span className="text-[9px] font-medium bg-emerald-500/10 text-emerald-500 rounded-full px-2 py-0.5">
                ETFs {formatAmount(goal.etf_value)}
              </span>
            )}
            {goal.entries_total > 0 && (
              <span className="text-[9px] font-medium bg-amber-500/10 text-amber-500 rounded-full px-2 py-0.5">
                Deposits {formatAmount(goal.entries_total)}
              </span>
            )}
            {goal.deadline && (
              <span className="text-[9px] font-medium bg-muted text-muted-foreground rounded-full px-2 py-0.5">
                Due {new Date(goal.deadline).toLocaleDateString(undefined, { month: "short", year: "numeric" })}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Expanded: entries */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-border animate-fade-in">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium">Deposits & Entries ({goal.entries_count})</span>
            <button onClick={() => setShowAddEntry(!showAddEntry)} className="text-[10px] text-primary font-medium hover:underline">
              {showAddEntry ? "Cancel" : "+ Add Entry"}
            </button>
          </div>
          {showAddEntry && <AddEntryForm goalId={goal.id} currency={goal.target_currency} onClose={() => setShowAddEntry(false)} />}
          <EntriesList goalId={goal.id} />
        </div>
      )}
    </div>
  );
}

// ============================================================
// ENTRIES
// ============================================================
function EntriesList({ goalId }: { goalId: string }) {
  const queryClient = useQueryClient();
  const { data: entries, isLoading } = useQuery({
    queryKey: ["goal-entries", goalId],
    queryFn: () => getGoalEntries(goalId),
  });

  const deleteMut = useMutation({
    mutationFn: deleteEntry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goal-entries", goalId] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["wealth-summary"] });
    },
  });

  if (isLoading) return <Loader2 className="h-4 w-4 animate-spin mx-auto" />;
  if (!entries || entries.length === 0) return <p className="text-xs text-muted-foreground text-center py-3">No entries yet. Add your first deposit.</p>;

  return (
    <div className="space-y-1.5 max-h-48 overflow-y-auto">
      {entries.map((e) => (
        <div key={e.id} className="flex items-center justify-between text-xs py-2 px-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-md bg-muted flex items-center justify-center text-[9px]">
              {CATEGORY_LABELS[e.category]?.[0] || "•"}
            </div>
            <div>
              <span className="font-medium">{e.label}</span>
              <span className="text-muted-foreground ml-1.5 text-[10px]">{CATEGORY_LABELS[e.category]}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <span className="font-bold">{e.currency === "INR" ? "₹" : "$"}{e.amount.toLocaleString()}</span>
              <p className="text-[9px] text-muted-foreground">{new Date(e.entry_date).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}</p>
            </div>
            <button onClick={() => deleteMut.mutate(e.id)} className="text-muted-foreground hover:text-red-500 transition-colors">
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

function AddEntryForm({ goalId, currency, onClose }: { goalId: string; currency: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState("savings");
  const [label, setLabel] = useState("");
  const [amount, setAmount] = useState("");
  const [entryCurrency, setEntryCurrency] = useState(currency);
  const [entryDate, setEntryDate] = useState(new Date().toISOString().split("T")[0]);

  const mutation = useMutation({
    mutationFn: (body: AddEntryBody) => addEntry(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goal-entries", goalId] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["wealth-summary"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!label || !amount) return;
    mutation.mutate({
      goal_id: goalId,
      category,
      label,
      amount: parseFloat(amount),
      currency: entryCurrency,
      entry_date: entryDate,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4 p-3 rounded-xl border bg-muted/10 animate-fade-in">
      <select value={category} onChange={(e) => setCategory(e.target.value)} className="input-field text-xs">
        {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label" className="input-field text-xs" required />
      <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount" step="0.01" className="input-field text-xs" required />
      <div className="flex gap-1">
        <select value={entryCurrency} onChange={(e) => setEntryCurrency(e.target.value)} className="input-field text-xs w-14">
          <option value="INR">₹</option>
          <option value="USD">$</option>
        </select>
        <input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} className="input-field text-xs flex-1" />
      </div>
      <div className="flex gap-1">
        <button type="submit" disabled={mutation.isPending} className="btn-primary text-xs flex-1">
          {mutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add"}
        </button>
        <button type="button" onClick={onClose} className="btn-ghost text-xs px-2"><X className="h-3 w-3" /></button>
      </div>
    </form>
  );
}

// ============================================================
// CREATE GOAL
// ============================================================
function CreateGoalForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [deadline, setDeadline] = useState("");
  const [icon, setIcon] = useState("target");
  const [color, setColor] = useState("blue");

  const mutation = useMutation({
    mutationFn: (body: CreateGoalBody) => createGoal(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !amount) return;
    mutation.mutate({ name, target_amount: parseFloat(amount), target_currency: currency, deadline: deadline || undefined, icon, color });
  };

  return (
    <div className="bento-card border-primary/20 animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          Create New Goal
        </h3>
        <button onClick={onClose} className="btn-icon"><X className="h-4 w-4" /></button>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="col-span-2">
            <label className="text-[10px] text-muted-foreground uppercase mb-1 block">What are you saving for?</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., Retirement, Dream Home" className="input-field w-full" required />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase mb-1 block">Target Amount</label>
            <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="10,00,000" step="1" className="input-field w-full" required />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase mb-1 block">Currency</label>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="input-field w-full">
              <option value="INR">₹ INR</option>
              <option value="USD">$ USD</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-muted-foreground uppercase mb-1 block">Target Date</label>
            <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="input-field w-full" />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase mb-1 block">Icon</label>
            <select value={icon} onChange={(e) => setIcon(e.target.value)} className="input-field w-full">
              <option value="target">🎯 Target</option>
              <option value="retirement">🐷 Retirement</option>
              <option value="home">🏠 Home</option>
              <option value="car">🚗 Car</option>
              <option value="emergency">🛡️ Emergency</option>
              <option value="coins">💰 Wealth</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase mb-1 block">Theme</label>
            <div className="flex gap-1.5 mt-1">
              {["blue", "green", "amber", "purple", "red"].map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`h-6 w-6 rounded-full border-2 transition-all ${
                    color === c ? "border-foreground scale-110" : "border-transparent"
                  } ${c === "blue" ? "bg-blue-500" : c === "green" ? "bg-emerald-500" : c === "amber" ? "bg-amber-500" : c === "purple" ? "bg-purple-500" : "bg-red-500"}`}
                />
              ))}
            </div>
          </div>
        </div>
        <button type="submit" disabled={mutation.isPending} className="btn-primary text-xs">
          {mutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <Plus className="h-3.5 w-3.5 mr-1.5" />}
          Create Goal
        </button>
      </form>
    </div>
  );
}

// ============================================================
// EMPTY + LOADING
// ============================================================
function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="bento-card text-center py-16 relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/3 to-emerald-500/3" />
      <div className="relative">
        <div className="h-16 w-16 mx-auto rounded-2xl bg-gradient-to-br from-blue-500/10 to-emerald-500/10 flex items-center justify-center mb-4">
          <Compass className="h-8 w-8 text-blue-500/50" />
        </div>
        <h3 className="text-lg font-bold">Set your first destination</h3>
        <p className="text-sm text-muted-foreground mt-2 max-w-xs mx-auto">
          Define a financial target — retirement, house, emergency fund. Track every step of the way.
        </p>
        <button onClick={onAdd} className="btn-primary text-xs mt-6">
          <Plus className="h-3.5 w-3.5 mr-1.5" /> Create First Goal
        </button>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-40 rounded-2xl bg-muted/50 animate-pulse" />
      <div className="h-24 rounded-xl bg-muted/50 animate-pulse" />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="h-48 rounded-xl bg-muted/50 animate-pulse" />
        <div className="h-48 rounded-xl bg-muted/50 animate-pulse" />
      </div>
    </div>
  );
}
