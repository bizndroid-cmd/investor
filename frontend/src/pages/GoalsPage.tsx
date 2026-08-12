import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getGoals, createGoal, deleteGoal, addEntry, getGoalEntries, deleteEntry, getWealthSummary,
  type GoalProgress, type CreateGoalBody, type AddEntryBody, type WealthSummary,
} from "@/api/goals";
import {
  Target, Plus, Trash2, PiggyBank, Home, Car, Shield,
  Loader2, ChevronDown, ChevronUp, Coins, X,
} from "lucide-react";

const GOAL_ICONS: Record<string, any> = {
  target: Target, retirement: PiggyBank, home: Home, car: Car, emergency: Shield, coins: Coins,
};

const GOAL_COLORS: Record<string, string> = {
  blue: "text-blue-500", green: "text-emerald-500", amber: "text-amber-500",
  purple: "text-purple-500", red: "text-red-500", pink: "text-pink-500",
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

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Target className="h-6 w-6 text-blue-500" />
            Financial Goals
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Track your journey towards financial targets</p>
        </div>
        <button onClick={() => setShowCreateGoal(true)} className="btn-primary text-xs">
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          New Goal
        </button>
      </div>

      {showCreateGoal && <CreateGoalForm onClose={() => setShowCreateGoal(false)} />}

      {summary && <WealthOverview summary={summary} />}

      {goals && goals.length > 0 ? (
        <div className="space-y-4">
          {goals.map((g) => <GoalCard key={g.id} goal={g} />)}
        </div>
      ) : (
        <EmptyState onAdd={() => setShowCreateGoal(true)} />
      )}
    </div>
  );
}

function WealthOverview({ summary }: { summary: WealthSummary }) {
  const formatL = (v: number) => v >= 100000 ? `₹${(v / 100000).toFixed(1)}L` : `₹${v.toLocaleString("en-IN")}`;

  return (
    <div className="bento-card bg-gradient-to-br from-blue-500/5 to-transparent">
      <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wide mb-3">Total Wealth</h3>
      <p className="text-2xl font-bold">{formatL(summary.total_wealth_inr)}</p>
      <div className="flex gap-4 mt-3 text-xs">
        <span className="text-muted-foreground">Stocks: <strong>{formatL(summary.breakdown.stocks_inr)}</strong></span>
        <span className="text-muted-foreground">ETFs: <strong>{formatL(summary.breakdown.etf_inr)}</strong></span>
        <span className="text-muted-foreground">Manual: <strong>{formatL(summary.breakdown.manual_inr)}</strong></span>
      </div>
    </div>
  );
}

function GoalCard({ goal }: { goal: GoalProgress }) {
  const [expanded, setExpanded] = useState(false);
  const [showAddEntry, setShowAddEntry] = useState(false);
  const queryClient = useQueryClient();
  const IconComp = GOAL_ICONS[goal.icon] || Target;
  const colorClass = GOAL_COLORS[goal.color] || "text-blue-500";
  const currency = goal.target_currency === "INR" ? "₹" : "$";

  const deleteMut = useMutation({
    mutationFn: () => deleteGoal(goal.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["goals"] }),
  });

  const formatAmount = (v: number) => `${currency}${v.toLocaleString(goal.target_currency === "INR" ? "en-IN" : "en-US", { maximumFractionDigits: 0 })}`;

  return (
    <div className="bento-card">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`h-10 w-10 rounded-xl bg-current/10 flex items-center justify-center ${colorClass}`}>
            <IconComp className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold">{goal.name}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {formatAmount(goal.current_total)} of {formatAmount(goal.target_amount)}
              {goal.deadline && <span className="ml-2">· Due {new Date(goal.deadline).toLocaleDateString(undefined, { month: "short", year: "numeric" })}</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setExpanded(!expanded)} className="btn-icon">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          <button onClick={() => deleteMut.mutate()} className="btn-icon text-muted-foreground hover:text-red-500">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-4">
        <div className="flex justify-between text-xs mb-1.5">
          <span className={`font-bold ${colorClass}`}>{goal.progress_pct.toFixed(0)}%</span>
          {goal.months_to_goal && (
            <span className="text-muted-foreground">~{goal.months_to_goal < 12 ? `${goal.months_to_goal.toFixed(0)} months` : `${(goal.months_to_goal / 12).toFixed(1)} years`} to go</span>
          )}
        </div>
        <div className="h-3 rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${goal.color === "green" ? "bg-emerald-500" : goal.color === "amber" ? "bg-amber-500" : goal.color === "purple" ? "bg-purple-500" : "bg-blue-500"}`}
            style={{ width: `${Math.min(100, goal.progress_pct)}%` }}
          />
        </div>
        {/* Milestones */}
        <div className="flex justify-between text-[9px] text-muted-foreground mt-1 px-0.5">
          <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
        </div>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-3 gap-2 mt-4 text-xs">
        <div className="text-center p-2 rounded-lg bg-secondary/30">
          <p className="text-[10px] text-muted-foreground">Stocks</p>
          <p className="font-medium">{formatAmount(goal.stocks_value)}</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-secondary/30">
          <p className="text-[10px] text-muted-foreground">ETFs</p>
          <p className="font-medium">{formatAmount(goal.etf_value)}</p>
        </div>
        <div className="text-center p-2 rounded-lg bg-secondary/30">
          <p className="text-[10px] text-muted-foreground">Deposits</p>
          <p className="font-medium">{formatAmount(goal.entries_total)}</p>
        </div>
      </div>

      {/* Expanded: entries */}
      {expanded && (
        <div className="mt-4 pt-4 border-t border-border animate-fade-in">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium">Wealth Entries ({goal.entries_count})</span>
            <button onClick={() => setShowAddEntry(true)} className="text-[10px] text-primary font-medium hover:underline">
              + Add Entry
            </button>
          </div>
          {showAddEntry && <AddEntryForm goalId={goal.id} currency={goal.target_currency} onClose={() => setShowAddEntry(false)} />}
          <EntriesList goalId={goal.id} />
        </div>
      )}
    </div>
  );
}

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
  if (!entries || entries.length === 0) return <p className="text-xs text-muted-foreground text-center py-2">No entries yet</p>;

  return (
    <div className="space-y-1.5">
      {entries.map((e) => (
        <div key={e.id} className="flex items-center justify-between text-xs py-1.5 px-2 rounded bg-muted/30">
          <div>
            <span className="font-medium">{e.label}</span>
            <span className="text-muted-foreground ml-2">{CATEGORY_LABELS[e.category] || e.category}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-medium">{e.currency === "INR" ? "₹" : "$"}{e.amount.toLocaleString()}</span>
            <span className="text-muted-foreground">{new Date(e.entry_date).toLocaleDateString(undefined, { month: "short", year: "2-digit" })}</span>
            <button onClick={() => deleteMut.mutate(e.id)} className="text-muted-foreground hover:text-red-500">
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
    <form onSubmit={handleSubmit} className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4 p-3 rounded-lg border bg-muted/20 animate-fade-in">
      <select value={category} onChange={(e) => setCategory(e.target.value)} className="input-field text-xs">
        {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label" className="input-field text-xs" required />
      <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount" step="0.01" className="input-field text-xs" required />
      <div className="flex gap-1">
        <select value={entryCurrency} onChange={(e) => setEntryCurrency(e.target.value)} className="input-field text-xs w-16">
          <option value="INR">₹</option>
          <option value="USD">$</option>
        </select>
        <input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} className="input-field text-xs flex-1" />
      </div>
      <div className="flex gap-1">
        <button type="submit" disabled={mutation.isPending} className="btn-primary text-xs flex-1">
          {mutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : "Add"}
        </button>
        <button type="button" onClick={onClose} className="btn-ghost text-xs"><X className="h-3 w-3" /></button>
      </div>
    </form>
  );
}

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
    mutation.mutate({
      name,
      target_amount: parseFloat(amount),
      target_currency: currency,
      deadline: deadline || undefined,
      icon,
      color,
    });
  };

  return (
    <div className="bento-card animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold">Create Goal</h3>
        <button onClick={onClose} className="btn-icon"><X className="h-4 w-4" /></button>
      </div>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="col-span-2">
            <label className="text-[10px] text-muted-foreground uppercase">Goal Name</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Retirement Fund" className="input-field w-full mt-1" required />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase">Target Amount</label>
            <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="1000000" step="1" className="input-field w-full mt-1" required />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase">Currency</label>
            <select value={currency} onChange={(e) => setCurrency(e.target.value)} className="input-field w-full mt-1">
              <option value="INR">₹ INR</option>
              <option value="USD">$ USD</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-[10px] text-muted-foreground uppercase">Deadline (optional)</label>
            <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="input-field w-full mt-1" />
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase">Icon</label>
            <select value={icon} onChange={(e) => setIcon(e.target.value)} className="input-field w-full mt-1">
              <option value="target">🎯 Target</option>
              <option value="retirement">🐷 Retirement</option>
              <option value="home">🏠 Home</option>
              <option value="car">🚗 Car</option>
              <option value="emergency">🛡️ Emergency</option>
              <option value="coins">💰 General</option>
            </select>
          </div>
          <div>
            <label className="text-[10px] text-muted-foreground uppercase">Color</label>
            <select value={color} onChange={(e) => setColor(e.target.value)} className="input-field w-full mt-1">
              <option value="blue">Blue</option>
              <option value="green">Green</option>
              <option value="amber">Amber</option>
              <option value="purple">Purple</option>
              <option value="red">Red</option>
            </select>
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

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="bento-card text-center py-12">
      <Target className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
      <p className="text-sm text-muted-foreground">No goals set yet</p>
      <p className="text-xs text-muted-foreground/70 mt-1">Create a financial target to start tracking progress</p>
      <button onClick={onAdd} className="btn-primary text-xs mt-4">
        <Plus className="h-3.5 w-3.5 mr-1.5" /> Create First Goal
      </button>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-48 rounded bg-muted animate-pulse" />
      <div className="bento-card h-24 animate-pulse bg-muted/50" />
      <div className="bento-card h-48 animate-pulse bg-muted/50" />
    </div>
  );
}
